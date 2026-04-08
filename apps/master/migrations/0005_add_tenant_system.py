# State-only migration: tells Django's ORM that Ingredient, Dish, and
# DishRecipe now have tenant FKs.
# All database changes were already applied by tenants.0001_add_tenant_system.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master',  '0004_add_meat_subcategories'),
        ('tenants', '0001_add_tenant_system'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='ingredient',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='ingredients',
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='dish',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='dishes',
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='dishrecipe',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='dish_recipes',
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
            ],
            database_operations=[],
        ),
    ]
