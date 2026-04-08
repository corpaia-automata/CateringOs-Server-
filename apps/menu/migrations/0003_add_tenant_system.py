# State-only migration: tells Django's ORM that EventMenuItem now has a tenant FK.
# All database changes were already applied by tenants.0001_add_tenant_system.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu',    '0002_eventmenuitem_quantity_unit'),
        ('tenants', '0001_add_tenant_system'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='eventmenuitem',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='menu_items',
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
            ],
            database_operations=[],
        ),
    ]
