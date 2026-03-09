import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0008_fix_model_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ppwork',
            name='coeff',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Коэффициент'),
        ),
        migrations.AlterField(
            model_name='ppwork',
            name='task_type',
            field=models.CharField(blank=True, default='Выпуск нового документа', max_length=100, verbose_name='Тип работы'),
        ),
    ]
