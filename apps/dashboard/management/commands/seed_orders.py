from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.products.models import Product, Category
from apps.orders.models import Order, OrderItem
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed database with sample orders and data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')
        
        # Get or create test user
        user, _ = User.objects.get_or_create(
            email='buyer@test.com',
            defaults={'username': 'buyer@test.com'}
        )
        
        # Get products
        products = list(Product.objects.all()[:10])
        if not products:
            self.stdout.write(self.style.ERROR('No products found. Please add products first.'))
            return
        
        # Create 50 orders over the past 30 days
        now = timezone.now()
        statuses = [
            Order.OrderStatus.PENDING,
            Order.OrderStatus.PROCESSING,
            Order.OrderStatus.SHIPPED,
            Order.OrderStatus.DELIVERED,
            Order.OrderStatus.CANCELLED,
        ]
        payment_statuses = [
            Order.PaymentStatus.PAID,
            Order.PaymentStatus.PENDING,
            Order.PaymentStatus.FAILED,
        ]
        payment_methods = [Order.PaymentMethod.MPESA, Order.PaymentMethod.CARD]
        
        names = [
            'Jane Wanjiku', 'David Otieno', 'Aisha Kamau', 'Peter Mwangi',
            'Grace Njeri', 'Samuel Kiprotich', 'Mary Wachira', 'John Omondi',
            'Faith Akinyi', 'Michael Kariuki', 'Lucy Wambui', 'James Mutua',
            'Sarah Chebet', 'Daniel Kipchoge', 'Rose Nyambura', 'Brian Odhiambo'
        ]
        
        for i in range(50):
            # Random date in past 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            
            # Random customer
            name = random.choice(names)
            email = f"{name.lower().replace(' ', '.')}@example.com"
            phone = f"+2547{random.randint(10000000, 99999999)}"
            
            # Random products (1-3 items)
            num_items = random.randint(1, 3)
            order_products = random.sample(products, min(num_items, len(products)))
            
            subtotal = sum(p.base_price * random.randint(1, 2) for p in order_products)
            delivery_fee = Decimal('500.00')
            total = subtotal + delivery_fee
            
            # Create order
            order = Order.objects.create(
                user=user if random.random() > 0.3 else None,  # 30% guest orders
                guest_email=email if not user else '',
                full_name=name,
                email=email,
                phone=phone,
                address_street=f"{random.randint(1, 999)} {random.choice(['Kenyatta', 'Moi', 'Uhuru', 'Kimathi'])} Avenue",
                address_city=random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru']),
                address_county=random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru']),
                status=random.choice(statuses),
                payment_method=random.choice(payment_methods),
                payment_status=random.choice(payment_statuses),
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                total=total,
                created_at=created_at,
            )
            
            # Create order items
            for product in order_products:
                quantity = random.randint(1, 2)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    product_price=product.base_price,
                    quantity=quantity,
                )
            
            self.stdout.write(f'Created order {order.order_number}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded 50 orders'))
