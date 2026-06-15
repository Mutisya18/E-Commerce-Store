from decimal import Decimal


def get_cart(request):
    """Returns unified cart list regardless of session or DB."""
    items = []

    if request.user.is_authenticated:
        try:
            cart = request.user.cart
            for item in cart.items.select_related('product').prefetch_related('product__images'):
                items.append({
                    'item_id': item.id,
                    'product': item.product,
                    'quantity': item.quantity,
                    'line_total': item.line_total,
                })
        except Exception:
            pass
    else:
        from apps.products.models import Product
        session_cart = request.session.get('cart', {})
        for key, qty in session_cart.items():
            try:
                product = Product.objects.prefetch_related('images').get(id=int(key), is_visible=True)
                items.append({
                    'item_id': None,
                    'product': product,
                    'quantity': qty,
                    'line_total': product.effective_price * qty,
                    'session_key': key,
                })
            except Exception:
                pass

    return items


def get_cart_subtotal(cart_items):
    return sum(i['line_total'] for i in cart_items)


def get_cart_delivery(cart_items):
    seen = set()
    total = Decimal('0')
    for i in cart_items:
        pid = i['product'].id
        if pid not in seen:
            total += i['product'].delivery_fee
            seen.add(pid)
    return total
