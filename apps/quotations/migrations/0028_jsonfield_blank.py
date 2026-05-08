from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0027_quotation_pdf_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quotationtemplate',
            name='special_notes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='terms_clauses',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='sections_config',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='template_schema',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
