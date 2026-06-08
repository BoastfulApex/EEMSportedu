from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0013_add_masofaviy_and_muqobil_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='limit_start_date',
            field=models.DateField(
                null=True,
                blank=True,
                verbose_name='Limit hisoblash boshlanish sanasi',
                help_text="Bu sanadan oldingi darslar 'sinov' deb qaraladi va limitga hisoblanmaydi",
            ),
        ),
    ]
