from django.db import models
from django.conf import settings


class StoreSettings(models.Model):
    """Singleton — always use pk=1."""
    store_name = models.CharField(max_length=200, default='Mutisya')
    store_tagline = models.CharField(max_length=300, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    physical_address = models.TextField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    delivery_timeframe = models.CharField(max_length=100, default='2-4 business days')
    notif_email = models.EmailField(blank=True)
    notif_new_order = models.BooleanField(default=True)
    notif_out_of_stock = models.BooleanField(default=True)
    notif_low_stock = models.BooleanField(default=True)
    notif_payment_failure = models.BooleanField(default=True)
    notif_refund_outcome = models.BooleanField(default=True)
    logo = models.ImageField(upload_to='store/', null=True, blank=True)
    # Hero
    hero_headline = models.CharField(max_length=80, default='Tech That Moves With You.')
    hero_subheading = models.CharField(max_length=300, blank=True)
    hero_overline = models.CharField(max_length=200, blank=True)
    hero_cta1_text = models.CharField(max_length=100, default='Shop Now')
    hero_cta1_link = models.CharField(max_length=200, default='/products/')
    hero_cta2_text = models.CharField(max_length=100, blank=True)
    hero_cta2_link = models.CharField(max_length=200, blank=True)
    hero_image = models.ImageField(upload_to='store/', null=True, blank=True)
    # Story
    story_heading = models.CharField(max_length=120, blank=True)
    story_text = models.TextField(blank=True)
    story_cta_text = models.CharField(max_length=100, blank=True)
    story_cta_link = models.CharField(max_length=200, blank=True)
    story_image = models.ImageField(upload_to='store/', null=True, blank=True)
    # Featured categories (M2M — set after Category model exists)
    featured_categories = models.ManyToManyField('products.Category', blank=True)
    # Section visibility toggles
    section_hero_visible = models.BooleanField(default=True)
    section_categories_visible = models.BooleanField(default=True)
    section_featured_visible = models.BooleanField(default=True)
    section_deals_visible = models.BooleanField(default=True)
    section_bestsellers_visible = models.BooleanField(default=True)
    section_story_visible = models.BooleanField(default=True)
    section_testimonials_visible = models.BooleanField(default=True)
    section_newsletter_visible = models.BooleanField(default=True)
    # Section headings
    section_heading_featured = models.CharField(max_length=100, default='Featured Products')
    section_subheading_featured = models.CharField(max_length=200, blank=True)
    section_heading_deals = models.CharField(max_length=100, default="Today's Deals")
    section_heading_bestsellers = models.CharField(max_length=100, default='Best Sellers')
    section_subheading_bestsellers = models.CharField(max_length=200, blank=True)
    section_heading_newsletter = models.CharField(max_length=100, default='Stay in the Loop')
    section_subheading_newsletter = models.CharField(max_length=200, blank=True)
    section_newsletter_fine = models.CharField(max_length=200, blank=True)
    # Footer
    footer_tagline = models.CharField(max_length=200, blank=True)
    footer_ig_url = models.URLField(blank=True)
    footer_tiktok_url = models.URLField(blank=True)
    footer_x_url = models.URLField(blank=True)
    footer_privacy_url = models.CharField(max_length=200, blank=True)
    footer_terms_url = models.CharField(max_length=200, blank=True)
    footer_shop_links = models.JSONField(default=list, blank=True)
    footer_help_links = models.JSONField(default=list, blank=True)
    nav_categories_visible = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Store Settings'
        verbose_name_plural = 'Store Settings'

    def __str__(self):
        return self.store_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DashboardNotification(models.Model):
    class Type(models.TextChoices):
        NEW_ORDER = 'new_order', 'New Order'
        LOW_STOCK = 'low_stock', 'Low Stock'
        OUT_OF_STOCK = 'out_of_stock', 'Out of Stock'
        PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
        REFUND_SUCCESS = 'refund_success', 'Refund Success'
        REFUND_FAILED = 'refund_failed', 'Refund Failed'

    type = models.CharField(max_length=30, choices=Type.choices)
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.type}: {self.message[:60]}'


class CustomerNote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owner_notes')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Note on {self.user.email}'


