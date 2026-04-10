from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("works", "0021_notice_status_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workreport",
            name="doc_type",
            field=models.CharField(
                blank=True,
                default="",
                verbose_name="Вид документа",
                choices=[
                    ("design", "Конструкторский"),
                    ("tech", "Технологический"),
                    ("report", "Отчёт"),
                    ("program", "Программа испытаний"),
                    ("other", "Прочее"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="workreport",
            name="doc_class",
            field=models.CharField(
                blank=True,
                default="",
                verbose_name="Класс документа",
                choices=[
                    ("original", "Подлинник"),
                    ("copy", "Копия"),
                    ("draft", "Черновик"),
                ],
                max_length=20,
            ),
        ),
    ]
