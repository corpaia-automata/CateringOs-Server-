from django.db import migrations, models


def populate_quote_numbers(apps, schema_editor):
    Quotation = apps.get_model('quotations', 'Quotation')
    for i, q in enumerate(Quotation.objects.order_by('created_at'), start=1):
        q.quote_number = f'QTN-{str(i).zfill(5)}'
        q.save(update_fields=['quote_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0002_add_tenant_system'),
    ]

    operations = [
        # 1. Add the column as nullable (no unique constraint yet)
        migrations.AddField(
            model_name='quotation',
            name='quote_number',
            field=models.CharField(blank=True, editable=False, max_length=20, default=''),
            preserve_default=False,
        ),
        # 2. Populate existing rows
        migrations.RunPython(populate_quote_numbers, migrations.RunPython.noop),
        # 3. Apply unique constraint
        migrations.AlterField(
            model_name='quotation',
            name='quote_number',
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True),
        ),
        migrations.AlterModelOptions(
            name='quotation',
            options={'db_table': 'quotations', 'ordering': ['-created_at']},
        ),
    ]
