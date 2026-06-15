from django.core.management.base import BaseCommand
from apps.products.models import Product
import random

class Command(BaseCommand):
    help = 'Update existing products with stock and prices'

    def handle(self, *args, **options):
        products = Product.objects.all()
        
        if not products.exists():
            self.stdout.write(self.style.ERROR('No products found. Create products first.'))
            return
        
        for product in products:
            # Set realistic prices
            if product.base_price == 0:
                product.base_price = random.choice([1500, 2500, 3500, 4500, 5500, 7500, 9500, 12000, 15000])
            
            # Set stock levels
            product.stock = random.randint(5, 50)
            product.low_stock_threshold = 5
            
            product.save()
            self.stdout.write(f'Updated {product.name}: KES {product.base_price}, Stock: {product.stock}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {products.count()} products'))
