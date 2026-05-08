import uuid

from django.db import migrations, models


def populate_public_tokens(apps, schema_editor):
    Quotation = apps.get_model('quotations', 'Quotation')
    for pk in Quotation.objects.filter(public_token__isnull=True).values_list('pk', flat=True):
        Quotation.objects.filter(pk=pk).update(public_token=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0014_quotationtemplate_font_family'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='public_token',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='quotation',
            name='public_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
