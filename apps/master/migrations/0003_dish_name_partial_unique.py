from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0002_dish_batch_fields'),
    ]

    operations = [
        # Drop the old full unique constraint on name
        migrations.AlterField(
            model_name='dish',
            name='name',
            field=models.CharField(max_length=255),
        ),
        # Add partial unique constraint — only active (non-deleted) dishes must have unique names
        migrations.AddConstraint(
            model_name='dish',
            constraint=models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(is_deleted=False),
                name='unique_active_dish_name',
            ),
        ),
    ]
