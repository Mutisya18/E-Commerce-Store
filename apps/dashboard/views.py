import json
import logging
from functools import wraps
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _mask_email(email):
    local, _, domain = email.partition('@')
    return f'{local[:2]}{"*" * (len(local) - 2)}@{domain}' if domain else email[:2] + '***'

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60
_SESSION_TIMEOUT = 12 * 60 * 60  # 12 hours


def dashboard_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect('/dashboard/login/')
        # Session timeout check
        last = request.session.get('dashboard_last_activity')
        now = timezone.now().timestamp()
        if last and (now - last) > _SESSION_TIMEOUT:
            logout(request)
            return redirect('/dashboard/login/?timeout=1')
        request.session['dashboard_last_activity'] = now
        return view_func(request, *args, **kwargs)
    return wrapper


def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/dashboard/')

    error = None
    if request.GET.get('timeout'):
        error = 'Session expired. Please sign in again.'

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        # Derive client IP (behind PaaS proxy)
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
        cache_key = f'dashboard_login_attempts_{email}_{ip}'

        attempts = cache.get(cache_key, {'count': 0, 'since': 0})
        now = timezone.now().timestamp()
        if attempts['count'] >= _MAX_ATTEMPTS:
            remaining = int((_LOCKOUT_SECONDS - (now - attempts['since'])) / 60) + 1
            error = f'Too many failed attempts. Try again in {remaining} minute(s).'
            return render(request, 'dashboard/login.html', {'error': error})

        user = authenticate(request, username=email, password=password)
        if user and user.is_staff and user.is_active:
            login(request, user)
            request.session['dashboard_last_activity'] = now
            cache.delete(cache_key)
            logger.info('dashboard.login', extra={'user_id': user.id, 'email': _mask_email(email)})
            return redirect('/dashboard/')
        else:
            attempts['count'] += 1
            if attempts['count'] == 1:
                attempts['since'] = now
            cache.set(cache_key, attempts, timeout=_LOCKOUT_SECONDS)
            error = 'Invalid credentials or insufficient permissions.'
            logger.warning('dashboard.login_failed', extra={'email': _mask_email(email), 'attempt': attempts['count']})

    return render(request, 'dashboard/login.html', {'error': error})


@require_POST
def logout_view(request):
    logger.info('dashboard.logout', extra={'user_id': request.user.id})
    logout(request)
    return redirect('/dashboard/login/')


@dashboard_login_required
def home_stats_api(request):
    """Returns stats JSON for the given period — used by the overview AJAX tabs."""
    from django.db.models import Sum, Count, Avg, F
    from apps.orders.models import Order, OrderItem
    from apps.products.models import Product
    from datetime import timedelta
    from django.http import JsonResponse

    period = request.GET.get('period', 'month')
    now = timezone.now()

    if period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=30)

    period_length = max((now - start_date).days, 1)
    prev_start = start_date - timedelta(days=period_length)

    paid_orders = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
    period_orders = paid_orders.filter(created_at__gte=start_date)
    prev_orders = paid_orders.filter(created_at__gte=prev_start, created_at__lt=start_date)

    period_revenue = float(period_orders.aggregate(t=Sum('total'))['t'] or 0)
    prev_revenue = float(prev_orders.aggregate(t=Sum('total'))['t'] or 0)
    revenue_change = ((period_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0

    avg_order_value = float(paid_orders.aggregate(avg=Avg('total'))['avg'] or 0)
    units_sold = OrderItem.objects.filter(
        order__payment_status=Order.PaymentStatus.PAID,
        order__created_at__gte=start_date
    ).aggregate(t=Sum('quantity'))['t'] or 0

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.objects.filter(created_at__gte=today_start).count()

    week_ago = now - timedelta(days=7)
    top_products = list(OrderItem.objects.filter(
        order__created_at__gte=week_ago,
        order__payment_status=Order.PaymentStatus.PAID
    ).values('product__name').annotate(units_sold=Sum('quantity')).order_by('-units_sold')[:5])

    low_stock = list(Product.objects.filter(
        stock__gt=0, stock__lte=F('low_stock_threshold')
    ).values('name', 'stock').order_by('stock')[:10])

    from django.db.models.functions import TruncHour, TruncDay
    trunc = TruncHour if period == 'today' else TruncDay
    fmt = '%H:%M' if period == 'today' else '%d %b'
    rev_by_day = list(period_orders.annotate(bucket=trunc('created_at'))
        .values('bucket').annotate(revenue=Sum('total')).order_by('bucket'))

    return JsonResponse({
        'period_revenue': period_revenue,
        'revenue_change': revenue_change,
        'today_orders': today_orders,
        'avg_order_value': avg_order_value,
        'units_sold': units_sold,
        'top_products': top_products,
        'low_stock_products': low_stock,
        'rev_labels': [r['bucket'].strftime(fmt) for r in rev_by_day],
        'rev_data': [float(r['revenue']) for r in rev_by_day],
    })


@dashboard_login_required
def home_view(request):
    from django.db.models import Sum, Count, Q, F, Avg
    from apps.orders.models import Order, OrderItem
    from apps.products.models import Product
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Date filter
    period = request.GET.get('period', 'month')
    now = timezone.now()
    
    if period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=30)
    
    # Previous period for comparison
    period_length = (now - start_date).days
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date
    
    # Stats
    paid_orders = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
    period_orders = paid_orders.filter(created_at__gte=start_date)
    prev_period_orders = paid_orders.filter(created_at__gte=prev_start, created_at__lt=prev_end)
    
    total_revenue = paid_orders.aggregate(total=Sum('total'))['total'] or 0
    period_revenue = period_orders.aggregate(total=Sum('total'))['total'] or 0
    prev_revenue = prev_period_orders.aggregate(total=Sum('total'))['total'] or 0
    
    # Revenue trend
    revenue_change = 0
    if prev_revenue > 0:
        revenue_change = ((period_revenue - prev_revenue) / prev_revenue) * 100
    
    total_orders = Order.objects.count()
    pending_orders_count = Order.objects.filter(status=Order.OrderStatus.PENDING).count()
    
    # Average order value
    avg_order_value = paid_orders.aggregate(avg=Avg('total'))['avg'] or 0
    
    # Units sold
    units_sold = OrderItem.objects.filter(
        order__payment_status=Order.PaymentStatus.PAID,
        order__created_at__gte=start_date
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Today's orders
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.objects.filter(created_at__gte=today_start).count()
    
    # Order status breakdown
    order_status_counts = {
        'pending': Order.objects.filter(status=Order.OrderStatus.PENDING).count(),
        'processing': Order.objects.filter(status=Order.OrderStatus.PROCESSING).count(),
        'shipped': Order.objects.filter(status=Order.OrderStatus.SHIPPED).count(),
        'delivered': Order.objects.filter(status=Order.OrderStatus.DELIVERED).count(),
        'cancelled': Order.objects.filter(status=Order.OrderStatus.CANCELLED).count(),
    }
    
    # Payment breakdown
    payment_counts = {
        'paid': Order.objects.filter(payment_status=Order.PaymentStatus.PAID).count(),
        'pending': Order.objects.filter(payment_status=Order.PaymentStatus.PENDING).count(),
        'failed': Order.objects.filter(payment_status=Order.PaymentStatus.FAILED).count(),
    }
    
    # Payment method breakdown
    payment_methods = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID
    ).values('payment_method').annotate(count=Count('id'))
    
    # Recent orders (last 10)
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:10]
    
    # Top selling products this week
    week_ago = now - timedelta(days=7)
    top_products = OrderItem.objects.filter(
        order__created_at__gte=week_ago,
        order__payment_status=Order.PaymentStatus.PAID
    ).values('product__name').annotate(
        units_sold=Sum('quantity')
    ).order_by('-units_sold')[:5]
    
    # Low stock products
    low_stock_products = Product.objects.filter(
        stock__gt=0,
        stock__lte=F('low_stock_threshold')
    ).select_related('category').order_by('stock')[:10]
    
    context = {
        'total_revenue': total_revenue,
        'period_revenue': period_revenue,
        'revenue_change': revenue_change,
        'total_orders': total_orders,
        'pending_orders_count': pending_orders_count,
        'avg_order_value': avg_order_value,
        'units_sold': units_sold,
        'today_orders': today_orders,
        'total_products': Product.objects.count(),
        'order_status_counts': order_status_counts,
        'payment_counts': payment_counts,
        'payment_methods': payment_methods,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'low_stock_products': low_stock_products,
        'period': period,
        'top_products_json': json.dumps(list(top_products)),
        'low_stock_json': json.dumps(list(low_stock_products.values('name', 'stock'))),
    }

    # Daily revenue series for the overview chart
    from django.db.models.functions import TruncHour, TruncDay
    trunc = TruncHour if period == 'today' else TruncDay
    fmt = '%H:%M' if period == 'today' else '%d %b'
    rev_by_day = list(
        Order.objects.filter(payment_status=Order.PaymentStatus.PAID, created_at__gte=start_date)
        .annotate(bucket=trunc('created_at'))
        .values('bucket').annotate(revenue=Sum('total')).order_by('bucket')
    )
    context['rev_labels_json'] = json.dumps([r['bucket'].strftime(fmt) for r in rev_by_day])
    context['rev_data_json'] = json.dumps([float(r['revenue']) for r in rev_by_day])

    return render(request, 'dashboard/home.html', context)


