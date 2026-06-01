from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0005_add_invite_token'),
        ('superadmin', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Smena',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Smena nomi')),
                ('para1_start', models.TimeField(verbose_name='1-para boshlanishi')),
                ('para2_start', models.TimeField(blank=True, null=True, verbose_name='2-para boshlanishi')),
                ('para3_start', models.TimeField(blank=True, null=True, verbose_name='3-para boshlanishi')),
                ('filial', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='smenas', to='superadmin.filial')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='smenas', to='superadmin.organization')),
            ],
            options={
                'verbose_name': 'Smena',
                'verbose_name_plural': 'Smenalar',
            },
        ),
        migrations.CreateModel(
            name='GroupLesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Sana')),
                ('building', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='superadmin.building', verbose_name='Lokatsiya')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='students.group')),
                ('smena', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='students.smena', verbose_name='Smena')),
            ],
            options={
                'verbose_name': 'Guruh darsi',
                'verbose_name_plural': 'Guruh darslari',
                'ordering': ['date'],
                'unique_together': {('group', 'date')},
            },
        ),
    ]
