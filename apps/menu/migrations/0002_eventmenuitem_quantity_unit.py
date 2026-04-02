from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventmenuitem',
            name='quantity_unit',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