@dashboard_login_required
def products_list(request):
    from apps.products.models import Product, Category

    products = Product.objects.select_related('category').prefetch_related('images').order_by('-created_at')
    categories = Category.objects.all().order_by('name')

    return render(request, 'dashboard/products.html', {
        'products': products,
        'categories': categories,
        'total_count': products.count(),
    })


@dashboard_login_required
def product_toggle_visibility(request, pk):
    from apps.products.models import Product
    from django.http import JsonResponse
    if request.method == 'POST':
        product = Product.objects.get(pk=pk)
        product.is_visible = not product.is_visible
        product.save(update_fields=['is_visible'])
        return JsonResponse({'is_visible': product.is_visible})
    return JsonResponse({'error': 'POST required'}, status=405)


@dashboard_login_required
def product_edit(request, pk):
    from apps.products.models import Product, ProductImage
    from django.shortcuts import get_object_or_404
    from django.contrib import messages as msg
    import json
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.name = request.POST.get('name', product.name).strip()
        cat_id = request.POST.get('category')
        if cat_id:
            from apps.products.models import Category
            product.category_id = int(cat_id)
        product.sku = request.POST.get('sku', '').strip()
        product.base_price = request.POST.get('base_price') or product.base_price
        sale = request.POST.get('sale_price', '').strip()
        product.sale_price = sale if sale and float(sale) > 0 else None
        product.stock = int(request.POST.get('stock') or product.stock)
        product.low_stock_threshold = int(request.POST.get('low_stock_threshold') or product.low_stock_threshold)
        product.description = request.POST.get('description', '').strip()
        # specs: stored as "Key: Value\n" lines from JSON array
        specs_json = request.POST.get('specs_json', '')
        if specs_json:
            if len(specs_json) > 10000:
                from django.contrib import messages as msg
                msg.error(request, 'Specs data is too large.')
                return redirect(f'/dashboard/products/{pk}/edit/')
            try:
                pairs = json.loads(specs_json)
                product.specs = '\n'.join(f"{p['k']}: {p['v']}" for p in pairs if p.get('k') and p.get('v'))
            except (ValueError, KeyError):
                product.specs = request.POST.get('specs', product.specs)
        product.is_visible = request.POST.get('is_visible') == 'on'
        product.is_featured = request.POST.get('is_featured') == 'on'
        deal = request.POST.get('deal_end_date', '').strip()
        if deal:
            from django.utils.dateparse import parse_datetime
            product.deal_end_date = parse_datetime(deal)
        else:
            product.deal_end_date = None
        product.save()
        # Handle new image uploads
        from apps.dashboard.utils import validate_and_rename_image
        for f in request.FILES.getlist('new_images'):
            try:
                validate_and_rename_image(f)
            except ValueError:
                continue
            has_cover = product.images.filter(is_cover=True).exists()
            ProductImage.objects.create(
                product=product,
                image=f,
                is_cover=not has_cover,
                order=product.images.count(),
            )
    return redirect(f'/dashboard/products/{pk}/')


@dashboard_login_required
def product_flag_toggle(request, pk):
    """AJAX: toggle is_featured or is_visible without entering edit mode."""
    from apps.products.models import Product
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    import json
    data = json.loads(request.body)
    field = data.get('field')
    if field not in ('is_featured', 'is_visible'):
        return JsonResponse({'error': 'invalid field'}, status=400)
    product = Product.objects.get(pk=pk)
    new_val = not getattr(product, field)
    setattr(product, field, new_val)
    product.save(update_fields=[field])
    return JsonResponse({field: new_val})


@dashboard_login_required
def product_add(request):
    from apps.products.models import Product, Category, ProductImage
    from django.utils.text import slugify
    import json, uuid

    categories = Category.objects.order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        cat_id = request.POST.get('category', '')
        sku = request.POST.get('sku', '').strip()
        description = request.POST.get('description', '').strip()
        base_price = request.POST.get('base_price') or 0
        sale_raw = request.POST.get('sale_price', '').strip()
        sale_price = float(sale_raw) if sale_raw and float(sale_raw) > 0 else None
        stock = int(request.POST.get('stock') or 0)
        threshold = int(request.POST.get('low_stock_threshold') or 5)
        is_visible = request.POST.get('is_visible') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        deal = request.POST.get('deal_end_date', '').strip()
        specs_json = request.POST.get('specs_json', '')

        # Build specs text
        specs = ''
        if specs_json:
            if len(specs_json) > 10000:
                from django.contrib import messages as msg
                msg.error(request, 'Specs data is too large.')
                return render(request, 'dashboard/product_add.html', {'categories': categories})
            try:
                pairs = json.loads(specs_json)
                specs = '\n'.join(f"{p['k']}: {p['v']}" for p in pairs if p.get('k') and p.get('v'))
            except (ValueError, KeyError):
                pass

        # Unique slug
        base_slug = slugify(name)
        slug = base_slug
        n = 1
        while Product.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{n}'; n += 1

        product = Product.objects.create(
            name=name, slug=slug, sku=sku,
            description=description, specs=specs,
            base_price=base_price, sale_price=sale_price,
            stock=stock, low_stock_threshold=threshold,
            is_visible=is_visible, is_featured=is_featured,
        )
        if cat_id:
            product.category_id = int(cat_id)
        if deal:
            from django.utils.dateparse import parse_datetime
            product.deal_end_date = parse_datetime(deal)
        product.save()

        # Images
        from apps.dashboard.utils import validate_and_rename_image
        for f in request.FILES.getlist('images'):
            try:
                validate_and_rename_image(f)
            except ValueError:
                continue
            is_cover = not product.images.exists()
            ProductImage.objects.create(product=product, image=f, is_cover=is_cover, order=product.images.count())

        return redirect(f'/dashboard/products/{product.pk}/')

    return render(request, 'dashboard/product_add.html', {'categories': categories})


