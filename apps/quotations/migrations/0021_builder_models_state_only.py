# Builder DB tables were created under the removed ``quotation_builder`` app.
# This migration only updates Django's model state to point at ``quotations``.

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0020_remove_quotationtemplate_tier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0004_remove_tenant_default_template'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='BuilderQuotationTemplate',
                    fields=[
                        (
                            'id',
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('is_deleted', models.BooleanField(default=False)),
                        ('deleted_at', models.DateTimeField(blank=True, null=True)),
                        ('name', models.CharField(max_length=200)),
                        (
                            'level',
                            models.CharField(
                                choices=[
                                    ('premium', 'Premium'),
                                    ('standard', 'Standard'),
                                    ('simple', 'Simple'),
                                ],
                                default='standard',
                                max_length=20,
                            ),
                        ),
                        ('pages_schema', models.JSONField(blank=True, default=list)),
                        ('is_active', models.BooleanField(default=True)),
                        (
                            'created_by',
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='builder_quotation_templates_created',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            'tenant',
                            models.ForeignKey(
                                db_column='tenant_id',
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='builder_quotation_templates',
                                to='tenants.tenant',
                            ),
                        ),
                    ],
                    options={
                        'db_table': 'builder_quotation_templates',
                        'ordering': ['tenant_id', 'name'],
                        'unique_together': {('tenant', 'name')},
                    },
                ),
                migrations.CreateModel(
                    name='BuilderMenuCategory',
                    fields=[
                        (
                            'id',
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('is_deleted', models.BooleanField(default=False)),
                        ('deleted_at', models.DateTimeField(blank=True, null=True)),
                        ('name', models.CharField(max_length=200)),
                        ('order', models.PositiveIntegerField(default=0)),
                        ('is_active', models.BooleanField(default=True)),
                        (
                            'tenant',
                            models.ForeignKey(
                                db_column='tenant_id',
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='builder_menu_categories',
                                to='tenants.tenant',
                            ),
                        ),
                    ],
                    options={
                        'db_table': 'builder_menu_categories',
                        'ordering': ['tenant_id', 'order', 'name'],
                        'unique_together': {('tenant', 'name')},
                    },
                ),
                migrations.CreateModel(
                    name='BuilderMenuItem',
                    fields=[
                        (
                            'id',
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('is_deleted', models.BooleanField(default=False)),
                        ('deleted_at', models.DateTimeField(blank=True, null=True)),
                        ('name', models.CharField(max_length=255)),
                        ('default_unit', models.CharField(default='portion', max_length=40)),
                        ('is_compliment', models.BooleanField(default=False)),
                        ('is_live_counter', models.BooleanField(default=False)),
                        ('order', models.PositiveIntegerField(default=0)),
                        ('is_active', models.BooleanField(default=True)),
                        (
                            'category',
                            models.ForeignKey(
                                db_column='builder_menu_category_id',
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='items',
                                to='quotations.buildermenucategory',
                            ),
                        ),
                        (
                            'tenant',
                            models.ForeignKey(
                                db_column='tenant_id',
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='builder_menu_items',
                                to='tenants.tenant',
                            ),
                        ),
                    ],
                    options={
                        'db_table': 'builder_menu_items',
                        'ordering': ['tenant_id', 'category_id', 'order', 'name'],
                    },
                ),
                migrations.CreateModel(
                    name='BuilderQuotation',
                    fields=[
                        (
                            'id',
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('is_deleted', models.BooleanField(default=False)),
                        ('deleted_at', models.DateTimeField(blank=True, null=True)),
                        (
                            'qnum',
                            models.CharField(blank=True, db_index=True, editable=False, max_length=40),
                        ),
                        (
                            'level',
                            models.CharField(
                                choices=[
                                    ('premium', 'Premium'),
                                    ('standard', 'Standard'),
                                    ('simple', 'Simple'),
                                ],
                                default='standard',
                                max_length=20,
                            ),
                        ),
                        ('client_name', models.CharField(max_length=255)),
                        ('client_phone', models.CharField(blank=True, max_length=40)),
                        ('client_email', models.EmailField(blank=True, max_length=254)),
                        ('client_address', models.TextField(blank=True)),
                        ('event_date', models.DateField(blank=True, null=True)),
                        ('quotation_date', models.DateField(blank=True, null=True)),
                        ('pax', models.PositiveIntegerField(blank=True, null=True)),
                        ('venue', models.CharField(blank=True, max_length=500)),
                        ('ceremony', models.CharField(blank=True, max_length=200)),
                        ('service_type', models.CharField(blank=True, max_length=200)),
                        ('pages_data', models.JSONField(blank=True, default=dict)),
                        (
                            'subtotal',
                            models.DecimalField(
                                decimal_places=2,
                                default=Decimal('0.00'),
                                max_digits=12,
                            ),
                        ),
                        (
                            'tax_pct',
                            models.DecimalField(
                                decimal_places=2,
                                default=Decimal('0.00'),
                                max_digits=6,
                            ),
                        ),
                        (
                            'tax_amount',
                            models.DecimalField(
                                decimal_places=2,
                                default=Decimal('0.00'),
                                max_digits=12,
                            ),
                        ),
                        (
                            'advance_amount',
                            models.DecimalField(
                                decimal_places=2,
                                default=Decimal('0.00'),
                                max_digits=12,
                            ),
                        ),
                        (
                            'total_amount',
                            models.DecimalField(
                                decimal_places=2,
                                default=Decimal('0.00'),
                                max_digits=12,
                            ),
                        ),
                        ('extra_charges', models.JSONField(blank=True, default=list)),
                        (
                            'status',
                            models.CharField(
                                choices=[
                                    ('draft', 'Draft'),
                                    ('sent', 'Sent'),
                                    ('viewed', 'Viewed'),
                                    ('accepted', 'Accepted'),
                                    ('rejected', 'Rejected'),
                                ],
                                default='draft',
                                max_length=20,
                            ),
                        ),
                        ('notes', models.TextField(blank=True)),
                        (
                            'created_by',
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='builder_quotations_created',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            'tenant',
                            models.ForeignKey(
                                db_column='tenant_id',
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name='builder_quotations',
                                to='tenants.tenant',
                            ),
                        ),
                        (
                            'template',
                            models.ForeignKey(
                                blank=True,
                                db_column='builder_template_id',
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='builder_quotations',
                                to='quotations.builderquotationtemplate',
                            ),
                        ),
                    ],
                    options={
                        'db_table': 'builder_quotations',
                        'ordering': ['-created_at'],
                        'unique_together': {('tenant', 'qnum')},
                    },
                ),
                migrations.CreateModel(
                    name='BuilderQuotationActivity',
                    fields=[
                        (
                            'id',
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ('action', models.CharField(max_length=100)),
                        ('description', models.TextField(blank=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        (
                            'created_by',
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='builder_quotation_activities',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            'quotation',
                            models.ForeignKey(
                                db_column='builder_quotation_id',
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='activities',
                                to='quotations.builderquotation',
                            ),
                        ),
                    ],
                    options={
                        'db_table': 'builder_quotation_activities',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
