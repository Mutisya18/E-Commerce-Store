import logging
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from apps.core.middleware import get_client_ip
from django.contrib import messages
from django.db import transaction
from django.db.models import F

from apps.orders.models import Order, OrderItem, Cart
from apps.orders.utils import get_cart, get_cart_subtotal, get_cart_delivery
from apps.core.logging import log_step

logger = logging.getLogger(__name__)

KENYAN_COUNTIES = [
    'Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret',
    'Thika', 'Kiambu', 'Machakos', 'Nyeri', 'Meru', 'Other',
]


def _validate_checkout_form(post):
    """Return (errors_dict, cleaned_data_dict)."""
    errors = {}
    data = {
        'full_name': post.get('full_name', '').strip(),
        'email': post.get('email', '').strip(),
        'phone': post.get('phone', '').strip(),
        'address_street': post.get('address_street', '').strip(),
        'address_city': post.get('address_city', '').strip(),
        'address_county': post.get('address_county', '').strip(),
        'payment_method': post.get('payment_method', '').strip(),
        'mpesa_number': post.get('mpesa_number', '').strip(),
        'notes': post.get('notes', '').strip()[:500],
    }

    if not data['full_name']:
        errors['full_name'] = 'Full name is required.'
    if not data['email'] or '@' not in data['email']:
        errors['email'] = 'A valid email is required.'
    if not data['phone']:
        errors['phone'] = 'Phone number is required.'
    if not data['address_street']:
        errors['address_street'] = 'Street address is required.'
    if not data['address_city']:
        errors['address_city'] = 'Town / City is required.'
    if data['address_county'] not in KENYAN_COUNTIES:
        errors['address_county'] = 'Select a valid county.'
    if data['payment_method'] not in ('mpesa', 'card'):
        errors['payment_method'] = 'Select a payment method.'
    if data['payment_method'] == 'mpesa' and not data['mpesa_number']:
        errors['mpesa_number'] = 'M-Pesa number is required.'

    return errors, data


def _clear_cart(request):
    if request.user.is_authenticated:
        try:
            request.user.cart.items.all().delete()
        except Exception:
            pass
    else:
        request.session['cart'] = {}


@require_http_methods(['GET', 'POST'])
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)
def checkout_view(request):
    cart_items = get_cart(request)

    if not cart_items:
        messages.warning(request, 'Your cart is empty.')
        return redirect('orders:cart')

    subtotal = get_cart_subtotal(cart_items)
    delivery = get_cart_delivery(cart_items)
    total = subtotal + delivery

    log_step('checkout', 'checkout_opened', request, item_count=len(cart_items), total=str(total))

    if request.method == 'GET':
        # Pre-fill from authenticated user profile
        prefill = {}
        if request.user.is_authenticated:
            u = request.user
            prefill = {
                'full_name': getattr(u, 'full_name', '') or f'{u.first_name} {u.last_name}'.strip(),
                'email': u.email,
                'phone': getattr(u, 'phone', '') or '',
            }
        return render(request, 'orders/checkout.html', {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery': delivery,
            'total': total,
            'counties': KENYAN_COUNTIES,
            'prefill': prefill,
        })

    # POST — place order
    log_step('checkout', 'place_order_submitted', request)

    errors, data = _validate_checkout_form(request.POST)
    if errors:
        log_step('checkout', 'checkout_validation_failed', request, errors=list(errors.keys()))
        return render(request, 'orders/checkout.html', {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery': delivery,
            'total': total,
            'counties': KENYAN_COUNTIES,
            'errors': errors,
            'form_data': data,
            'prefill': data,
        })

    try:
        with transaction.atomic():
            # Lock rows and validate stock before creating anything
            # select_for_update is a no-op on SQLite (dev); active on PostgreSQL (prod)
            from django.db import connection as _conn
            _use_lock = _conn.vendor != 'sqlite'
            for item in cart_items:
                qs = item['product'].__class__.objects.filter(pk=item['product'].pk)
                product = (qs.select_for_update() if _use_lock else qs).get()
                if product.stock < item['quantity']:
                    raise ValueError(f"'{product.name}' only has {product.stock} unit(s) left.")

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                guest_email=data['email'] if not request.user.is_authenticated else '',
                full_name=data['full_name'],
                email=data['email'],
                phone=data['phone'],
                address_street=data['address_street'],
                address_city=data['address_city'],
                address_county=data['address_county'],
                payment_method=data['payment_method'],
                payment_status=Order.PaymentStatus.PAID,   # mock: always succeeds
                status=Order.OrderStatus.PROCESSING,
                subtotal=subtotal,
                delivery_fee=delivery,
                total=total,
                notes=data['notes'],
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    product_name=item['product'].name,
                    product_price=item['product'].effective_price,
                    quantity=item['quantity'],
                )
                item['product'].__class__.objects.filter(pk=item['product'].pk).update(
                    stock=F('stock') - item['quantity']
                )

        if not request.user.is_authenticated:
            request.session['last_confirmed_order'] = order.order_number
            request.session['guest_order_email'] = order.guest_email

        _clear_cart(request)

        log_step('checkout', 'order_created', request,
                 order_number=order.order_number,
                 payment_method=data['payment_method'],
                 total=str(total))
        log_step('checkout', 'payment_success', request, order_number=order.order_number)
        log_step('checkout', 'journey_success', request, order_number=order.order_number)

        logger.info('order.created', extra={
            'order_number': order.order_number,
            'user_id': getattr(request.user, 'id', None),
            'total': str(total),
            'payment_method': data['payment_method'],
        })

        return redirect('payments:confirmation', order_number=order.order_number)

    except ValueError as exc:
        messages.error(request, str(exc))
        return render(request, 'orders/checkout.html', {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery': delivery,
            'total': total,
            'counties': KENYAN_COUNTIES,
            'form_data': data,
            'prefill': data,
        })
    except Exception as exc:
        logger.exception('order.create_failed', extra={'error': str(exc)})
        log_step('checkout', 'order_create_failed', request, error=str(exc))
        messages.error(request, 'Something went wrong placing your order. Please try again.')
        return render(request, 'orders/checkout.html', {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery': delivery,
            'total': total,
            'counties': KENYAN_COUNTIES,
            'form_data': data,
            'prefill': data,
        })


def order_confirmation(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)

    # Only the owner (or guest who just placed it) may view this page.
    if order.user and request.user.is_authenticated:
        if order.user != request.user and not request.user.is_staff:
            raise Http404
    elif order.user is None:
        if request.session.get('last_confirmed_order') != order_number:
            raise Http404

    log_step('checkout', 'confirmation_viewed', request, order_number=order_number)

    return render(request, 'orders/confirmation.html', {'order': order})