@dashboard_login_required
def product_detail(request, pk):
    from apps.products.models import Product, Category
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(Product.objects.select_related('category').prefetch_related('images'), pk=pk)
    categories = Category.objects.order_by('name')
    return render(request, 'dashboard/product_detail.html', {'product': product, 'categories': categories})


@dashboard_login_required
def product_update_stock(request, pk):
    from apps.products.models import Product
    from django.http import JsonResponse
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        stock = int(data.get('stock', 0))
        Product.objects.filter(pk=pk).update(stock=stock)
        return JsonResponse({'stock': stock})
    return JsonResponse({'error': 'POST required'}, status=405)


@dashboard_login_required
def product_delete(request, pk):
    from apps.products.models import Product
    from django.contrib import messages
    if request.method == 'POST':
        Product.objects.filter(pk=pk).delete()
        messages.success(request, 'Product deleted.')
    return redirect('/dashboard/products/')


@dashboard_login_required
def set_cover(request, pk):
    from apps.products.models import ProductImage
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    image_id = request.POST.get('image_id')
    ProductImage.objects.filter(product_id=pk).update(is_cover=False)
    ProductImage.objects.filter(pk=image_id, product_id=pk).update(is_cover=True)
    return JsonResponse({'ok': True})


@dashboard_login_required
def reorder_images(request, pk):
    import json
    from apps.products.models import ProductImage
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    order = json.loads(request.body).get('order', [])  # list of image ids
    for i, image_id in enumerate(order):
        ProductImage.objects.filter(pk=image_id, product_id=pk).update(order=i)
    return JsonResponse({'ok': True})


@dashboard_login_required
def order_detail(request, order_number):
    from apps.orders.models import Order, OrderNote
    from django.shortcuts import get_object_or_404
    order = get_object_or_404(Order.objects.prefetch_related('items__product', 'admin_notes'), order_number=order_number)
    return render(request, 'dashboard/order_detail.html', {
        'order': order,
        'status_choices': Order.OrderStatus.choices,
    })


@dashboard_login_required
def order_update_status(request, order_number):
    from apps.orders.models import Order
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    order = get_object_or_404(Order, order_number=order_number)
    new_status = request.POST.get('status')
    valid = [s for s, _ in Order.OrderStatus.choices]
    if new_status not in valid:
        return JsonResponse({'error': 'invalid status'}, status=400)
    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'status': order.status, 'label': order.get_status_display()})


@dashboard_login_required
def order_add_note(request, order_number):
    from apps.orders.models import Order, OrderNote
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    order = get_object_or_404(Order, order_number=order_number)
    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'error': 'empty note'}, status=400)
    note = OrderNote.objects.create(order=order, body=body)
    return JsonResponse({
        'id': note.pk,
        'body': note.body,
        'created_at': note.created_at.strftime('%d %b %Y, %H:%M'),
    })


