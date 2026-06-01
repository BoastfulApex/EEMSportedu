from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0009_attendancelimit'),
    ]

    operations = [
        # para1_start ni nullable qilish (eski ma'lumotlar saqlanib qoladi)
        migrations.AlterField(
            model_name='smena',
            name='para1_start',
            field=models.TimeField(blank=True, null=True, verbose_name='1-para boshlanishi (eski)'),
        ),
        migrations.AlterField(
            model_name='smena',
            name='para2_start',
            field=models.TimeField(blank=True, null=True, verbose_name='2-para boshlanishi (eski)'),
        ),
        migrations.AlterField(
            model_name='smena',
            name='para3_start',
            field=models.TimeField(blank=True, null=True, verbose_name='3-para boshlanishi (eski)'),
        ),
        # Yangi SmenaSlot modeli
        migrations.CreateModel(
            name='SmenaSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(default=1, verbose_name='Tartib raqami')),
                ('start', models.TimeField(verbose_name='Boshlanish vaqti')),
                ('end',   models.TimeField(blank=True, null=True, verbose_name='Tugash vaqti')),
                ('smena', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='slots', to='students.smena')),
            ],
            options={
                'verbose_name': 'Para vaqti',
                'verbose_name_plural': 'Para vaqtlari',
                'ordering': ['order'],
            },
        ),
        # Mavjud smenalardan SmenaSlot yaratish
        migrations.RunPython(
            code=lambda apps, schema_editor: _migrate_existing(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
    ]


def _migrate_existing(apps, schema_editor):
    Smena = apps.get_model('students', 'Smena')
    SmenaSlot = apps.get_model('students', 'SmenaSlot')
    for smena in Smena.objects.all():
        order = 1
        for field in ['para1_start', 'para2_start', 'para3_start']:
            t = getattr(smena, field)
            if t:
                SmenaSlot.objects.create(smena=smena, order=order, start=t, end=None)
                order += 1
