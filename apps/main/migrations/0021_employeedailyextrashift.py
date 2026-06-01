from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_employeedailyschedule_lunch'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeDailyExtraShift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.TimeField(verbose_name='Boshlanish vaqti')),
                ('end', models.TimeField(verbose_name='Tugash vaqti')),
                ('lunch_start', models.TimeField(blank=True, null=True, verbose_name='Tushlik boshlanishi')),
                ('lunch_end', models.TimeField(blank=True, null=True, verbose_name='Tushlik tugashi')),
                ('note', models.CharField(blank=True, max_length=200, null=True, verbose_name='Izoh')),
                ('order', models.PositiveSmallIntegerField(default=2, verbose_name='Tartib')),
                ('daily', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='extra_shifts',
                    to='main.employeedailyschedule',
                    verbose_name='Kunlik jadval'
                )),
                ('location', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='extra_shifts',
                    to='main.location',
                    verbose_name='Lokatsiya'
                )),
            ],
            options={
                'verbose_name': "Qo'shimcha shift",
                'verbose_name_plural': "Qo'shimcha shiftlar",
                'ordering': ['order', 'start'],
            },
        ),
    ]
