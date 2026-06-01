import uuid
from django.db import migrations, models


def fill_invite_tokens(apps, schema_editor):
    Group = apps.get_model('students', 'Group')
    for group in Group.objects.filter(invite_token__isnull=True):
        group.invite_token = uuid.uuid4()
        group.save(update_fields=['invite_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0004_add_plain_password'),
    ]

    operations = [
        # 1 — nullable, unique yo'q
        migrations.AddField(
            model_name='group',
            name='invite_token',
            field=models.UUIDField(null=True, blank=True, editable=False),
        ),
        # 2 — mavjud qatorlarga UUID to'ldirish
        migrations.RunPython(fill_invite_tokens, migrations.RunPython.noop),
        # 3 — unique va not null qilish
        migrations.AlterField(
            model_name='group',
            name='invite_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
