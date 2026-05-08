from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0028_jsonfield_blank'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quotationtemplate',
            name='gallery_images',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='cover_elements',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
