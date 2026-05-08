from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inquiries', '0011_inquiry_venue'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inquiry',
            name='source_channel',
            field=models.CharField(
                blank=True,
                choices=[('PHONE_CALL', 'Phone Call'), ('WHATSAPP', 'WhatsApp'), ('WALK_IN', 'Walk-In')],
                default='',
                max_length=15,
            ),
        ),
    ]
