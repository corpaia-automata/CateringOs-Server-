# Generated manually for Inquiry.venue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inquiries', '0010_alter_inquiry_managers_alter_preestimate_managers_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inquiry',
            name='venue',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
