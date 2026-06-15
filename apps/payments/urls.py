from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.checkout_view, name='checkout'),
    path('confirmation/<str:order_number>/', views.order_confirmation, name='confirmation'),
]
