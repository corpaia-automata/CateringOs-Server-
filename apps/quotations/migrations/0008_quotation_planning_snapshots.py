from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0007_quotation_credited_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='costing_data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='quotation',
            name='grocery_data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='quotation',
            name='pricing_data',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
