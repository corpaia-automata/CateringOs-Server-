# CharField ``default_template`` + FK ``default_quotation_template`` (replaces legacy FK-only 0003 + 0004).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0001_initial'),
        ('tenants', '0004_remove_tenant_default_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='default_template',
            field=models.CharField(
                choices=[
                    ('classic', 'Classic'),
                    ('premium', 'Premium'),
                    ('minimal', 'Minimal'),
                ],
                default='classic',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='tenant',
            name='default_quotation_template',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='default_for_tenants',
                to='quotations.quotationtemplate',
            ),
        ),
    ]
