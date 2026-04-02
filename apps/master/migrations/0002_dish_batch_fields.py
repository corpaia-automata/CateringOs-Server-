from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dish',
            name='batch_size',
            field=models.DecimalField(decimal_places=3, default=1, max_digits=10),
        ),
        migrations.AddField(
            model_name='dish',
            name='batch_unit',
            field=models.CharField(default='KG', max_length=20),
        ),
    ]
