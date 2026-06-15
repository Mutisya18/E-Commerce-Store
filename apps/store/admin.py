from django.contrib import admin
from .models import Testimonial, NewsletterSubscriber


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('reviewer_name', 'rating', 'is_visible', 'order', 'created_at')
    list_filter = ('is_visible', 'rating')


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'subscribed_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('email',)