@dashboard_login_required
def analytics(request):
    from django.db.models import Sum, Count, Avg, F, Q
    from django.db.models.functions import TruncDay, TruncWeek
    from apps.orders.models import Order, OrderItem, Cart, CartItem
    from apps.products.models import Product
    from apps.payments.models import Payment
    from datetime import timedelta
    import json

    # Always use last 30 days since period switcher was removed
    period = '30'
    now = timezone.now()
    start = now - timedelta(days=30)

    days = (now - start).days or 1
    prev_start = start - timedelta(days=days)

    paid = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
    period_paid = paid.filter(created_at__gte=start)
    prev_paid = paid.filter(created_at__gte=prev_start, created_at__lt=start)

    def pct_change(curr, prev):
        if not prev: return None
        return round((curr - prev) / prev * 100, 1)

    # KPI values - separate calculations for different periods
    # Today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    today_paid = paid.filter(created_at__gte=today_start)
    yesterday_paid = paid.filter(created_at__gte=yesterday_start, created_at__lt=today_start)
    
    revenue_today = float(today_paid.aggregate(t=Sum('total'))['t'] or 0)
    revenue_yesterday = float(yesterday_paid.aggregate(t=Sum('total'))['t'] or 0)
    orders_today = today_paid.count()
    orders_yesterday = yesterday_paid.count()
    
    # Month-to-date
    mtd_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (mtd_start - timedelta(days=1)).replace(day=1)
    mtd_paid = paid.filter(created_at__gte=mtd_start)
    prev_month_paid = paid.filter(created_at__gte=prev_month_start, created_at__lt=mtd_start)
    
    revenue_mtd = float(mtd_paid.aggregate(t=Sum('total'))['t'] or 0)
    revenue_prev_month = float(prev_month_paid.aggregate(t=Sum('total'))['t'] or 0)
    
    # 30-day metrics (for charts and other KPIs)
    revenue = float(period_paid.aggregate(t=Sum('total'))['t'] or 0)
    prev_revenue = float(prev_paid.aggregate(t=Sum('total'))['t'] or 0)
    orders_count = period_paid.count()
    prev_orders = prev_paid.count()
    avg_order = float(period_paid.aggregate(a=Avg('total'))['a'] or 0)
    prev_avg = float(prev_paid.aggregate(a=Avg('total'))['a'] or 0)
    units_sold = OrderItem.objects.filter(order__in=period_paid).aggregate(t=Sum('quantity'))['t'] or 0
    prev_units = OrderItem.objects.filter(order__in=prev_paid).aggregate(t=Sum('quantity'))['t'] or 0
    pending_count = Order.objects.filter(status=Order.OrderStatus.PENDING).count()
    low_stock_count = Product.objects.filter(stock__gt=0, stock__lte=F('low_stock_threshold')).count()

    # Revenue over time (daily) - check for custom period
    rev_period_days = int(request.GET.get('rev_period', 30))
    rev_start = now - timedelta(days=rev_period_days)
    rev_period_paid = paid.filter(created_at__gte=rev_start)
    
    rev_by_day = list(rev_period_paid.annotate(day=TruncDay('created_at'))
        .values('day').annotate(revenue=Sum('total')).order_by('day'))
    rev_labels = [r['day'].strftime('%d %b') for r in rev_by_day]
    rev_data = [float(r['revenue']) for r in rev_by_day]

    # Order status breakdown
    status_data = {s: Order.objects.filter(created_at__gte=start, status=s).count()
                   for s, _ in Order.OrderStatus.choices}

    # Top 5 products by units
    top_units = list(OrderItem.objects.filter(order__in=period_paid)
        .values('product__name').annotate(units=Sum('quantity')).order_by('-units')[:5])

    # Top 5 products by revenue
    top_rev = list(OrderItem.objects.filter(order__in=period_paid)
        .values('product__name').annotate(revenue=Sum(F('product_price') * F('quantity'))).order_by('-revenue')[:5])

    # Payment methods
    method_data = {m: period_paid.filter(payment_method=m).count()
                   for m in ['MPESA', 'CARD']}

    # New vs returning
    from django.contrib.auth import get_user_model
    User = get_user_model()
    new_customers = User.objects.filter(date_joined__gte=start).count()
    returning = period_paid.filter(user__date_joined__lt=start).values('user').distinct().count()

    # Revenue by county (top 5 + others)
    county_rev = list(period_paid.values('address_county')
        .annotate(
            revenue=Sum('total'),
            orders=Count('id'),
            customers=Count('user', distinct=True)
        ).order_by('-revenue')[:5])
    
    # Calculate "Other" counties
    top_counties = [c['address_county'] for c in county_rev]
    other_orders = period_paid.exclude(address_county__in=top_counties)
    other_revenue = float(other_orders.aggregate(t=Sum('total'))['t'] or 0)
    other_count = other_orders.count()
    
    if other_count > 0:
        county_rev.append({
            'address_county': 'Other',
            'revenue': other_revenue,
            'orders': other_count,
            'customers': 0
        })

    # Cart abandonment
    abandoned_carts = CartItem.objects.values('cart').distinct().exclude(
        cart__user__order__created_at__gte=start
    ).count()

    # Inventory health
    total_products = Product.objects.filter(is_visible=True).count()
    out_of_stock = Product.objects.filter(stock=0, is_visible=True).count()
    low_stock = low_stock_count
    healthy = total_products - out_of_stock - low_stock

    # Cohort retention (last 6 weeks)
    # Cohort retention (configurable weeks)
    cohort_weeks = int(request.GET.get('cohort_weeks', 8))
    cohorts = []
    for i in range(cohort_weeks - 1, -1, -1):
        w_start = now - timedelta(weeks=i+1)
        w_end = now - timedelta(weeks=i)
        cohort_users = list(Order.objects.filter(
            created_at__gte=w_start, created_at__lt=w_end,
            payment_status=Order.PaymentStatus.PAID
        ).values_list('user_id', flat=True).distinct())
        size = len(cohort_users)
        if size and cohort_users[0]:
            w2 = Order.objects.filter(user_id__in=cohort_users, created_at__gte=w_end,
                                      payment_status=Order.PaymentStatus.PAID).values('user_id').distinct().count()
            ret = round(w2 / size * 100) if size else 0
        else:
            ret = 0
        cohorts.append({'week': w_start.strftime('%d %b'), 'size': size, 'w1': ret})

    context = {
        'period': period,
        'revenue_today': revenue_today, 'revenue_today_change': pct_change(revenue_today, revenue_yesterday),
        'revenue_mtd': revenue_mtd, 'revenue_mtd_change': pct_change(revenue_mtd, revenue_prev_month),
        'orders_today': orders_today, 'orders_today_change': pct_change(orders_today, orders_yesterday),
        'revenue': revenue, 'revenue_change': pct_change(revenue, prev_revenue),
        'orders_count': orders_count, 'orders_change': pct_change(orders_count, prev_orders),
        'avg_order': avg_order, 'avg_change': pct_change(avg_order, prev_avg),
        'units_sold': units_sold, 'units_change': pct_change(units_sold, prev_units),
        'pending_count': pending_count,
        'low_stock_count': low_stock_count,
        'rev_labels_json': json.dumps(rev_labels),
        'rev_data_json': json.dumps(rev_data),
        'status_data_json': json.dumps(status_data),
        'top_units_json': json.dumps(top_units),
        'top_rev_json': json.dumps([{'product__name': r['product__name'], 'revenue': float(r['revenue'])} for r in top_rev]),
        'method_data_json': json.dumps(method_data),
        'new_customers': new_customers, 'returning_customers': returning,
        'county_data': county_rev,
        'abandoned_carts': abandoned_carts,
        'inventory': {'total': total_products, 'healthy': healthy, 'low': low_stock, 'out': out_of_stock},
        'cohorts': cohorts,
    }

    return render(request, 'dashboard/analytics.html', context)


def _get_period_bounds(request):
    """Helper: returns (start, end, period_label) from ?period= param."""
    from datetime import timedelta
    now = timezone.now()
    period = request.GET.get('period', '30')
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == '7':
        start = now - timedelta(days=7)
    elif period == '90':
        start = now - timedelta(days=90)
    else:
        period = '30'
        start = now - timedelta(days=30)
    return start, now, period


