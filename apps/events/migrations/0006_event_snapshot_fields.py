from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_event_credited_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='costing_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='event',
            name='grocery_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='event',
            name='menu_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='event',
            name='pricing_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
