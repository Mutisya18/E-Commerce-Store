from django.db import migrations, models

SHOP_LINKS_DEFAULT = [
    {"label": "All Products",  "url": "/products/",              "visible": True},
    {"label": "New Arrivals",  "url": "/products/?sort=newest",  "visible": True},
    {"label": "Deals",         "url": "/products/?sale=1",       "visible": True},
    {"label": "Best Sellers",  "url": "#bestsellers",            "visible": True},
]

HELP_LINKS_DEFAULT = [
    {"label": "Track My Order",     "url": "/orders/",             "visible": True},
    {"label": "Returns & Warranty", "url": "/help/returns/",       "visible": True},
    {"label": "FAQs",               "url": "/help/faq/",           "visible": True},
    {"label": "Sign In",            "url": "/accounts/login/",     "visible": True},
    {"label": "Create Account",     "url": "/accounts/signup/",    "visible": True},
]


def seed_footer_links(apps, schema_editor):
    StoreSettings = apps.get_model('dashboard', 'StoreSettings')
    StoreSettings.objects.filter(pk=1).update(
        footer_shop_links=SHOP_LINKS_DEFAULT,
        footer_help_links=HELP_LINKS_DEFAULT,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_forest_palette'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='footer_tagline',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_ig_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_tiktok_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_x_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_privacy_url',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_terms_url',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_shop_links',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='footer_help_links',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(seed_footer_links, reverse_code=migrations.RunPython.noop),
    ]
