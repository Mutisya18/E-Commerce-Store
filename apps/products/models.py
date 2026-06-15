from django.db import models
from django.db.models import Avg
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    icon = models.CharField(max_length=10, blank=True, help_text='Emoji icon, e.g. 📱')
    icon_name = models.CharField(max_length=60, default='squares-four', help_text='Phosphor icon name (kebab-case, no ph- prefix). e.g. device-mobile, laptop')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL, related_name='products')
    description = models.TextField()
    specs = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    is_visible = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deal_end_date = models.DateTimeField(null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_visible', 'created_at']),
            models.Index(fields=['is_visible', 'is_featured']),
            models.Index(fields=['category', 'is_visible']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    @property
    def cover_image(self):
        img = self.images.filter(is_cover=True).first()
        return img or self.images.first()

    @property
    def effective_price(self):
        return self.sale_price if self.sale_price else self.base_price

    @property
    def is_in_stock(self):
        return self.stock > 0

    @property
    def is_low_stock(self):
        return 0 < self.stock <= self.low_stock_threshold

    @property
    def discount_percent(self):
        if self.sale_price and self.sale_price < self.base_price and self.base_price > 0:
            return round((1 - self.sale_price / self.base_price) * 100)
        return None

    @property
    def average_rating(self):
        result = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(result, 1) if result else None


def product_image_upload_to(instance, filename):
    import os
    ext = os.path.splitext(filename)[1].lower()
    return f'products/{instance.product.id}-{instance.product.slug}-{instance.order}{ext}'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=product_image_upload_to, max_length=200)
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.product.name} image {self.order}'


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')

    def __str__(self):
        return f'{self.user.email} — {self.product.name} ({self.rating}★)'
