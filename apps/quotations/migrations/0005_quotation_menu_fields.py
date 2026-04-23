from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0004_alter_quotation_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='menu_dishes',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='quotation',
            name='menu_services',
            field=models.JSONField(default=list),
        ),
    ]
