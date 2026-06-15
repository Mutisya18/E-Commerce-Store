import logging
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from apps.products.models import Product
from apps.orders.models import Cart, CartItem
from apps.orders.utils import get_cart, get_cart_subtotal, get_cart_delivery
from apps.core.logging import log_step

logger = logging.getLogger(__name__)


def _session_cart_count(request):
    return sum(request.session.get('cart', {}).values())


def _db_cart_count(user):
    from django.db.models import Sum
    try:
        return user.cart.items.aggregate(t=Sum('quantity'))['t'] or 0
    except Exception:
        return 0


def cart_count(request):
    if request.user.is_authenticated:
        return _db_cart_count(request.user)
    return _session_cart_count(request)


@require_POST
@ratelimit(key='user_or_ip', rate='30/m', method='POST', block=True)
def cart_add(request):
    try:
        product_id = int(request.POST.get('product_id', 0))
        quantity = max(0, min(99, int(request.POST.get('quantity', 1))))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    product = get_object_or_404(Product, id=product_id, is_visible=True)
    if not product.is_in_stock:
        return JsonResponse({'ok': False, 'error': 'Out of stock'})

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        if quantity == 0:
            CartItem.objects.filter(cart=cart, product=product).delete()
        else:
            item, _ = CartItem.objects.get_or_create(cart=cart, product=product)
            item.quantity = quantity
            item.save(update_fields=['quantity'])
        count = _db_cart_count(request.user)
        item_id = CartItem.objects.filter(cart=cart, product=product).values_list('id', flat=True).first()
    else:
        key = str(product_id)
        session_cart = request.session.get('cart', {})
        if quantity == 0:
            session_cart.pop(key, None)
        else:
            session_cart[key] = quantity
        request.session['cart'] = session_cart
        count = _session_cart_count(request)
        item_id = None

    logger.info('cart.add', extra={'user_id': getattr(request.user, 'id', None), 'product_id': product_id, 'quantity': quantity})
    log_step('cart', 'add_to_cart_clicked', request, product_id=product_id, quantity=quantity, cart_count=count)
    return JsonResponse({'ok': True, 'cart_count': count, 'item_id': item_id})


@require_POST
def cart_update(request, item_id):
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid quantity'}, status=400)

    if request.user.is_authenticated:
        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        if quantity <= 0:
            item.delete()
        else:
            item.quantity = min(99, quantity)
            item.save(update_fields=['quantity'])
        cart_items = get_cart(request)
        subtotal = get_cart_subtotal(cart_items)
        count = _db_cart_count(request.user)
        line_total = f'KES {item.line_total:,.0f}' if quantity > 0 else 'KES 0'
    else:
        # session cart: item_id is the session key
        session_cart = request.session.get('cart', {})
        key = request.POST.get('session_key', '')
        if quantity <= 0:
            session_cart.pop(key, None)
        else:
            session_cart[key] = min(99, quantity)
        request.session['cart'] = session_cart
        cart_items = get_cart(request)
        subtotal = get_cart_subtotal(cart_items)
        count = _session_cart_count(request)
        line_total = 'KES 0'

    return JsonResponse({
        'ok': True,
        'cart_count': count,
        'line_total': f'KES {subtotal:,.0f}',
        'subtotal': f'KES {subtotal:,.0f}',
    })


@require_POST
def cart_remove(request, item_id):
    if request.user.is_authenticated:
        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        item.delete()
        count = _db_cart_count(request.user)
    else:
        key = request.POST.get('session_key', '')
        session_cart = request.session.get('cart', {})
        session_cart.pop(key, None)
        request.session['cart'] = session_cart
        count = _session_cart_count(request)

    logger.info('cart.remove', extra={'user_id': getattr(request.user, 'id', None), 'item_id': item_id})
    log_step('cart', 'cart_item_removed', request, item_id=item_id, cart_count=count)
    return JsonResponse({'ok': True, 'cart_count': count})


def cart_view(request):
    cart_items = get_cart(request)
    subtotal = get_cart_subtotal(cart_items)
    delivery = get_cart_delivery(cart_items)
    return render(request, 'orders/cart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'delivery': delivery,
        'total': subtotal + delivery,
    })


def order_detail(request, order_number):
    from apps.orders.models import Order
    from django.utils import timezone
    
    order = get_object_or_404(Order, order_number=order_number)
    
    # Security: only show order to owner or guest with matching email
    if request.user.is_authenticated:
        if order.user != request.user:
            return render(request, '404.html', status=404)
    else:
        # Guest order - check session
        guest_email = request.session.get('guest_order_email')
        if not guest_email or order.guest_email != guest_email:
            return render(request, '404.html', status=404)
    
    # Build timeline based on order status
    timeline = []
    now = timezone.now()
    
    # Order placed
    timeline.append({
        'label': 'Order placed',
        'time': order.created_at,
        'status': 'done'
    })
    
    # Payment confirmed
    if order.payment_status == Order.PaymentStatus.PAID:
        timeline.append({
            'label': 'Payment confirmed',
            'time': order.created_at,
            'status': 'done'
        })
    
    # Processing
    if order.status in [Order.OrderStatus.PROCESSING, Order.OrderStatus.SHIPPED, Order.OrderStatus.OUT_FOR_DELIVERY, Order.OrderStatus.DELIVERED]:
        timeline.append({
            'label': 'Processing',
            'time': order.updated_at if order.status != Order.OrderStatus.PENDING else None,
            'status': 'done' if order.status != Order.OrderStatus.PROCESSING else 'active'
        })
    else:
        timeline.append({
            'label': 'Processing',
            'time': None,
            'status': 'active' if order.status == Order.OrderStatus.PROCESSING else 'pending'
        })
    
    # Shipped
    if order.status in [Order.OrderStatus.SHIPPED, Order.OrderStatus.OUT_FOR_DELIVERY, Order.OrderStatus.DELIVERED]:
        timeline.append({
            'label': 'Shipped',
            'time': order.updated_at,
            'status': 'done' if order.status != Order.OrderStatus.SHIPPED else 'active'
        })
    else:
        timeline.append({
            'label': 'Shipped',
            'time': None,
            'status': 'pending'
        })
    
    # Delivered
    if order.status == Order.OrderStatus.DELIVERED:
        timeline.append({
            'label': 'Delivered',
            'time': order.updated_at,
            'status': 'done'
        })
    else:
        timeline.append({
            'label': 'Delivered',
            'time': None,
            'status': 'pending'
        })
    
    # Estimate delivery date (3-5 days from order)
    from datetime import timedelta
    est_start = (order.created_at + timedelta(days=3)).strftime('%d %b')
    est_end = (order.created_at + timedelta(days=5)).strftime('%d %b')
    
    context = {
        'order': order,
        'timeline': timeline,
        'est_delivery': f'{est_start}–{est_end}',
    }
    
    return render(request, 'orders/order_detail.html', context)
