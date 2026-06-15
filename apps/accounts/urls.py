from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('profile/orders/', views.order_history_view, name='order_history'),
    path('check-username/', views.check_username, name='check_username'),
]
