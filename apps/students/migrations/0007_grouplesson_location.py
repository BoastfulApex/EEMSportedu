from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0006_smena_grouplesson'),
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='grouplesson',
            name='building',
        ),
        migrations.AddField(
            model_name='grouplesson',
            name='location',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='main.location',
                verbose_name='Lokatsiya'
            ),
        ),
    ]
