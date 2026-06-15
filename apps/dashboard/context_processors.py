def notif_count(request):
    from apps.dashboard.models import DashboardNotification
    count = 0
    if request.user.is_authenticated and request.user.is_staff:
        count = DashboardNotification.objects.filter(is_read=False).count()
    return {'unread_notif_count': count}


def global_context(request):
    """Injects nav_categories and store_settings into every template."""
    from apps.products.models import Category
    from apps.dashboard.models import StoreSettings
    return {
        'nav_categories': Category.objects.filter(parent=None).order_by('order')[:8],
        'store_settings': StoreSettings.get(),
    }
