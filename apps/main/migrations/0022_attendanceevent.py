from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0021_employeedailyextrashift'),
        ('students', '0014_group_limit_start_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('person_type', models.CharField(choices=[('employee', 'Xodim'), ('student', 'Tinglovchi')], max_length=10)),
                ('event_type', models.CharField(choices=[('check_in', 'Kirish'), ('check_out', 'Chiqish')], max_length=20)),
                ('date', models.DateField()),
                ('time', models.TimeField()),
                ('location_name', models.CharField(blank=True, max_length=200, null=True)),
                ('latitude', models.FloatField(blank=True, null=True)),
                ('longitude', models.FloatField(blank=True, null=True)),
                ('distance_meters', models.FloatField(blank=True, null=True)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='attendance_photos/%Y/%m/%d/')),
                ('verified_by', models.CharField(choices=[('self', "O'zi (bot orqali)"), ('hr_admin', 'HR admin'), ('edu_admin', "O'quv admin")], default='self', max_length=20)),
                ('face_match_score', models.FloatField(blank=True, help_text="Yuz o'xshashlik foizi (0-100), faqat admin orqali kelganda mavjud", null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendance_events', to='main.employee')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendance_events', to='students.student')),
                ('attendance', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='main.attendance')),
                ('student_attendance', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='students.studentattendance')),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_events', to='main.location')),
            ],
            options={
                'verbose_name': 'Kirish-chiqish hodisasi',
                'verbose_name_plural': 'Kirish-chiqish hodisalari',
                'ordering': ['-date', '-time'],
            },
        ),
    ]
