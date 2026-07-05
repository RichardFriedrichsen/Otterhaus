from django.db import migrations, models

import core.models


def backfill_access_codes(apps, schema_editor):
    House = apps.get_model('core', 'House')
    used = set(House.objects.exclude(access_code=None).values_list('access_code', flat=True))
    for house in House.objects.all():
        code = core.models.generate_access_code()
        while code in used:
            code = core.models.generate_access_code()
        used.add(code)
        house.access_code = code
        house.save(update_fields=['access_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_chore_assigned_to_chore_house_chore_recurrence_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='house',
            name='access_code',
            field=models.CharField(
                max_length=8, null=True, editable=False,
                help_text='Shared with others so they can join this house.',
            ),
        ),
        migrations.RunPython(backfill_access_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='house',
            name='access_code',
            field=models.CharField(
                max_length=8, unique=True, editable=False,
                default=core.models.generate_access_code,
                help_text='Shared with others so they can join this house.',
            ),
        ),
        migrations.DeleteModel(
            name='HouseInvite',
        ),
    ]
