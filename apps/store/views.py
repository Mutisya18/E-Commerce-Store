import logging
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Sum, Avg, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from apps.core.middleware import get_client_ip
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone

from apps.products.models import Product, Category, Review
from apps.dashboard.models import StoreSettings, HomepageSection
from apps.store.models import Testimonial, NewsletterSubscriber
from apps.core.logging import log_step

logger = logging.getLogger(__name__)


def home_view(request):
    settings = StoreSettings.get()
    now = timezone.now()

    featured = (Product.objects
                .filter(is_visible=True, is_featured=True)
                .prefetch_related('images')
                .select_related('category')[:8])

    deals = (Product.objects
             .filter(is_visible=True, sale_price__isnull=False)
             .prefetch_related('images')
             .distinct()[:8])

    best_sellers = (Product.objects
                    .filter(is_visible=True)
                    .annotate(total_sold=Sum('orderitem__quantity'))
                    .order_by('-total_sold')
                    .prefetch_related('images')[:8])

    from django.db.models import Count
    featured_cats = settings.featured_categories.annotate(
        product_count=Count('products', filter=Q(products__is_visible=True))
    ).all()
    testimonials = Testimonial.objects.filter(is_visible=True).order_by('order')[:3]

    sections = HomepageSection.objects.filter(is_visible=True).order_by('order')

    # Bestsellers section custom content
    _bs_section = sections.filter(key='bestsellers').first()
    _bs_cc = (_bs_section.custom_content or {}) if _bs_section else {}
    _bs_ids = _bs_cc.get('product_ids', [])
    if _bs_ids:
        _bs_qs = Product.objects.filter(pk__in=_bs_ids, is_visible=True).prefetch_related('images')
        best_sellers = sorted(_bs_qs, key=lambda p: _bs_ids.index(p.pk))

    # Story section custom content
    _story_section = sections.filter(key='story').first()
    _story_cc = (_story_section.custom_content or {}) if _story_section else {}
    _story_variant = (_story_section.variant if _story_section else '1')
    _sv_defaults = {
        'bg_colour':'--surface-alt','overline':'Our Story','overline_colour':'--gold-muted','overline_visible':True,
        'heading':'Bringing you the best in technology, curated for Kenya.',
        'heading_colour':'--forest','heading_size':'36px',
        'body':'We believe great technology shouldn\'t require a trip abroad or guesswork about authenticity.',
        'body_colour':'--text','body_size':'16px',
        'cta_text':'Learn More →','cta_link':'/about/','cta_colour':'--forest','cta_style':'ghost','cta_visible':True,
        'image_url':'','image_visible':True,'image_bg_colour':'--sage',
        'overlay_colour':'--forest','overlay_opacity':40,'image_height':'40vh',
    }
    _sv = {**_sv_defaults, **_story_cc.get('sv'+_story_variant, _story_cc)}
    logger.info(f'[STORY] variant={_story_variant} bg={_sv.get("bg_colour")} heading_colour={_sv.get("heading_colour")} image_url={_sv.get("image_url","")[:40]}')

    # Hero deal products — use saved IDs if set, else fall back to first sale product
    hero_section = sections.filter(key='hero').first()
    saved_cc = (hero_section.custom_content or {}) if hero_section else {}
    hero_deal_ids = saved_cc.get('deal_product_ids', [])
    if hero_deal_ids:
        # Preserve order of selected IDs
        hero_deals_qs = Product.objects.filter(pk__in=hero_deal_ids, is_visible=True).prefetch_related('images')
        hero_deals = sorted(hero_deals_qs, key=lambda p: hero_deal_ids.index(p.pk))
    else:
        first_deal = Product.objects.filter(is_visible=True, sale_price__isnull=False).prefetch_related('images').first()
        hero_deals = [first_deal] if first_deal else []

    cat_section = sections.filter(key='categories').first()
    cat_cc = (cat_section.custom_content or {}) if cat_section else {}
    _cat_variant_key = 'cv' + (cat_section.variant if cat_section else '1')
    _cat_cv = cat_cc.get('cat_variants', {}).get(_cat_variant_key, {})
    
    # Log what we're fetching
    logger.info(f'[CATEGORY FETCH] Variant: {cat_section.variant if cat_section else "none"}, Key: {_cat_variant_key}, Data: {_cat_cv}')
    
    # Process category colors for template
    cat_colors = _cat_cv.get('category_colors', [])
    default_colors = [
        {'bg': '--forest', 'text': '--surface', 'icon': '--gold'},
        {'bg': '--sage',   'text': '--forest',  'icon': '--gold'},
        {'bg': '--gold',   'text': '--forest',  'icon': '--forest'},
        {'bg': '--forest', 'text': '--surface', 'icon': '--gold'},
        {'bg': '--sage',   'text': '--forest',  'icon': '--gold'},
        {'bg': '--gold',   'text': '--forest',  'icon': '--forest'},
    ]
    cat_colors_list = cat_colors if cat_colors is not None and len(cat_colors) > 0 else default_colors
    
    # Attach colors to categories
    featured_cats_with_colors = []
    visible_cats = _cat_cv.get('visible_categories', [0,1,2,3,4,5])
    
    # Get category_settings for variant B
    cat_settings = _cat_cv.get('category_settings', [])
    
    if featured_cats:
        for idx, cat in enumerate(featured_cats):
            if idx in visible_cats:
                colors = cat_colors_list[idx] if idx < len(cat_colors_list) else default_colors[idx % 6]
                cat_setting = cat_settings[idx] if idx < len(cat_settings) else {}
                cat_dict = {
                    'id': cat.id,
                    'name': cat.name,
                    'slug': cat.slug,
                    'image': cat.image,
                    'icon': cat.icon,
                    'icon_name': cat.icon_name,
                    'product_count': cat.product_count,
                    'border_color': colors.get('bg', '--forest'),
                    'text_color': colors.get('text', '--surface'),
                    'icon_color': colors.get('icon', '--gold'),
                    # Variant B settings
                    'bg_image': cat_setting.get('bg_image'),
                    'bg_color': cat_setting.get('bg_color', '--forest'),
                    'overlay_color': cat_setting.get('overlay_color', '--forest'),
                    'overlay_opacity': cat_setting.get('overlay_opacity', 65),
                    'settings_text_color': cat_setting.get('text_color', '--surface'),
                }
                featured_cats_with_colors.append(cat_dict)

    # Deals section — use saved product IDs if set
    deals_section_obj = sections.filter(key='deals').first()
    deals_cc_store = (deals_section_obj.custom_content or {}) if deals_section_obj else {}
    _deals_variant_key = 'dv' + (deals_section_obj.variant if deals_section_obj else '1')
    _deals_cv = deals_cc_store.get('deal_variants', {}).get(_deals_variant_key, {})
    deals_product_ids = _deals_cv.get('product_ids', [])
    if deals_product_ids:
        _deals_qs = Product.objects.filter(pk__in=deals_product_ids, is_visible=True, sale_price__isnull=False).prefetch_related('images').select_related('category')
        deals_list = sorted(_deals_qs, key=lambda p: deals_product_ids.index(p.pk) if p.pk in deals_product_ids else 999)
    else:
        deals_list = list(deals)

    # Featured products section
    feat_section = sections.filter(key='featured').first()
    feat_cc = (feat_section.custom_content or {}) if feat_section else {}
    _feat_variant_key = 'fv' + (feat_section.variant if feat_section else '1')
    _feat_cv = feat_cc.get('feat_variants', {}).get(_feat_variant_key, {})
    feat_product_ids = _feat_cv.get('product_ids') or feat_cc.get('product_ids', [])
    feat_hero_id = _feat_cv.get('hero_product_id')
    all_feat_ids = list(dict.fromkeys(([feat_hero_id] if feat_hero_id else []) + feat_product_ids))
    if all_feat_ids:
        _feat_qs = Product.objects.filter(pk__in=all_feat_ids, is_visible=True).prefetch_related('images').select_related('category')
        feat_products_list = sorted(_feat_qs, key=lambda p: all_feat_ids.index(p.pk) if p.pk in all_feat_ids else 999)
    else:
        feat_products_list = list(featured)
    # Reorder so hero product is first if explicitly set
    if feat_hero_id and feat_products_list:
        hero = next((p for p in feat_products_list if p.pk == feat_hero_id), None)
        if hero:
            feat_products_list = [hero] + [p for p in feat_products_list if p.pk != feat_hero_id]  # fallback to is_featured products

    return render(request, 'store/home.html', {
        'settings': settings,
        'sections': sections,
        'featured_products': featured,
        'deals': deals_list,
        'deals_heading': _deals_cv.get('heading', "Today's Deals"),
        'deals_heading_size': _deals_cv.get('heading_size', '38px'),
        'deals_heading_colour': _deals_cv.get('heading_colour', '--surface'),
        'deals_subheading': _deals_cv.get('subheading', ''),
        'deals_subheading_colour': _deals_cv.get('subheading_colour', '--surface'),
        'deals_subheading_size': _deals_cv.get('subheading_size', '16px'),
        'deals_view_all_link': _deals_cv.get('view_all_link', '/products/?sale=1'),
        'deals_view_all_colour': _deals_cv.get('view_all_colour', '--surface'),
        'deals_banner_bg': _deals_cv.get('banner_bg', '--gold'),
        'deals_banner_text': _deals_cv.get('banner_text', '--surface'),
        'deals_banner_label': _deals_cv.get('banner_label', '🔥 Flash Sale ends in:'),
        'deals_banner_label_size': _deals_cv.get('banner_label_size', '16px'),
        'deals_banner_label_visible': _deals_cv.get('banner_label_visible', True),
        'deals_timer_end': _deals_cv.get('timer_end', ''),
        'deals_timer_size': _deals_cv.get('timer_size', '32px'),
        'deals_timer_visible': _deals_cv.get('timer_visible', True),
        'deals_timer_position': _deals_cv.get('timer_position', 'banner'),
        'deals_timer_align': _deals_cv.get('timer_align', 'right'),
        'hero_deals': hero_deals,
        'hero_show_deal_card': saved_cc.get('show_deal_card', True),
        'hero_show_stats': saved_cc.get('show_stats', True),
        'hero_overline_colour': saved_cc.get('overline_colour', '--gold'),
        'best_sellers': best_sellers,
        'bs_heading': _bs_cc.get('heading', 'Best Sellers'),
        'bs_heading_size': _bs_cc.get('heading_size', '38px'),
        'bs_heading_colour': _bs_cc.get('heading_colour', '--forest'),
        'bs_subheading': _bs_cc.get('subheading', ''),
        'bs_subheading_size': _bs_cc.get('subheading_size', '16px'),
        'bs_subheading_colour': _bs_cc.get('subheading_colour', '--text'),
        'bs_bg_colour': _bs_cc.get('bg_colour', '--surface'),
        'story_overline': _sv.get('overline', 'Our Story'),
        'story_overline_colour': _sv.get('overline_colour', '--gold-muted'),
        'story_overline_visible': _sv.get('overline_visible', True),
        'story_heading': _sv.get('heading', 'Bringing you the best in technology, curated for Kenya.'),
        'story_heading_colour': _sv.get('heading_colour', '--forest'),
        'story_heading_size': _sv.get('heading_size', '36px'),
        'story_body': _sv.get('body', 'We believe great technology shouldn\'t require a trip abroad or guesswork about authenticity.'),
        'story_body_colour': _sv.get('body_colour', '--text'),
        'story_body_size': _sv.get('body_size', '16px'),
        'story_cta_text': _sv.get('cta_text', 'Learn More →'),
        'story_cta_link': _sv.get('cta_link', '/about/'),
        'story_cta_colour': _sv.get('cta_colour', '--forest'),
        'story_cta_style': _sv.get('cta_style', 'ghost'),
        'story_cta_visible': _sv.get('cta_visible', True),
        'story_image_url': _sv.get('image_url', ''),
        'story_image_visible': _sv.get('image_visible', True),
        'story_image_bg_colour': _sv.get('image_bg_colour', '--surface-alt'),
        'story_overlay_colour': _sv.get('overlay_colour', '--forest'),
        'story_overlay_opacity': _sv.get('overlay_opacity', 40),
        'story_image_height': _sv.get('image_height', '40vh'),
        'story_bg_colour': _sv.get('bg_colour', '--surface'),
        'featured_categories': featured_cats_with_colors,
        'testimonials': testimonials,
        'cat_overline': _cat_cv.get('overline', 'Explore'),
        'cat_heading': _cat_cv.get('heading', 'Shop by Category'),
        'cat_heading_size': _cat_cv.get('heading_size', '38px'),
        'cat_heading_colour': _cat_cv.get('heading_colour', '--forest'),
        'cat_overline_colour': _cat_cv.get('overline_colour', '--gold-muted'),
        'cat_visible_categories': _cat_cv.get('visible_categories', [0,1,2,3,4,5]),
        'cat_default_colors': cat_colors_list,  # For fallback rendering
        'feat_products': feat_products_list,
        'feat_overline': _feat_cv.get('overline', 'Handpicked'),
        'feat_heading': _feat_cv.get('heading', 'Featured Products'),
        'feat_heading_size': _feat_cv.get('heading_size', '38px'),
        'feat_heading_colour': _feat_cv.get('heading_colour', '--forest'),
        'feat_overline_colour': _feat_cv.get('overline_colour', '--gold-muted'),
        'feat_subheading': _feat_cv.get('subheading', ''),
        'feat_subheading_colour': _feat_cv.get('subheading_colour', '--text'),
        'feat_view_all_link': _feat_cv.get('view_all_link', '/products/'),
        'feat_view_all_colour': _feat_cv.get('view_all_colour', '--forest'),
    })


