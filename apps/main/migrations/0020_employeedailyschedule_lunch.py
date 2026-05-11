from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0019_public_holiday_employee_daily_schedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeedailyschedule',
            name='lunch_start',
            field=models.TimeField(blank=True, null=True, verbose_name='Tushlik boshlanishi'),
        ),
        migrations.AddField(
            model_name='employeedailyschedule',
            name='lunch_end',
            field=models.TimeField(blank=True, null=True, verbose_name='Tushlik tugashi'),
        ),
    ]