def _excel_response(filename, headers, rows):
    """Return a StreamingHttpResponse with CSV (Excel-compatible)."""
    import csv
    from django.http import StreamingHttpResponse

    def stream():
        buf = __import__('io').StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        yield buf.getvalue(); buf.seek(0); buf.truncate()
        for row in rows:
            w.writerow(row)
            yield buf.getvalue(); buf.seek(0); buf.truncate()

    resp = StreamingHttpResponse(stream(), content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@dashboard_login_required
def report_revenue(request):
    from apps.orders.models import Order
    from django.db.models import Sum
    from django.db.models.functions import TruncDay
    start, end, period = _get_period_bounds(request)
    rows = (Order.objects.filter(payment_status=Order.PaymentStatus.PAID, created_at__gte=start)
            .annotate(day=TruncDay('created_at'))
            .values('day').annotate(revenue=Sum('total'), orders=__import__('django.db.models', fromlist=['Count']).Count('id'))
            .order_by('day'))
    if request.GET.get('export'):
        return _excel_response('revenue_report.csv', ['Date', 'Orders', 'Revenue (KES)'],
                               [[r['day'].strftime('%Y-%m-%d'), r['orders'], r['revenue']] for r in rows])
    return render(request, 'dashboard/report_revenue.html', {'rows': rows, 'period': period})


@dashboard_login_required
def report_top_products_units(request):
    from apps.orders.models import Order, OrderItem
    from django.db.models import Sum
    start, end, period = _get_period_bounds(request)
    rows = (OrderItem.objects.filter(order__payment_status=Order.PaymentStatus.PAID, order__created_at__gte=start)
            .values('product__name', 'product__sku').annotate(units=Sum('quantity')).order_by('-units'))
    if request.GET.get('export'):
        return _excel_response('top_products_units.csv', ['Product', 'SKU', 'Units Sold'],
                               [[r['product__name'], r['product__sku'], r['units']] for r in rows])
    return render(request, 'dashboard/report_top_products_units.html', {'rows': rows, 'period': period})


@dashboard_login_required
def report_top_products_revenue(request):
    from apps.orders.models import Order, OrderItem
    from django.db.models import Sum, F
    start, end, period = _get_period_bounds(request)
    rows = (OrderItem.objects.filter(order__payment_status=Order.PaymentStatus.PAID, order__created_at__gte=start)
            .values('product__name', 'product__sku')
            .annotate(revenue=Sum(F('product_price') * F('quantity')), units=Sum('quantity'))
            .order_by('-revenue'))
    if request.GET.get('export'):
        return _excel_response('top_products_revenue.csv', ['Product', 'SKU', 'Units Sold', 'Revenue (KES)'],
                               [[r['product__name'], r['product__sku'], r['units'], r['revenue']] for r in rows])
    return render(request, 'dashboard/report_top_products_revenue.html', {'rows': rows, 'period': period})


@dashboard_login_required
def report_top_customers(request):
    from apps.orders.models import Order
    from django.db.models import Sum, Count
    from django.http import JsonResponse
    start, end, period = _get_period_bounds(request)
    rows = (Order.objects.filter(payment_status=Order.PaymentStatus.PAID, created_at__gte=start)
            .values('user__id', 'user__first_name', 'user__last_name', 'user__email')
            .annotate(total_spent=Sum('total'), order_count=Count('id'))
            .order_by('-total_spent'))
    if request.GET.get('export'):
        return _excel_response('top_customers.csv', ['Name', 'Email', 'Orders', 'Total Spent (KES)'],
                               [[f"{r['user__first_name']} {r['user__last_name']}".strip() or r['user__email'],
                                 r['user__email'], r['order_count'], r['total_spent']] for r in rows])
    return render(request, 'dashboard/report_top_customers.html', {'rows': rows, 'period': period})


@dashboard_login_required
def report_revenue_by_county(request):
    from apps.orders.models import Order
    from django.db.models import Sum, Count
    start, end, period = _get_period_bounds(request)
    rows = (Order.objects.filter(payment_status=Order.PaymentStatus.PAID, created_at__gte=start)
            .values('address_county').annotate(revenue=Sum('total'), orders=Count('id')).order_by('-revenue'))
    if request.GET.get('export'):
        return _excel_response('revenue_by_county.csv', ['County', 'Orders', 'Revenue (KES)'],
                               [[r['address_county'] or 'Unknown', r['orders'], r['revenue']] for r in rows])
    return render(request, 'dashboard/report_revenue_by_county.html', {'rows': rows, 'period': period})


@dashboard_login_required
def report_inventory(request):
    from apps.products.models import Product
    from django.db.models import F
    rows = Product.objects.select_related('category').filter(is_visible=True).order_by('stock')
    if request.GET.get('export'):
        return _excel_response('inventory_health.csv', ['Product', 'SKU', 'Category', 'Stock', 'Threshold', 'Status'],
                               [[p.name, p.sku, p.category.name if p.category else '', p.stock, p.low_stock_threshold,
                                 'Out of Stock' if p.stock == 0 else ('Low Stock' if p.stock <= p.low_stock_threshold else 'Healthy')]
                                for p in rows])
    return render(request, 'dashboard/report_inventory.html', {'rows': rows})


@dashboard_login_required
def report_cart_abandonment(request):
    from apps.orders.models import Cart, CartItem, Order
    from django.db.models import Sum, Count
    # Carts with items where the user has no completed order
    abandoned = (CartItem.objects.select_related('cart__user', 'product')
                 .filter(cart__user__isnull=False)
                 .exclude(cart__user__order__payment_status=Order.PaymentStatus.PAID)
                 .values('cart__user__email', 'cart__user__first_name', 'cart__user__last_name')
                 .annotate(items=Count('id'), est_value=Sum('product__base_price'))
                 .order_by('-est_value'))
    if request.GET.get('export'):
        return _excel_response('cart_abandonment.csv', ['Customer', 'Email', 'Items', 'Est. Value (KES)'],
                               [[f"{r['cart__user__first_name']} {r['cart__user__last_name']}".strip(),
                                 r['cart__user__email'], r['items'], r['est_value']] for r in abandoned])
    return render(request, 'dashboard/report_cart_abandonment.html', {'rows': abandoned})


@dashboard_login_required
def report_cohort_retention(request):
    from datetime import timedelta
    from django.utils import timezone
    from apps.orders.models import Order
    
    now = timezone.now()
    cohort_weeks = int(request.GET.get('weeks', 12))
    
    cohorts = []
    for i in range(cohort_weeks - 1, -1, -1):
        w_start = now - timedelta(weeks=i+1)
        w_end = now - timedelta(weeks=i)
        cohort_users = list(Order.objects.filter(
            created_at__gte=w_start, created_at__lt=w_end,
            payment_status=Order.PaymentStatus.PAID
        ).values_list('user_id', flat=True).distinct())
        size = len(cohort_users)
        if size and cohort_users[0]:
            w2 = Order.objects.filter(user_id__in=cohort_users, created_at__gte=w_end,
                                      payment_status=Order.PaymentStatus.PAID).values('user_id').distinct().count()
            ret = round(w2 / size * 100) if size else 0
        else:
            ret = 0
        cohorts.append({'week': w_start.strftime('%d %b'), 'size': size, 'w1': ret})
    
    logger.debug('cohorts count=%d first_few=%s', len(cohorts), cohorts[:3])
    
    return render(request, 'dashboard/report_cohort_retention.html', {
        'cohorts': cohorts,
        'cohort_weeks': cohort_weeks
    })


@dashboard_login_required
def payments_list(request):
    from apps.payments.models import Payment
    from django.core.paginator import Paginator

    qs = Payment.objects.select_related('order', 'order__user').order_by('-created_at')

    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/payments.html', {
        'page_obj': page_obj,
        'status': status,
        'status_choices': Payment.Status.choices,
    })


@dashboard_login_required
def customers_list(request):
    from django.contrib.auth import get_user_model
    from django.db.models import Sum, Count, Q
    User = get_user_model()

    qs = User.objects.annotate(
        order_count=Count('order', distinct=True),
        total_spent=Sum('order__total'),
    ).order_by('-date_joined')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(phone_number__icontains=q))

    status = request.GET.get('status', '')
    if status == 'banned':
        qs = qs.filter(is_banned=True)
    elif status == 'active':
        qs = qs.filter(is_banned=False)

    return render(request, 'dashboard/customers.html', {
        'customers': qs,
        'total_count': qs.count(),
        'q': q,
        'status': status,
    })


@dashboard_login_required
def customer_detail(request, pk):
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum, Count, Avg
    from apps.orders.models import Order
    from apps.dashboard.models import CustomerNote
    User = get_user_model()

    customer = get_object_or_404(User, pk=pk)
    orders = Order.objects.filter(user=customer).order_by('-created_at')
    stats = orders.aggregate(
        total_spent=Sum('total'),
        order_count=Count('id'),
        avg_order=Avg('total'),
    )
    notes = CustomerNote.objects.filter(user=customer)
    last_order = orders.first()

    from django.core.paginator import Paginator
    paginator = Paginator(orders, 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/customer_detail.html', {
        'customer': customer,
        'page_obj': page_obj,
        'total_spent': stats['total_spent'] or 0,
        'order_count': stats['order_count'] or 0,
        'avg_order': stats['avg_order'] or 0,
        'notes': notes,
        'last_order': last_order,
    })


@dashboard_login_required
def customer_ban(request, pk):
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404
    User = get_user_model()
    if request.method == 'POST':
        customer = get_object_or_404(User, pk=pk)
        customer.is_banned = True
        customer.is_active = False
        customer.ban_reason = request.POST.get('reason', '').strip()
        customer.save(update_fields=['is_banned', 'is_active', 'ban_reason'])
    return redirect(f'/dashboard/customers/{pk}/')


@dashboard_login_required
def customer_unban(request, pk):
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404
    User = get_user_model()
    if request.method == 'POST':
        customer = get_object_or_404(User, pk=pk)
        customer.is_banned = False
        customer.is_active = True
        customer.ban_reason = ''
        customer.save(update_fields=['is_banned', 'is_active', 'ban_reason'])
    return redirect(f'/dashboard/customers/{pk}/')


