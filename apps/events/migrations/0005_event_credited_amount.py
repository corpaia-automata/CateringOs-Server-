from django.db import migrations, models


def backfill_credited_amount(apps, schema_editor):
    Event = apps.get_model('events', 'Event')
    for event in Event.objects.all().only('id', 'advance_amount'):
        event.credited_amount = event.advance_amount
        event.save(update_fields=['credited_amount'])


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_event_inquiry_event_quotation'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='credited_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.RunPython(backfill_credited_amount, migrations.RunPython.noop),
    ]