def _apply_filters(qs, params):
    q = params.get('q', '').strip()
    category = params.get('category', '').strip()
    min_price = params.get('min_price', '').strip()
    max_price = params.get('max_price', '').strip()
    in_stock = params.get('in_stock', '')
    sort = params.get('sort', 'newest')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category__slug=category)
    if min_price:
        try:
            qs = qs.filter(base_price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            qs = qs.filter(base_price__lte=float(max_price))
        except ValueError:
            pass
    if in_stock == '1':
        qs = qs.filter(stock__gt=0)

    sort_map = {
        'price_asc': 'base_price',
        'price_desc': '-base_price',
        'newest': '-created_at',
        'rating': '-avg_rating',
    }
    if sort == 'rating':
        qs = qs.annotate(avg_rating=Avg('reviews__rating'))
    qs = qs.order_by(sort_map.get(sort, '-created_at'))
    return qs


def listing_view(request):
    qs = (Product.objects
          .filter(is_visible=True)
          .select_related('category')
          .prefetch_related('images'))

    qs = _apply_filters(qs, request.GET)
    categories = Category.objects.filter(parent=None).order_by('order')
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get('page'))

    active_filters = {k: v for k, v in request.GET.items() if v and k != 'page'}

    return render(request, 'store/listing.html', {
        'page_obj': page,
        'categories': categories,
        'active_filters': active_filters,
        'total_count': paginator.count,
    })


