from django.db import migrations

# Old token → new token mapping
TOKEN_MAP = {
    '--navy':    '--forest',
    '--emerald': '--sage',
    # --gold, --surface, --surface-alt, --text stay the same
}

COLOUR_FIELDS = [
    'bg_colour', 'bg_overlay_colour',
    'heading_colour', 'body_colour',
    'btn1_colour', 'btn2_colour',
]


def remap_tokens(apps, schema_editor):
    HomepageSection = apps.get_model('dashboard', 'HomepageSection')
    for section in HomepageSection.objects.all():
        update = {f: TOKEN_MAP[getattr(section, f)]
                  for f in COLOUR_FIELDS if getattr(section, f) in TOKEN_MAP}
        if update:
            HomepageSection.objects.filter(pk=section.pk).update(**update)


def reverse_remap(apps, schema_editor):
    REVERSE = {v: k for k, v in TOKEN_MAP.items()}
    HomepageSection = apps.get_model('dashboard', 'HomepageSection')
    for section in HomepageSection.objects.all():
        update = {}
        for field in COLOUR_FIELDS:
            val = getattr(section, field)
            if val in REVERSE:
                update[field] = REVERSE[val]
        if update:
            HomepageSection.objects.filter(pk=section.pk).update(**update)


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_variant_choices_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='homepagesection',
            name='bg_colour',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('--forest', 'Forest'), ('--gold', 'Gold'), ('--gold-muted', 'Gold Muted'),
                    ('--sage', 'Sage'), ('--base', 'Parchment'), ('--surface', 'White'),
                    ('--surface-alt', 'Warm Grey'), ('--text', 'Dark'),
                ],
                default='--surface',
            ),
        ),
        migrations.AlterField(
            model_name='homepagesection',
            name='bg_overlay_colour',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('--forest', 'Forest'), ('--gold', 'Gold'), ('--gold-muted', 'Gold Muted'),
                    ('--sage', 'Sage'), ('--base', 'Parchment'), ('--surface', 'White'),
                    ('--surface-alt', 'Warm Grey'), ('--text', 'Dark'),
                ],
                default='--forest',
            ),
        ),
        migrations.AlterField(
            model_name='homepagesection',
            name='heading_colour',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('--forest', 'Forest'), ('--gold', 'Gold'), ('--gold-muted', 'Gold Muted'),
                    ('--sage', 'Sage'), ('--base', 'Parchment'), ('--surface', 'White'),
                    ('--surface-alt', 'Warm Grey'), ('--text', 'Dark'),
                ],
                default='--text',
            ),
        ),
        migrations.AlterField(
            model_name='homepagesection',
            name='body_colour',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('--forest', 'Forest'), ('--gold', 'Gold'), ('--gold-muted', 'Gold Muted'),
                    ('--sage', 'Sage'), ('--base', 'Parchment'), ('--surface', 'White'),
                    ('--surface-alt', 'Warm Grey'), ('--text', 'Dark'),
                ],
                default='--text',
            ),
        ),
        migrations.AlterField(
            model_name='homepagesection',
            name='btn1_colour',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20, blank=True,
                choices=[
                    ('--forest', 'Forest'), ('--gold', 'Gold'), ('--gold-muted', 'Gold Muted'),
                    ('--sage', 'Sage'), ('--base', 'Parchment'), ('--surface', 'White'),
                    ('--surface-alt', 'Warm Grey'), ('--text', 'Dark'),
                ],
                default='--forest',
            ),
        ),
        migrations.AlterField(
            model_name='homepagesection',
            name='btn2_colour',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20, blank=True,
                choices=[
                    ('--forest', 'Forest'), ('--gold', 'Gold'), ('--gold-muted', 'Gold Muted'),
                    ('--sage', 'Sage'), ('--base', 'Parchment'), ('--surface', 'White'),
                    ('--surface-alt', 'Warm Grey'), ('--text', 'Dark'),
                ],
                default='--forest',
            ),
        ),
        migrations.RunPython(remap_tokens, reverse_code=reverse_remap),
    ]
