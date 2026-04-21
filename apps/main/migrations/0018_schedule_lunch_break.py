from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0017_remove_employee_user_id_employee_telegram_user_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='lunch_start',
            field=models.TimeField(blank=True, null=True, verbose_name='Tushlik boshlanishi'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='lunch_end',
            field=models.TimeField(blank=True, null=True, verbose_name='Tushlik tugashi'),
        ),
    ]