def category_view(request, slug):
    category = get_object_or_404(Category, slug=slug)
    qs = (Product.objects
          .filter(is_visible=True, category=category)
          .select_related('category')
          .prefetch_related('images'))
    qs = _apply_filters(qs, request.GET)
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'store/listing.html', {
        'page_obj': page,
        'category': category,
        'categories': Category.objects.filter(parent=None).order_by('order'),
        'active_filters': {k: v for k, v in request.GET.items() if v and k != 'page'},
        'total_count': paginator.count,
    })


@ensure_csrf_cookie
def product_detail_view(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related('images', 'reviews__user').select_related('category'),
        slug=slug, is_visible=True
    )

    log_step('browse', 'product_opened', request, product_id=product.id, slug=slug)

    user_can_review = False
    user_has_reviewed = False
    if request.user.is_authenticated:
        from apps.orders.models import OrderItem
        user_can_review = OrderItem.objects.filter(
            order__user=request.user, product=product
        ).exists()
        user_has_reviewed = product.reviews.filter(user=request.user).exists()

    spec_rows = []
    if product.specs:
        for line in product.specs.splitlines():
            if ':' in line:
                key, _, value = line.partition(':')
                spec_rows.append((key.strip(), value.strip()))

    return render(request, 'store/product_detail.html', {
        'product': product,
        'reviews': product.reviews.select_related('user').order_by('-created_at'),
        'user_can_review': user_can_review and not user_has_reviewed,
        'spec_rows': spec_rows,
        'savings': (product.base_price - product.sale_price) if product.sale_price else None,
    })


