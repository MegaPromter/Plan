"""
Migration: Add УП module fields to Project, add ProjectProduct,
add up_project FK on PPProject, add updated_at to Project.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0005_workcalendar_auditlog'),
    ]

    operations = [
        # 1. Rename 'name' -> 'name_full' on Project
        migrations.RenameField(
            model_name='project',
            old_name='name',
            new_name='name_full',
        ),
        # 2. Add name_short field
        migrations.AddField(
            model_name='project',
            name='name_short',
            field=models.CharField(blank=True, max_length=100, verbose_name='Краткое наименование'),
        ),
        # 3. Add updated_at field
        migrations.AddField(
            model_name='project',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Обновлён'),
        ),
        # 4. Create ProjectProduct model
        migrations.CreateModel(
            name='ProjectProduct',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Наименование изделия')),
                ('code', models.CharField(blank=True, max_length=100, verbose_name='Шифр')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='products',
                    to='works.project',
                    verbose_name='Проект',
                )),
            ],
            options={
                'verbose_name': 'Изделие проекта',
                'verbose_name_plural': 'Изделия проекта',
                'db_table': 'work_project_product',
                'ordering': ['name'],
            },
        ),
        # 5. Add up_project FK on PPProject
        migrations.AddField(
            model_name='ppproject',
            name='up_project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pp_plans',
                to='works.project',
                verbose_name='Проект УП',
            ),
        ),
    ]
