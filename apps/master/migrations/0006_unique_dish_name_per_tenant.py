from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0005_add_tenant_system'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='dish',
            name='unique_active_dish_name',
        ),
        migrations.AddConstraint(
            model_name='dish',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'name'],
                condition=models.Q(is_deleted=False),
                name='unique_active_dish_name_per_tenant',
            ),
        ),
    ]