class HomepageSection(models.Model):
    SECTION_KEYS = [
        ('hero',          'Hero Banner'),
        ('categories',    'Category Tiles'),
        ('featured',      'Featured Products'),
        ('deals',         'Deals / Flash Sales'),
        ('bestsellers',   'Best Sellers'),
        ('story',         'Brand Story'),
        ('testimonials',  'Testimonials'),
        ('newsletter',    'Newsletter Signup'),
        ('custom_promo',        'Promo Banner'),
        ('custom_image_text',   'Image + Text'),
        ('custom_video',        'Video Embed'),
        ('custom_faq',          'FAQ'),
        ('custom_spotlight',    'Product Spotlight'),
        ('custom_countdown',    'Countdown Timer'),
        ('custom_richtext',     'Rich Text'),
        ('custom_html',         'Custom HTML'),
    ]
    VARIANT_CHOICES   = [('1', 'Variant 1'), ('2', 'Variant 2'), ('3', 'Variant 3'), ('4', 'Variant 4'), ('5', 'Variant 5'), ('6', 'Variant 6')]
    SPACING_CHOICES   = [('sm', 'Small'), ('md', 'Medium'), ('lg', 'Large'), ('xl', 'Extra Large')]
    BG_MODE_CHOICES   = [('colour', 'Colour'), ('image', 'Image'), ('image_overlay', 'Image + Overlay')]
    BTN_STYLE_CHOICES = [('filled', 'Filled'), ('outline', 'Outline'), ('ghost', 'Ghost')]
    PALETTE_CHOICES   = [
        ('--forest',      'Forest'),
        ('--gold',        'Gold'),
        ('--gold-muted',  'Gold Muted'),
        ('--sage',        'Sage'),
        ('--base',        'Parchment'),
        ('--surface',     'White'),
        ('--surface-alt', 'Warm Grey'),
        ('--text',        'Dark'),
    ]
    HEADING_SIZE_CHOICES = [('28px', 'S'), ('36px', 'M'), ('48px', 'L'), ('60px', 'XL')]
    BODY_SIZE_CHOICES    = [('14px', 'S'), ('16px', 'M'), ('18px', 'L')]
    WEIGHT_CHOICES       = [('300', 'Light'), ('400', 'Regular'), ('500', 'Medium'), ('600', 'Bold')]
    IMG_POSITION_CHOICES = [
        ('top left', '↖'), ('top center', '↑'), ('top right', '↗'),
        ('center left', '←'), ('center center', '·'), ('center right', '→'),
        ('bottom left', '↙'), ('bottom center', '↓'), ('bottom right', '↘'),
    ]

    # Identity
    key        = models.CharField(max_length=50, choices=SECTION_KEYS)
    label      = models.CharField(max_length=100)
    order      = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    is_core    = models.BooleanField(default=True)

    # Layout
    variant = models.CharField(max_length=1, choices=VARIANT_CHOICES, default='1')

    # Background
    bg_mode            = models.CharField(max_length=15, choices=BG_MODE_CHOICES, default='colour')
    bg_colour          = models.CharField(max_length=20, choices=PALETTE_CHOICES, default='--surface')
    bg_image           = models.ImageField(upload_to='sections/', blank=True, null=True)
    bg_image_pos       = models.CharField(max_length=20, choices=IMG_POSITION_CHOICES, default='center center')
    bg_overlay_colour  = models.CharField(max_length=20, choices=PALETTE_CHOICES, default='--forest')
    bg_overlay_opacity = models.PositiveSmallIntegerField(default=40)  # 0–90

    # Spacing
    spacing = models.CharField(max_length=2, choices=SPACING_CHOICES, default='lg')

    # Typography — heading
    heading_colour = models.CharField(max_length=20, choices=PALETTE_CHOICES, default='--text')
    heading_size   = models.CharField(max_length=6, choices=HEADING_SIZE_CHOICES, default='48px')
    heading_weight = models.CharField(max_length=3, choices=WEIGHT_CHOICES, default='600')

    # Typography — body
    body_colour = models.CharField(max_length=20, choices=PALETTE_CHOICES, default='--text')
    body_size   = models.CharField(max_length=5, choices=BODY_SIZE_CHOICES, default='16px')
    body_weight = models.CharField(max_length=3, choices=WEIGHT_CHOICES, default='400')

    # Buttons
    btn1_colour  = models.CharField(max_length=20, choices=PALETTE_CHOICES, default='--forest', blank=True)
    btn1_style   = models.CharField(max_length=10, choices=BTN_STYLE_CHOICES, default='filled', blank=True)
    btn1_enabled = models.BooleanField(default=True)
    btn2_colour  = models.CharField(max_length=20, choices=PALETTE_CHOICES, default='--forest', blank=True)
    btn2_style   = models.CharField(max_length=10, choices=BTN_STYLE_CHOICES, default='outline', blank=True)
    btn2_enabled = models.BooleanField(default=False)

    # Custom section content
    custom_content   = models.JSONField(default=dict, blank=True)
    inline_image     = models.ImageField(upload_to='sections/inline/', blank=True, null=True)
    inline_image_pos = models.CharField(max_length=10, default='right',
                                        choices=[('left', 'Left'), ('right', 'Right')])

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.label} (order={self.order})'

    def get_bg_style(self):
        if self.bg_mode == 'image' and self.bg_image:
            return (f'background: url("{self.bg_image.url}") '
                    f'{self.bg_image_pos} / cover no-repeat;')
        if self.bg_mode == 'image_overlay' and self.bg_image:
            pct = self.bg_overlay_opacity
            return (
                f'background: linear-gradient('
                f'color-mix(in srgb, var({self.bg_overlay_colour}) {pct}%, transparent),'
                f'color-mix(in srgb, var({self.bg_overlay_colour}) {pct}%, transparent)),'
                f'url("{self.bg_image.url}") {self.bg_image_pos} / cover no-repeat;'
            )
        return f'background: var({self.bg_colour});'

    def get_spacing_padding(self):
        mapping = {'sm': '20px', 'md': '32px', 'lg': '40px', 'xl': '80px'}
        p = mapping.get(self.spacing, '80px')
        return f'padding: {p} 0;'

    def get_css_vars(self):
        return (
            f'--section-heading-color: var({self.heading_colour});'
            f'--section-heading-size: {self.heading_size};'
            f'--section-heading-weight: {self.heading_weight};'
            f'--section-body-color: var({self.body_colour});'
            f'--section-body-size: {self.body_size};'
            f'--section-body-weight: {self.body_weight};'
        )


class HomepageTemplate(models.Model):
    name       = models.CharField(max_length=100)
    is_active  = models.BooleanField(default=False)
    snapshot   = models.JSONField()   # serialised HomepageSection configs
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
