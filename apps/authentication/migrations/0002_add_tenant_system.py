# State-only migration: tells Django's ORM that User now has a tenant FK
# and that the email unique constraint has changed to (tenant_id, email).
# All database changes were already applied by tenants.0001_add_tenant_system.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('tenants',        '0001_add_tenant_system'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # Remove old unique=True on email
                migrations.AlterField(
                    model_name='user',
                    name='email',
                    field=models.EmailField(max_length=254),
                ),
                # Register the tenant FK in Django's state
                migrations.AddField(
                    model_name='user',
                    name='tenant',
                    field=models.ForeignKey(
                        'tenants.Tenant',
                        db_column='tenant_id',
                        on_delete=models.deletion.PROTECT,
                        related_name='users',
                        # Temporary default — only used by Django state; column
                        # is already NOT NULL in the DB (backfilled by SQL).
                        default=None,
                        null=False,
                    ),
                    preserve_default=False,
                ),
                # Register the composite unique constraint
                migrations.AddConstraint(
                    model_name='user',
                    constraint=models.UniqueConstraint(
                        fields=['tenant', 'email'],
                        name='users_tenant_email_unique',
                    ),
                ),
            ],
            database_operations=[],   # DB already updated by tenants.0001
        ),
    ]
