"""Unify QuotationTemplate with builder data; drop BuilderQuotationTemplate."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_quotation_templates(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    for t in QuotationTemplate.objects.all():
        bf = []
        if not (t.name or '').strip():
            bf.append('name')
            t.name = (t.business_name or 'Template')[:200]
        if not t.pages_schema and getattr(t, 'sections_config', None) is not None:
            bf.append('pages_schema')
            t.pages_schema = t.sections_config if isinstance(t.sections_config, list) else []
        if not t.created_by_id and t.configured_by_id:
            bf.append('created_by_id')
            t.created_by_id = t.configured_by_id
        if bf:
            t.save(update_fields=list(set(bf)))


def copy_builder_rows(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    BuilderQuotationTemplate = apps.get_model('quotations', 'BuilderQuotationTemplate')

    def defaults_from_tenant(tenant_id):
        q = QuotationTemplate.objects.filter(tenant_id=tenant_id).first()
        if not q:
            return {
                'business_name': '',
                'tagline': '',
                'logo_url': '',
                'phone': '',
                'offices': '',
                'primary_color': '#1a6b4a',
                'accent_color': '#ffffff',
                'footer_text': '',
                'pricing_style': 'simple_total',
                'tax_percent': 5.0,
                'advance_percent': 50.0,
                'special_notes': [],
                'terms_clauses': [],
                'setup_fee_paid': False,
                'activated_at': None,
                'configured_by_id': None,
                'cover_image_url': '',
                'font_family': '',
                'about_text': '',
                'gallery_images': [],
                'background_color': '#ffffff',
                'payment_terms': '',
                'cover_elements': [],
                'since_year': '2013',
            }
        return {
            'business_name': q.business_name,
            'tagline': q.tagline or '',
            'logo_url': q.logo_url or '',
            'phone': q.phone or '',
            'offices': q.offices or '',
            'primary_color': q.primary_color,
            'accent_color': q.accent_color,
            'footer_text': q.footer_text or '',
            'pricing_style': q.pricing_style,
            'tax_percent': q.tax_percent,
            'advance_percent': q.advance_percent,
            'special_notes': q.special_notes or [],
            'terms_clauses': q.terms_clauses or [],
            'setup_fee_paid': q.setup_fee_paid,
            'activated_at': q.activated_at,
            'configured_by_id': q.configured_by_id,
            'cover_image_url': q.cover_image_url or '',
            'font_family': q.font_family or '',
            'about_text': q.about_text or '',
            'gallery_images': q.gallery_images or [],
            'background_color': q.background_color or '#ffffff',
            'payment_terms': q.payment_terms or '',
            'cover_elements': q.cover_elements or [],
            'since_year': q.since_year or '2013',
        }

    for b in BuilderQuotationTemplate.objects.all():
        if QuotationTemplate.objects.filter(pk=b.pk).exists():
            continue
        d = defaults_from_tenant(b.tenant_id)
        nm = b.name
        if QuotationTemplate.objects.filter(tenant_id=b.tenant_id, name=nm).exists():
            nm = f'{nm} (layout)'
        QuotationTemplate.objects.create(
            id=b.id,
            created_at=b.created_at,
            updated_at=b.updated_at,
            is_deleted=b.is_deleted,
            deleted_at=b.deleted_at,
            tenant_id=b.tenant_id,
            name=nm,
            level=b.level,
            pages_schema=b.pages_schema or [],
            is_active=b.is_active,
            created_by_id=b.created_by_id,
            **d,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('quotations', '0022_remove_quotation_builder_migration_history'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationtemplate',
            name='name',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='level',
            field=models.CharField(
                choices=[('premium', 'Premium'), ('standard', 'Standard'), ('simple', 'Simple')],
                default='standard',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='pages_schema',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='quotationtemplate',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='quotation_templates_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(forwards_quotation_templates, noop),
        migrations.AlterField(
            model_name='quotationtemplate',
            name='tenant',
            field=models.ForeignKey(
                db_column='tenant_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='quotation_templates',
                to='tenants.tenant',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='quotationtemplate',
            unique_together={('tenant', 'name')},
        ),
        migrations.RunPython(copy_builder_rows, noop),
        migrations.AlterField(
            model_name='builderquotation',
            name='template',
            field=models.ForeignKey(
                blank=True,
                db_column='builder_template_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='canvas_quotations',
                to='quotations.quotationtemplate',
            ),
        ),
        migrations.DeleteModel(
            name='BuilderQuotationTemplate',
        ),
        migrations.RemoveField(
            model_name='quotationtemplate',
            name='sections_config',
        ),
    ]
