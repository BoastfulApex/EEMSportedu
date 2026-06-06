from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0012_add_muqobil_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='muqobil_to',
            field=models.DateField(blank=True, null=True, verbose_name="Muqobil tugash sanasi"),
        ),
        migrations.AddField(
            model_name='student',
            name='is_masofaviy',
            field=models.BooleanField(default=False, verbose_name="Masofaviy ta'limda"),
        ),
        migrations.AddField(
            model_name='student',
            name='masofaviy_from',
            field=models.DateField(blank=True, null=True, verbose_name="Masofaviyga o'tgan sana"),
        ),
        migrations.AddField(
            model_name='student',
            name='masofaviy_to',
            field=models.DateField(blank=True, null=True, verbose_name="Masofaviy tugash sanasi"),
        ),
    ]
