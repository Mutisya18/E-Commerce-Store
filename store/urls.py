from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.orders.views import order_detail

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('', include('apps.store.urls')),
    path('products/', include('apps.products.urls')),
    path('cart/', include('apps.orders.urls')),
    path('orders/<str:order_number>/', order_detail, name='order_detail'),
    path('checkout/', include('apps.payments.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
