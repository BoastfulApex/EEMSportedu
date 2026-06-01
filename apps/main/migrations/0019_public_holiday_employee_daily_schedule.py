from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0018_schedule_lunch_break'),
        ('superadmin', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicHoliday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True, verbose_name='Sana')),
                ('name', models.CharField(max_length=200, verbose_name='Nomi')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('filial', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='public_holidays',
                    to='superadmin.filial',
                    verbose_name="Filial (bo'sh = barchasi)"
                )),
            ],
            options={
                'verbose_name': 'Umumiy dam olish kuni',
                'verbose_name_plural': 'Umumiy dam olish kunlari',
                'ordering': ['date'],
            },
        ),
        migrations.CreateModel(
            name='EmployeeDailySchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Sana')),
                ('start', models.TimeField(blank=True, null=True, verbose_name='Ish boshlanishi')),
                ('end', models.TimeField(blank=True, null=True, verbose_name='Ish tugashi')),
                ('is_day_off', models.BooleanField(default=False, verbose_name='Dam olish kuni')),
                ('day_off_reason', models.CharField(blank=True, max_length=200, null=True, verbose_name='Dam olish sababi')),
                ('is_manually_edited', models.BooleanField(default=False, verbose_name="Qo'lda o'zgartirilgan")),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='daily_schedules',
                    to='main.employee',
                    verbose_name='Xodim'
                )),
                ('location', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='daily_schedules',
                    to='main.location',
                    verbose_name='Lokatsiya'
                )),
                ('source_schedule', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='daily_entries',
                    to='main.schedule',
                    verbose_name='Manba jadval'
                )),
            ],
            options={
                'verbose_name': 'Xodim kunlik jadvali',
                'verbose_name_plural': 'Xodim kunlik jadvallari',
                'ordering': ['date'],
                'unique_together': {('employee', 'date')},
            },
        ),
    ]
