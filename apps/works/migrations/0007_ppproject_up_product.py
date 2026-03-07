from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0006_project_up_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='ppproject',
            name='up_product',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pp_plans',
                to='works.projectproduct',
                verbose_name='Изделие УП',
            ),
        ),
    ]
