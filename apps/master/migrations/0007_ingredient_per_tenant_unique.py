from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0006_unique_dish_name_per_tenant'),
    ]

    operations = [
        # Drop the old global unique index on name
        migrations.AlterField(
            model_name='ingredient',
            name='name',
            field=models.CharField(max_length=255),
        ),
        # Add per-tenant unique constraint
        migrations.AddConstraint(
            model_name='ingredient',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_ingredient_name_per_tenant',
            ),
        ),
    ]
