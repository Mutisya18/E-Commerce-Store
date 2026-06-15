import json


def cart_count(request):
    items = []
    count = 0

    if request.user.is_authenticated:
        try:
            for item in request.user.cart.items.select_related('product'):
                items.append({
                    'item_id': item.id,
                    'product_id': item.product_id,
                    'quantity': item.quantity,
                })
                count += item.quantity
        except Exception:
            pass
    else:
        for key, qty in request.session.get('cart', {}).items():
            try:
                items.append({
                    'item_id': None,
                    'product_id': int(key),
                    'quantity': qty,
                })
                count += qty
            except (ValueError, AttributeError):
                pass

    return {
        'cart_count': count,
        'cart_state_json': json.dumps({'items': items, 'count': count}),
    }
