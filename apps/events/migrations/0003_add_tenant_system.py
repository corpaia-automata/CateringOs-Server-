# State-only migration: tells Django's ORM that Event now has a tenant FK.
# All database changes were already applied by tenants.0001_add_tenant_system.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events',  '0002_event_add_fields'),
        ('tenants', '0001_add_tenant_system'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='event',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='events',
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
            ],
            database_operations=[],
        ),
    ]
