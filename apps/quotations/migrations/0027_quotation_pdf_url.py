"""Add ``Quotation.pdf_url`` for Celery-generated S3 PDF links."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0026_seed_quotationtemplate_json_defaults'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='pdf_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
