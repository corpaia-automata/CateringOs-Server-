# Generated manually for template builder API / PDF snapshot parity

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0016_quotationtemplate_about_text_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationtemplate',
            name='background_color',
            field=models.CharField(blank=True, default='#ffffff', max_length=7),
        ),
    ]
