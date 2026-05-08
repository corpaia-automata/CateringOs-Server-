from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0012_alter_quotationtemplate_managers'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationtemplate',
            name='cover_image_url',
            field=models.URLField(blank=True),
        ),
    ]
