from django.db import migrations

CORE_SECTIONS = [
    # (key, label, order, bg_colour, heading_colour)
    ('hero',         'Hero Banner',        0, '--forest',      '--surface'),
    ('categories',   'Category Tiles',     1, '--base',        '--forest'),
    ('featured',     'Featured Products',  2, '--surface',     '--forest'),
    ('deals',        'Deals / Flash Sales',3, '--forest',      '--surface'),
    ('bestsellers',  'Best Sellers',       4, '--surface-alt', '--forest'),
    ('story',        'Brand Story',        5, '--surface-alt', '--forest'),
    ('testimonials', 'Testimonials',       6, '--surface',     '--forest'),
    ('newsletter',   'Newsletter Signup',  7, '--sage',        '--forest'),
]


def seed_sections(apps, schema_editor):
    HomepageSection = apps.get_model('dashboard', 'HomepageSection')
    for key, label, order, bg_colour, heading_colour in CORE_SECTIONS:
        HomepageSection.objects.get_or_create(
            key=key,
            defaults=dict(
                label=label,
                order=order,
                is_visible=True,
                is_core=True,
                variant='1',
                bg_mode='colour',
                bg_colour=bg_colour,
                heading_colour=heading_colour,
            ),
        )


def unseed_sections(apps, schema_editor):
    HomepageSection = apps.get_model('dashboard', 'HomepageSection')
    HomepageSection.objects.filter(
        key__in=[s[0] for s in CORE_SECTIONS], is_core=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_homepage_section_and_template'),
    ]

    operations = [
        migrations.RunPython(seed_sections, reverse_code=unseed_sections),
    ]
