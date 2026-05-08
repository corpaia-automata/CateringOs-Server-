from django.db import migrations, models


def backfill_credited_amount(apps, schema_editor):
    Quotation = apps.get_model('quotations', 'Quotation')
    for quotation in Quotation.objects.all().only('id', 'advance_amount'):
        quotation.credited_amount = quotation.advance_amount or 0
        quotation.save(update_fields=['credited_amount'])


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0006_quotation_pricing_lock_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='credited_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(backfill_credited_amount, migrations.RunPython.noop),
    ]
