from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_event_snapshot_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='services_snapshot',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
