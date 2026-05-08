# Generated manually for QuotationTemplate OneToOne on tenant — removes legacy FK.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_tenant_default_template'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tenant',
            name='default_template',
        ),
    ]
