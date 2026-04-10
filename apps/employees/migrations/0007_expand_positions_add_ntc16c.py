"""
Расширение должностей (8 новых позиций, max_length 30→50)
и добавление НТЦ-16Ц в справочник центров.
"""

from django.db import migrations, models


def add_ntc_16c(apps, schema_editor):
    NTCCenter = apps.get_model("employees", "NTCCenter")
    NTCCenter.objects.get_or_create(code="НТЦ-16Ц")


def remove_ntc_16c(apps, schema_editor):
    NTCCenter = apps.get_model("employees", "NTCCenter")
    NTCCenter.objects.filter(code="НТЦ-16Ц").delete()


NEW_POSITION_CHOICES = [
    ("tech_3", "Техник-конструктор"),
    ("tech_2", "Техник-конструктор 2 кат."),
    ("tech_1", "Техник-конструктор 1 кат."),
    ("spec", "Специалист"),
    ("spec_2", "Специалист 2 кат."),
    ("spec_1", "Специалист 1 кат."),
    ("lead_spec", "Ведущий специалист"),
    ("eng", "Инженер-конструктор"),
    ("eng_3", "Инженер-конструктор 3 кат."),
    ("eng_2", "Инженер-конструктор 2 кат."),
    ("eng_1", "Инженер-конструктор 1 кат."),
    ("lead_eng", "Ведущий инженер-конструктор"),
    ("lead_eng_dir_3", "Ведущий инженер по направлению 3 класса"),
    ("lead_eng_dir_2", "Ведущий инженер по направлению 2 класса"),
    ("lead_eng_coord", "Ведущий инженер - координатор группы"),
    ("bureau_head", "Начальник бюро"),
    ("jr_researcher", "Младший научный сотрудник"),
    ("sr_researcher", "Старший научный сотрудник"),
    ("lead_researcher", "Ведущий научный сотрудник"),
    ("sector_head", "Начальник сектора"),
    ("dept_deputy_sector", "Зам. начальника отдела – начальник сектора"),
    ("dept_deputy", "Зам. начальника отдела"),
    ("dept_head", "Начальник отдела"),
    ("dir_direction", "Руководитель направления"),
    ("ntc_deputy", "Зам. руководителя НТЦ"),
    ("ntc_head", "Руководитель НТЦ"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0006_business_trip"),
    ]

    operations = [
        # Расширяем max_length и обновляем choices
        migrations.AlterField(
            model_name="employee",
            name="position",
            field=models.CharField(
                "Должность",
                max_length=50,
                choices=NEW_POSITION_CHOICES,
                blank=True,
            ),
        ),
        # Добавляем НТЦ-16Ц
        migrations.RunPython(add_ntc_16c, remove_ntc_16c),
    ]
