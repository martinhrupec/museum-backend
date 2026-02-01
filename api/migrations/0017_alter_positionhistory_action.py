from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_remove_guard_available_positions_exhibition_open_on_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='positionhistory',
            name='action',
            field=models.CharField(
                choices=[
                    ('ASSIGNED', 'Assigned'),
                    ('CANCELED', 'Cancelled'),
                    ('REPLACED', 'Replaced'),
                ],
                max_length=25,
            ),
        ),
    ]
