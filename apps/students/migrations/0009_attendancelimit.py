from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0008_add_early_leave_minutes'),
        ('superadmin', '0005_organization_administrator_is_org_admin_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('para_hours', models.FloatField(default=2.0, verbose_name='1 para (soat)')),
                ('max_missed_hours', models.FloatField(default=20.0, verbose_name="Maksimal qoldirish mumkin bo'lgan soat")),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_limits', to='superadmin.organization')),
                ('filial', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_limits', to='superadmin.filial')),
            ],
            options={
                'verbose_name': 'Davomat limiti',
                'verbose_name_plural': 'Davomat limitlari',
                'unique_together': {('organization', 'filial')},
            },
        ),
    ]
