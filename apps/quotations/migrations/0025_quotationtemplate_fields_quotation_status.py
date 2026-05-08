"""Add QuotationTemplate layout/branding fields; normalize ``template_type`` and quotation ``status`` values."""

from django.db import migrations, models


def forwards_map_template_standard_to_classic(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    QuotationTemplate.objects.filter(template_type='standard').update(template_type='classic')


def reverse_map_template_classic_to_standard(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    QuotationTemplate.objects.filter(template_type='classic').update(template_type='standard')


def forwards_lower_quotation_status(apps, schema_editor):
    Quotation = apps.get_model('quotations', 'Quotation')
    mapping = {
        'DRAFT': 'draft',
        'SENT': 'sent',
        'ACCEPTED': 'accepted',
        'REJECTED': 'rejected',
    }
    for old, new in mapping.items():
        Quotation.objects.filter(status=old).update(status=new)


def reverse_upper_quotation_status(apps, schema_editor):
    Quotation = apps.get_model('quotations', 'Quotation')
    mapping = {
        'draft': 'DRAFT',
        'sent': 'SENT',
        'accepted': 'ACCEPTED',
        'rejected': 'REJECTED',
    }
    for old, new in mapping.items():
        Quotation.objects.filter(status=old).update(status=new)


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0024_remove_builder_simplify_quotation_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationtemplate',
            name='hero_image',
            field=models.ImageField(blank=True, null=True, upload_to='heroes/'),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='font_heading',
            field=models.CharField(default='Playfair Display', max_length=50),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='font_body',
            field=models.CharField(default='Inter', max_length=50),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='company_tagline',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='why_choose_us',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='sections_config',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='template_schema',
            field=models.JSONField(default=dict),
        ),
        migrations.RunPython(forwards_map_template_standard_to_classic, reverse_map_template_classic_to_standard),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='template_type',
            field=models.CharField(
                choices=[
                    ('classic', 'Classic'),
                    ('premium', 'Premium'),
                    ('minimal', 'Minimal'),
                ],
                default='classic',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='primary_color',
            field=models.CharField(default='#1A1A1A', max_length=7),
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='accent_color',
            field=models.CharField(default='#C9A84C', max_length=7),
        ),
        migrations.RunPython(forwards_lower_quotation_status, reverse_upper_quotation_status),
        migrations.AlterField(
            model_name='quotation',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('sent', 'Sent'),
                    ('accepted', 'Accepted'),
                    ('rejected', 'Rejected'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