@dashboard_login_required
def customer_delete(request, pk):
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404
    User = get_user_model()
    if request.method == 'POST':
        get_object_or_404(User, pk=pk).delete()
        return redirect('/dashboard/customers/')
    return redirect(f'/dashboard/customers/{pk}/')


@dashboard_login_required
def customer_note_add(request, pk):
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404
    from apps.dashboard.models import CustomerNote
    from django.http import JsonResponse
    User = get_user_model()
    if request.method == 'POST':
        customer = get_object_or_404(User, pk=pk)
        body = request.POST.get('body', '').strip()
        if body:
            note = CustomerNote.objects.create(user=customer, body=body)
            return JsonResponse({'id': note.pk, 'body': note.body, 'created_at': note.created_at.strftime('%d %b %Y, %H:%M')})
    return JsonResponse({'error': 'invalid'}, status=400)


@dashboard_login_required
def categories_list(request):
    from apps.products.models import Category
    from django.db.models import Count
    categories = Category.objects.annotate(product_count=Count('products')).order_by('order', 'name')
    return render(request, 'dashboard/categories.html', {'categories': categories})


@dashboard_login_required
def category_add(request):
    from apps.products.models import Category
    from django.utils.text import slugify
    parents = Category.objects.order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip() or slugify(name)
        description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent') or None
        order = int(request.POST.get('order') or 0)
        # Ensure unique slug
        base = slug
        n = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f'{base}-{n}'; n += 1
        cat = Category.objects.create(name=name, slug=slug, description=description, order=order)
        if parent_id:
            cat.parent_id = int(parent_id)
        if 'image' in request.FILES:
            cat.image = request.FILES['image']
        cat.icon = request.POST.get('icon', '').strip()
        cat.icon_name = request.POST.get('icon_name', 'squares-four').strip() or 'squares-four'
        cat.save()
        return redirect('/dashboard/categories/')
    return render(request, 'dashboard/category_form.html', {'parents': parents, 'category': None})


@dashboard_login_required
def category_edit(request, pk):
    from apps.products.models import Category
    from django.shortcuts import get_object_or_404
    from django.utils.text import slugify
    cat = get_object_or_404(Category, pk=pk)
    parents = Category.objects.exclude(pk=pk).order_by('name')
    if request.method == 'POST':
        cat.name = request.POST.get('name', cat.name).strip()
        new_slug = request.POST.get('slug', '').strip() or slugify(cat.name)
        if new_slug != cat.slug and Category.objects.filter(slug=new_slug).exists():
            new_slug = f'{new_slug}-{pk}'
        cat.slug = new_slug
        cat.description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent') or None
        cat.parent_id = int(parent_id) if parent_id else None
        cat.order = int(request.POST.get('order') or 0)
        if 'image' in request.FILES:
            cat.image = request.FILES['image']
        cat.icon = request.POST.get('icon', '').strip()
        cat.icon_name = request.POST.get('icon_name', 'squares-four').strip() or 'squares-four'
        cat.save()
        return redirect('/dashboard/categories/')
    return render(request, 'dashboard/category_form.html', {'parents': parents, 'category': cat})


@dashboard_login_required
def category_delete(request, pk):
    from apps.products.models import Category
    from django.shortcuts import get_object_or_404
    if request.method == 'POST':
        get_object_or_404(Category, pk=pk).delete()
    return redirect('/dashboard/categories/')


@dashboard_login_required
def orders_list(request):
    from apps.orders.models import Order
    from django.core.paginator import Paginator

    qs = Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')

    status_counts = {s: qs.filter(status=s).count() for s in ['pending', 'processing', 'shipped', 'delivered']}

    kanban_columns = [
        ('pending',    'Pending',    status_counts['pending']),
        ('processing', 'Processing', status_counts['processing']),
        ('shipped',    'Shipped',    status_counts['shipped']),
        ('delivered',  'Delivered',  status_counts['delivered']),
    ]

    paginator = Paginator(qs, 200)
    page_obj = paginator.get_page(1)

    return render(request, 'dashboard/orders.html', {
        'orders': qs,
        'page_obj': page_obj,
        'pending_count': status_counts['pending'],
        'processing_count': status_counts['processing'],
        'kanban_columns': kanban_columns,
    })


