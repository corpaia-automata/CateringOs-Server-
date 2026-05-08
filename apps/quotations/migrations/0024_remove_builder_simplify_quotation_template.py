"""Drop canvas builder models, remove ``pages_schema``, rename ``level`` → ``template_type``."""

from django.db import migrations, models


def map_simple_to_minimal(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    QuotationTemplate.objects.filter(level='simple').update(level='minimal')


def reverse_minimal_to_simple(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    QuotationTemplate.objects.filter(level='minimal').update(level='simple')


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0023_unified_quotation_template'),
    ]

    operations = [
        migrations.DeleteModel(name='BuilderQuotationActivity'),
        migrations.DeleteModel(name='BuilderQuotation'),
        migrations.DeleteModel(name='BuilderMenuItem'),
        migrations.DeleteModel(name='BuilderMenuCategory'),
        migrations.RemoveField(
            model_name='quotationtemplate',
            name='pages_schema',
        ),
        migrations.RunPython(map_simple_to_minimal, reverse_minimal_to_simple),
        migrations.RenameField(
            model_name='quotationtemplate',
            old_name='level',
            new_name='template_type',
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='template_type',
            field=models.CharField(
                choices=[
                    ('premium', 'Premium'),
                    ('standard', 'Standard'),
                    ('minimal', 'Minimal'),
                ],
                default='standard',
                max_length=20,
            ),
        ),
    ]
