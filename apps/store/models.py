from django.db import models


class Testimonial(models.Model):
    reviewer_name = models.CharField(max_length=100)
    review_text = models.TextField()
    rating = models.PositiveSmallIntegerField()
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f'{self.reviewer_name} ({self.rating}★)'


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email