@dashboard_login_required
def homepage_editor(request):
    from apps.dashboard.models import HomepageSection, HomepageTemplate, StoreSettings
    from apps.products.models import Product
    from django.db.models import Count, Q
    import json as _json
    from django.core.serializers.json import DjangoJSONEncoder
    def _jdumps(obj): return _json.dumps(obj, cls=DjangoJSONEncoder)
    sections = HomepageSection.objects.order_by('order')
    # Build section visibility map
    section_visibility = {str(s.pk): s.is_visible for s in sections}
    section_visibility_json = _json.dumps(section_visibility)
    settings = StoreSettings.get()
    hero_section = HomepageSection.objects.filter(key='hero').first()
    cat_section = HomepageSection.objects.filter(key='categories').first()
    cat_cc = cat_section.custom_content if cat_section else {}
    cat_saved_variants = cat_cc.get('cat_variants', {})
    featured_categories = settings.featured_categories.annotate(
        product_count=Count('products', filter=Q(products__is_visible=True))
    ).all()
    cat_products_json = _jdumps([
        {'name': c.name, 'slug': c.slug, 'product_count': c.product_count or 0,
         'icon': c.icon, 'icon_name': c.icon_name, 'image_url': c.image.url if c.image else ''}
        for c in featured_categories
    ])
    deal_products = list(Product.objects.filter(is_visible=True, sale_price__isnull=False).prefetch_related('images').values(
        'id', 'name', 'base_price', 'sale_price'
    ).order_by('name')[:50])
    # Add cover image url per product
    from apps.products.models import ProductImage
    cover_map = {pi.product_id: pi.image.url for pi in ProductImage.objects.filter(
        product_id__in=[p['id'] for p in deal_products], is_cover=True
    )}
    for p in deal_products:
        p['cover_image_url'] = cover_map.get(p['id'], '')
        p['effective_price'] = float(p['sale_price'] if p['sale_price'] else p['base_price'])
        p['base_price'] = float(p['base_price'])
        p['sale_price'] = float(p['sale_price']) if p['sale_price'] else None
    
    # All visible products for featured section picker
    all_products = list(Product.objects.filter(is_visible=True).prefetch_related('images').values(
        'id', 'name', 'base_price', 'sale_price'
    ).order_by('name')[:100])
    cover_map_all = {pi.product_id: pi.image.url for pi in ProductImage.objects.filter(
        product_id__in=[p['id'] for p in all_products], is_cover=True
    )}
    for p in all_products:
        p['cover_image_url'] = cover_map_all.get(p['id'], '')
        p['effective_price'] = float(p['sale_price'] if p['sale_price'] else p['base_price'])
        p['base_price'] = float(p['base_price'])
        p['sale_price'] = float(p['sale_price']) if p['sale_price'] else None
    
    # Featured section
    feat_section = HomepageSection.objects.filter(key='featured').first()
    feat_cc = feat_section.custom_content if feat_section else {}
    feat_saved_variants = feat_cc.get('feat_variants', {})
    feat_saved_product_ids = feat_cc.get('product_ids', [])

    # Deals section
    deals_section = HomepageSection.objects.filter(key='deals').first()
    deals_cc = deals_section.custom_content if deals_section else {}
    deals_saved = deals_cc.get('deal_variants', {})

    # Bestsellers section
    bs_section = HomepageSection.objects.filter(key='bestsellers').first()
    bs_cc = (bs_section.custom_content or {}) if bs_section else {}
    bs_defaults = {'heading':'Best Sellers','heading_size':'38px','heading_colour':'--forest','subheading':'','subheading_colour':'--text','subheading_size':'16px','bg_colour':'--surface-alt','product_ids':[]}
    bs_saved = {**bs_defaults, **bs_cc}

    # Story section
    story_section = HomepageSection.objects.filter(key='story').first()
    story_cc = (story_section.custom_content or {}) if story_section else {}
    sv_defaults = {
        'bg_colour':'--surface-alt','overline':'Our Story','overline_colour':'--gold-muted','overline_visible':True,
        'heading':'Bringing you the best in technology, curated for Kenya.',
        'heading_colour':'--forest','heading_size':'36px',
        'body':'We believe great technology shouldn\'t require a trip abroad or guesswork about authenticity.',
        'body_colour':'--text','body_size':'16px',
        'cta_text':'Learn More →','cta_link':'/about/','cta_colour':'--forest','cta_style':'ghost','cta_visible':True,
        'image_url':'','image_visible':True,'image_bg_colour':'--sage',
        'overlay_colour':'--forest','overlay_opacity':40,'image_height':'40vh',
    }
    sv_saved = {
        'sv1': {**sv_defaults, **story_cc.get('sv1', {})},
        'sv2': {**sv_defaults, **story_cc.get('sv2', {})},
        'sv3': {**sv_defaults, **story_cc.get('sv3', {})},
    }
    deal = deal_products[0] if deal_products else None
    saved_cc = (hero_section.custom_content or {}) if hero_section else {}
    saved_deal_ids = saved_cc.get('deal_product_ids', [])
    # Pad to 3 slots
    saved_deal_ids = (saved_deal_ids + [None, None, None])[:3]
    saved_variants = saved_cc.get('variants', {})
    return render(request, 'dashboard/homepage_editor.html', {
        'sections': sections,
        'section_visibility_json': section_visibility_json,
        'templates': HomepageTemplate.objects.order_by('name'),
        'settings': settings,
        'hero_section': hero_section,
        'cat_section': cat_section,
        'cat_cc': cat_cc,
        'cat_products_json': cat_products_json,
        'cat_saved_variants_json': _jdumps(cat_saved_variants),
        'deal': deal,
        'deal_products_json': _jdumps(deal_products),
        'saved_deal_ids_json': _jdumps(saved_deal_ids),
        'saved_overline_colour': saved_cc.get('overline_colour', '--gold'),
        'saved_show_deal_card': _jdumps(saved_cc.get('show_deal_card', True)),
        'saved_show_stats': _jdumps(saved_cc.get('show_stats', True)),
        'saved_variants_json': _jdumps(saved_variants),
        'featured_categories': featured_categories,
        'feat_section': feat_section,
        'feat_products_json': _jdumps(all_products),
        'feat_saved_variants_json': _jdumps(feat_saved_variants),
        'feat_saved_product_ids_json': _jdumps(feat_saved_product_ids),
        'deals_section': deals_section,
        'deals_products_json': _jdumps(deal_products),
        'deals_saved_json': _jdumps(deals_saved),
        'bs_section': bs_section,
        'bs_products_json': _jdumps(all_products),
        'bs_saved_json': _jdumps(bs_saved),
        'story_section': story_section,
        'sv_saved_json': _jdumps(sv_saved),
        'footer_shop_links_json': _jdumps(settings.footer_shop_links or []),
        'footer_help_links_json': _jdumps(settings.footer_help_links or []),
    })


@dashboard_login_required
def homepage_hero_content_save(request):
    """Save hero text fields directly to StoreSettings."""
    from apps.dashboard.models import StoreSettings
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    settings = StoreSettings.get()
    # Only fields that actually exist on StoreSettings
    fields = [
        'hero_overline', 'hero_headline', 'hero_subheading',
        'hero_cta1_text', 'hero_cta1_link', 'hero_cta2_text', 'hero_cta2_link',
    ]
    changed = []
    for field in fields:
        val = request.POST.get(field)
        if val is not None and hasattr(settings, field):
            setattr(settings, field, val)
            changed.append(field)
    if changed:
        settings.save(update_fields=changed)
    logger.info('dashboard.homepage.hero_content_save', extra={'user_id': request.user.id})
    return JsonResponse({'status': 'ok'})


@dashboard_login_required
def homepage_section_save(request, pk):
    from apps.dashboard.models import HomepageSection
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        section = HomepageSection.objects.get(pk=pk)
    except HomepageSection.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)

    data = request.POST

    # Layout
    variant = data.get('variant', section.variant)
    if variant in ('1', '2', '3', '4', '5', '6'):
        section.variant = variant

    # Visibility
    if 'is_visible' in data:
        section.is_visible = data['is_visible'] == 'true'

    # Background
    bg_mode = data.get('bg_mode')
    if bg_mode in ('colour', 'image', 'image_overlay'):
        section.bg_mode = bg_mode
    bg_colour = data.get('bg_colour')
    valid_colours = [c[0] for c in HomepageSection.PALETTE_CHOICES]
    if bg_colour in valid_colours:
        section.bg_colour = bg_colour
    bg_image_pos = data.get('bg_image_pos')
    if bg_image_pos in [c[0] for c in HomepageSection.IMG_POSITION_CHOICES]:
        section.bg_image_pos = bg_image_pos
    bg_overlay_colour = data.get('bg_overlay_colour')
    if bg_overlay_colour in valid_colours:
        section.bg_overlay_colour = bg_overlay_colour
    try:
        opacity = int(data.get('bg_overlay_opacity', section.bg_overlay_opacity))
        if 0 <= opacity <= 90:
            section.bg_overlay_opacity = opacity
    except (ValueError, TypeError):
        pass

    # Background image upload
    if 'bg_image' in request.FILES:
        section.bg_image = request.FILES['bg_image']

    # Spacing
    spacing = data.get('spacing')
    if spacing in ('sm', 'md', 'lg', 'xl'):
        section.spacing = spacing

    # Typography
    for field, choices in (
        ('heading_colour', valid_colours),
        ('heading_size', [c[0] for c in HomepageSection.HEADING_SIZE_CHOICES]),
        ('heading_weight', [c[0] for c in HomepageSection.WEIGHT_CHOICES]),
        ('body_colour', valid_colours),
        ('body_size', [c[0] for c in HomepageSection.BODY_SIZE_CHOICES]),
        ('body_weight', [c[0] for c in HomepageSection.WEIGHT_CHOICES]),
    ):
        val = data.get(field)
        if val in choices:
            setattr(section, field, val)

    # Buttons
    btn1_style = data.get('btn1_style')
    if btn1_style in ('filled', 'outline', 'ghost'):
        section.btn1_style = btn1_style
    btn1_colour = data.get('btn1_colour')
    if btn1_colour in valid_colours:
        section.btn1_colour = btn1_colour
    if 'btn1_enabled' in data:
        section.btn1_enabled = data['btn1_enabled'] == 'true'
    btn2_style = data.get('btn2_style')
    if btn2_style in ('filled', 'outline', 'ghost'):
        section.btn2_style = btn2_style
    btn2_colour = data.get('btn2_colour')
    if btn2_colour in valid_colours:
        section.btn2_colour = btn2_colour
    if 'btn2_enabled' in data:
        section.btn2_enabled = data['btn2_enabled'] == 'true'

    # Custom content (JSON)
    custom_content_raw = data.get('custom_content')
    if custom_content_raw:
        try:
            import json as _json
            section.custom_content = _json.loads(custom_content_raw)
            # Log category section saves
            if section.key == 'categories':
                logger.info(f'[CATEGORY SAVE] Variant: {section.variant}, Custom content: {section.custom_content}')
        except ValueError:
            pass

    # Inline image
    if 'inline_image' in request.FILES:
        section.inline_image = request.FILES['inline_image']
    inline_image_pos = data.get('inline_image_pos')
    if inline_image_pos in ('left', 'right'):
        section.inline_image_pos = inline_image_pos

    section.save()
    logger.info('dashboard.homepage.section_save', extra={'user_id': request.user.id, 'section_id': pk})
    return JsonResponse({'status': 'ok', 'section_id': section.pk})