@require_POST
@ratelimit(key=get_client_ip, rate='5/m', method='POST', block=True)
def newsletter_subscribe(request):
    email = request.POST.get('email', '').strip().lower()
    if not email or '@' not in email:
        return JsonResponse({'ok': False, 'error': 'Invalid email'})
    _, created = NewsletterSubscriber.objects.get_or_create(email=email)
    if not created:
        return JsonResponse({'ok': False, 'error': 'Already subscribed'})
    logger.info('newsletter.subscribe', extra={'email': email})
    return JsonResponse({'ok': True})


@require_POST
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)
def review_submit(request, slug):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required'}, status=401)

    product = get_object_or_404(Product, slug=slug, is_visible=True)

    from apps.orders.models import OrderItem
    if not OrderItem.objects.filter(order__user=request.user, product=product).exists():
        return JsonResponse({'ok': False, 'error': 'Purchase required'}, status=403)

    rating = int(request.POST.get('rating', 0))
    body = request.POST.get('body', '').strip()
    # Strip all HTML — store plain text only
    import html, re
    body = re.sub(r'<[^>]+>', '', html.unescape(body)).strip()

    if not (1 <= rating <= 5) or not body:
        return JsonResponse({'ok': False, 'error': 'Rating and review text are required'}, status=400)

    Review.objects.update_or_create(
        product=product, user=request.user,
        defaults={'rating': rating, 'body': body},
    )
    from django.db.models import Avg
    avg = product.reviews.aggregate(avg=Avg('rating'))['avg']
    return JsonResponse({
        'ok': True,
        'review': {
            'name': request.user.get_full_name() or request.user.email,
            'initials': (request.user.first_name[:1] + request.user.last_name[:1]).upper() or request.user.email[:2].upper(),
            'rating': rating,
            'body': body,
            'date': 'Just now',
        },
        'avg': round(avg, 1),
        'count': product.reviews.count(),
    })
