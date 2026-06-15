from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('products/', views.listing_view, name='listing'),
    path('products/<slug:slug>/', views.product_detail_view, name='product_detail'),
    path('categories/<slug:slug>/', views.category_view, name='category'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('products/<slug:slug>/review/', views.review_submit, name='review_submit'),
]
