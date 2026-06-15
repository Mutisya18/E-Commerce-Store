from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import random
from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed sales data over 90 days with variations'

    def handle(self, *args, **options):
        products = list(Product.objects.filter(is_visible=True)[:20])
        if not products:
            self.stdout.write(self.style.ERROR('No products found'))
            return

        users = list(User.objects.all()[:50])
        if not users:
            users = [User.objects.first()]

        # End date: today
        now = timezone.now()
        counties = ['Nairobi', 'Kiambu', 'Mombasa', 'Nakuru', 'Eldoret', 'Kisumu', 'Thika', 'Nyeri']
        statuses = [Order.OrderStatus.DELIVERED, Order.OrderStatus.SHIPPED, Order.OrderStatus.PROCESSING, Order.OrderStatus.PENDING]
        payment_methods = ['MPESA', 'CARD']

        created = 0
        
        for day_offset in range(90, 0, -1):
            order_date = now - timedelta(days=day_offset)
            weekday = order_date.weekday()
            daily_orders = random.randint(2, 6) if weekday in [5, 6] else random.randint(5, 15)
            
            for _ in range(daily_orders):
                user = random.choice(users)
                order = Order.objects.create(
                    user=user,
                    status=random.choices(statuses, weights=[70, 15, 10, 5])[0],
                    payment_status=Order.PaymentStatus.PAID,
                    payment_method=random.choices(payment_methods, weights=[72, 28])[0],
                    address_street=f'{random.randint(1,999)} Main St',
                    address_city='Nairobi',
                    address_county=random.choice(counties),
                    phone=f'+254{random.randint(700000000, 799999999)}',
                    subtotal=Decimal('0'),
                    total=Decimal('0')
                )
                
                # Override auto_now_add dates - queryset.update() bypasses auto_now
                Order.objects.filter(pk=order.pk).update(created_at=order_date, updated_at=order_date)
                order.refresh_from_db()
                
                order_total = Decimal('0')
                for _ in range(random.randint(1, 4)):
                    product = random.choice(products)
                    quantity = random.randint(1, 3)
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        product_price=product.base_price
                    )
                    order_total += product.base_price * quantity
                
                order.subtotal = order_total
                order.total = order_total
                order.save()
                created += 1
        
        self.stdout.write(self.style.SUCCESS(f'Created {created} orders over 90 days'))
