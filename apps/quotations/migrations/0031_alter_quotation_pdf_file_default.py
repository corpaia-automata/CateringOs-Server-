"""Correct ``pdf_file`` default after interactive makemigrations typo (``1`` → empty string)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0030_alter_quotationtemplate_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quotation',
            name='pdf_file',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
