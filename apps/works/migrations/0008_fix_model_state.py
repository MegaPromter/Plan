"""
State-only migration: синхронизирует состояние Django ORM с реальным состоянием БД.
Все изменения уже применены в БД ранее.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0007_ppproject_up_product'),
    ]

    operations = [
        # Обновляем Meta.ordering для Project
        migrations.AlterModelOptions(
            name='project',
            options={
                'ordering': ['name_short', 'name_full'],
                'verbose_name': 'Проект',
                'verbose_name_plural': 'Проекты',
            },
        ),
        # AlterField — только state, DB уже правильная
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='ppproject',
                    name='name',
                    field=models.CharField(max_length=255, verbose_name='Название плана'),
                ),
                migrations.AlterField(
                    model_name='project',
                    name='code',
                    field=models.CharField(blank=True, max_length=100, verbose_name='Шифр / код'),
                ),
                migrations.AlterField(
                    model_name='project',
                    name='name_full',
                    field=models.CharField(max_length=500, verbose_name='Полное наименование'),
                ),
                migrations.AlterField(
                    model_name='projectproduct',
                    name='id',
                    field=models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
