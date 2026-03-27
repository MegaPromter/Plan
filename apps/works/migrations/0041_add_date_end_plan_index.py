# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0040_add_composite_indexes'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='work',
            index=models.Index(
                fields=['date_end', 'show_in_plan'],
                name='idx_work_date_end_plan',
            ),
        ),
    ]
