import logging
from allauth.account.signals import user_logged_in
from django.dispatch import receiver
from apps.orders.models import Cart, CartItem
from apps.products.models import Product
from apps.core.logging import log_step

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def merge_session_cart(request, user, **kwargs):
    session_cart = request.session.get('cart', {})
    log_step('login', 'login_response_200', request, user_id=user.id)

    if not session_cart:
        log_step('login', 'journey_success', request, user_id=user.id)
        return

    cart, _ = Cart.objects.get_or_create(user=user)
    merged = 0

    for key, qty in session_cart.items():
        try:
            product = Product.objects.get(id=int(key), is_visible=True)
            item, created = CartItem.objects.get_or_create(cart=cart, product=product)
            item.quantity = qty if created else item.quantity + qty
            item.save(update_fields=['quantity'])
            merged += 1
        except (Product.DoesNotExist, ValueError):
            pass

    del request.session['cart']
    logger.info('cart.merged', extra={'user_id': user.id, 'items_merged': merged})
    log_step('login', 'cart_merged', request, user_id=user.id, items_merged=merged)
    log_step('login', 'journey_success', request, user_id=user.id)
