from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0005_quotation_menu_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='advance_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='quotation',
            name='final_selling_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='quotation',
            name='internal_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='quotation',
            name='is_locked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quotation',
            name='margin',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=6),
        ),
        migrations.AddField(
            model_name='quotation',
            name='payment_terms',
            field=models.TextField(blank=True),
        ),
    ]
