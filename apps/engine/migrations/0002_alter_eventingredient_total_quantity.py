# Generated manually — increase decimal_places 4→6 to prevent sub-milligram precision loss

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('engine', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventingredient',
            name='total_quantity',
            field=models.DecimalField(decimal_places=6, max_digits=14),
        ),
    ]
