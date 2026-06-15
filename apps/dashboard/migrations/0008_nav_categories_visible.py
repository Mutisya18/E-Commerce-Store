from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_footer_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='nav_categories_visible',
            field=models.BooleanField(default=True),
        ),
    ]
