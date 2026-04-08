# State-only migration: tells Django's ORM that Quotation now has a tenant FK.
# All database changes were already applied by tenants.0001_add_tenant_system.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0001_initial'),
        ('tenants',    '0001_add_tenant_system'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='quotation',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='quotations',
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
            ],
            database_operations=[],
        ),
    ]
