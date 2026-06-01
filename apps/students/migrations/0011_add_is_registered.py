from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0010_smenaslot'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='is_registered',
            field=models.BooleanField(
                default=False,
                verbose_name="Ro'yxatdan o'tganmi",
                help_text="Tinglovchi foto yuklagan va tizimga ulanganmi"
            ),
        ),
    ]
