import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0004_remove_tenant_default_template'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('quotations', '0010_seed_quotation_templates'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='quotation',
            name='template',
        ),
        migrations.DeleteModel(
            name='QuotationTemplate',
        ),
        migrations.CreateModel(
            name='QuotationTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('business_name', models.CharField(max_length=200)),
                ('tagline', models.CharField(blank=True, max_length=200)),
                ('logo_url', models.URLField(blank=True)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('offices', models.CharField(blank=True, max_length=300)),
                ('primary_color', models.CharField(default='#1a6b4a', max_length=7)),
                ('accent_color', models.CharField(default='#ffffff', max_length=7)),
                ('footer_text', models.CharField(blank=True, max_length=300)),
                ('sections_config', models.JSONField(default=list)),
                ('pricing_style', models.CharField(
                    choices=[
                        ('simple_total', 'Simple total'),
                        ('tax_table', 'Tax table'),
                        ('per_head', 'Per head'),
                    ],
                    default='simple_total',
                    max_length=20,
                )),
                ('tax_percent', models.DecimalField(decimal_places=1, default=5.0, max_digits=4)),
                ('advance_percent', models.DecimalField(decimal_places=1, default=50.0, max_digits=4)),
                ('special_notes', models.JSONField(default=list)),
                ('terms_clauses', models.JSONField(default=list)),
                ('setup_fee_paid', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=False)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                (
                    'configured_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'tenant',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='quote_template',
                        to='tenants.tenant',
                    ),
                ),
            ],
            options={
                'db_table': 'quotation_templates',
            },
        ),
        migrations.AddField(
            model_name='quotation',
            name='template',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='quotations',
                to='quotations.quotationtemplate',
            ),
        ),
    ]