@dashboard_login_required
def upload_category_image(request):
    from django.http import JsonResponse
    from django.core.files.storage import default_storage
    from apps.dashboard.utils import validate_and_rename_image

    if request.method != 'POST' or 'image' not in request.FILES:
        return JsonResponse({'error': 'Invalid request'}, status=400)

    image = request.FILES['image']
    try:
        safe_name = validate_and_rename_image(image)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    filename = default_storage.save(f'categories/{safe_name}', image)
    return JsonResponse({'url': default_storage.url(filename)})


@dashboard_login_required
def upload_story_image(request):
    from django.http import JsonResponse
    from django.core.files.storage import default_storage
    from apps.dashboard.utils import validate_and_rename_image

    if request.method != 'POST' or 'image' not in request.FILES:
        return JsonResponse({'error': 'Invalid request'}, status=400)

    image = request.FILES['image']
    try:
        safe_name = validate_and_rename_image(image)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    filename = default_storage.save(f'story/{safe_name}', image)
    return JsonResponse({'url': default_storage.url(filename)})


@dashboard_login_required
def homepage_section_add(request):
    from apps.dashboard.models import HomepageSection
    from django.http import JsonResponse
    import json as _json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    # Max 10 custom sections
    custom_count = HomepageSection.objects.filter(is_core=False).count()
    if custom_count >= 10:
        return JsonResponse({'error': 'Section limit reached (10/10)'}, status=400)

    try:
        data = _json.loads(request.body)
    except ValueError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)

    key = data.get('key', '')
    valid_keys = [k[0] for k in HomepageSection.SECTION_KEYS if k[0].startswith('custom_')]
    if key not in valid_keys:
        return JsonResponse({'error': 'invalid key'}, status=400)

    # Disallow custom_html for non-staff (already staff-only here, but double-check)
    if key == 'custom_html' and not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)

    label = data.get('label', dict(HomepageSection.SECTION_KEYS).get(key, key))
    max_order = HomepageSection.objects.order_by('-order').values_list('order', flat=True).first() or 0
    section = HomepageSection.objects.create(
        key=key,
        label=label,
        order=max_order + 1,
        is_core=False,
        is_visible=True,
    )
    logger.info('dashboard.homepage.section_add', extra={'user_id': request.user.id, 'section_id': section.pk, 'key': key})
    return JsonResponse({'status': 'ok', 'section_id': section.pk})


@dashboard_login_required
def homepage_section_delete(request, pk):
    from apps.dashboard.models import HomepageSection
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        section = HomepageSection.objects.get(pk=pk, is_core=False)
    except HomepageSection.DoesNotExist:
        return JsonResponse({'error': 'not found or core section'}, status=404)

    section.delete()
    logger.info('dashboard.homepage.section_delete', extra={'user_id': request.user.id, 'section_id': pk})
    return JsonResponse({'status': 'ok'})


@dashboard_login_required
def homepage_section_reorder(request):
    from apps.dashboard.models import HomepageSection
    from django.http import JsonResponse
    import json as _json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = _json.loads(request.body)
        order = [int(i) for i in data.get('order', [])]
    except (ValueError, TypeError):
        return JsonResponse({'error': 'invalid data'}, status=400)

    from django.db import transaction
    with transaction.atomic():
        for idx, section_id in enumerate(order):
            HomepageSection.objects.filter(pk=section_id).update(order=idx)

    logger.info('dashboard.homepage.reorder', extra={'user_id': request.user.id})
    return JsonResponse({'status': 'ok'})


@dashboard_login_required
def homepage_template_save(request):
    from apps.dashboard.models import HomepageSection, HomepageTemplate
    from django.http import JsonResponse
    import json as _json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = _json.loads(request.body)
    except ValueError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'name required'}, status=400)

    from django.core import serializers
    snapshot = _json.loads(serializers.serialize('json', HomepageSection.objects.order_by('order')))
    template = HomepageTemplate.objects.create(name=name, snapshot=snapshot)
    logger.info('dashboard.homepage.template_save', extra={'user_id': request.user.id, 'template_id': template.pk})
    return JsonResponse({'status': 'ok', 'template_id': template.pk})


@dashboard_login_required
def homepage_template_load(request, pk):
    from apps.dashboard.models import HomepageSection, HomepageTemplate
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        tmpl = HomepageTemplate.objects.get(pk=pk)
    except HomepageTemplate.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)

    from django.db import transaction
    with transaction.atomic():
        # Only restore core sections from snapshot; preserve custom sections
        core_keys = [k[0] for k in HomepageSection.SECTION_KEYS if not k[0].startswith('custom_')]
        for item in tmpl.snapshot:
            fields = item.get('fields', {})
            key = fields.get('key', '')
            if key not in core_keys:
                continue
            HomepageSection.objects.filter(key=key).update(**{
                k: v for k, v in fields.items()
                if k not in ('bg_image', 'inline_image')  # skip file fields
            })

    logger.info('dashboard.homepage.template_load', extra={'user_id': request.user.id, 'template_id': pk})
    return JsonResponse({'status': 'ok'})


@dashboard_login_required
def footer_settings_save(request):
    from apps.dashboard.models import StoreSettings
    from django.http import JsonResponse
    import json as _json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    settings = StoreSettings.get()
    data = request.POST

    simple_fields = [
        'store_name', 'footer_tagline',
        'footer_ig_url', 'footer_tiktok_url', 'footer_x_url',
        'footer_privacy_url', 'footer_terms_url',
    ]
    changed = [f for f in simple_fields if data.get(f) is not None]
    for f in changed:
        setattr(settings, f, data[f])

    if 'nav_categories_visible' in data:
        settings.nav_categories_visible = data['nav_categories_visible'] == 'true'
        changed.append('nav_categories_visible')

    for json_field in ('footer_shop_links', 'footer_help_links'):
        raw = data.get(json_field)
        if raw:
            try:
                setattr(settings, json_field, _json.loads(raw))
                changed.append(json_field)
            except ValueError:
                pass

    if changed:
        settings.save(update_fields=changed)

    return JsonResponse({'status': 'ok'})
