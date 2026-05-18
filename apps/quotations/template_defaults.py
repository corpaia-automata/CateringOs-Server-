"""
Default ``QuotationTemplate`` rows per tenant; ``Tenant.default_quotation_template`` stays aligned
with ``Tenant.default_template`` (CharField). No ``slug`` on templates — ``template_type`` is the key.
"""

from __future__ import annotations

import logging
import uuid

from django.db import IntegrityError, transaction

from apps.quotations.models import QuotationTemplate, TemplateType
from apps.tenants.models import Tenant
from shared.db_schema import column_on_db, filter_kwargs_for_model, queryset_for_db

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_NAMES: dict[TemplateType, str] = {
    TemplateType.CLASSIC: 'Classic',
    TemplateType.PREMIUM: 'Premium',
    TemplateType.MINIMAL: 'Minimal',
}

SECTIONS_CONFIG_DEFAULT: dict = {
    'sections': [
        {'id': 'cover', 'enabled': True, 'order': 1},
        {'id': 'about', 'enabled': True, 'order': 2},
        {'id': 'why_us', 'enabled': False, 'order': 3},
        {'id': 'event_details', 'enabled': True, 'order': 4},
        {'id': 'menu', 'enabled': True, 'order': 5},
        {'id': 'services', 'enabled': True, 'order': 6},
        {'id': 'pricing', 'enabled': True, 'order': 7},
        {'id': 'terms', 'enabled': True, 'order': 8},
    ]
}

TEMPLATE_SCHEMA_BY_TYPE: dict[str, dict] = {
    'classic': {
        'spacing': 'comfortable',
        'menu_layout': 'table',
        'show_item_quantities': True,
        'show_complimentary_tags': True,
        'pricing_style': 'summary_box',
        'cover_style': 'full_bleed',
        'show_page_numbers': True,
        'footer_text': 'Thank you for considering us.',
    },
    'premium': {
        'spacing': 'spacious',
        'menu_layout': 'cards',
        'show_item_quantities': True,
        'show_complimentary_tags': True,
        'pricing_style': 'highlight_box',
        'cover_style': 'full_bleed',
        'show_page_numbers': True,
        'footer_text': 'We look forward to serving you.',
    },
    'minimal': {
        'spacing': 'compact',
        'menu_layout': 'list',
        'show_item_quantities': False,
        'show_complimentary_tags': False,
        'pricing_style': 'inline',
        'cover_style': 'none',
        'show_page_numbers': False,
        'footer_text': '',
    },
}


def _allowed_template_type_values() -> set[str]:
    return {c[0] for c in TemplateType.choices}


def coerce_tenant_default_template_type(value: str | None) -> str:
    """Return a valid ``TemplateType`` value; ``classic`` if missing or invalid."""
    if not value:
        return TemplateType.CLASSIC
    v = str(value).strip().lower()
    if v in ('standard', 'std'):
        v = 'classic'
    if v in _allowed_template_type_values():
        return v
    return TemplateType.CLASSIC


def _row_defaults(tenant: Tenant, template_type: str) -> dict:
    business_name = (tenant.name or '').strip() or 'Your catering business'
    schema = TEMPLATE_SCHEMA_BY_TYPE.get(template_type, TEMPLATE_SCHEMA_BY_TYPE['classic'])
    raw = {
        'template_type': template_type,
        'business_name': business_name,
        'tagline': '',
        'company_tagline': '',
        'logo_url': '',
        'phone': '',
        'offices': '',
        'primary_color': '#1A1A1A',
        'accent_color': '#C9A84C',
        'footer_text': '',
        'pricing_style': 'simple_total',
        'tax_percent': 5.0,
        'advance_percent': 50.0,
        'special_notes': [],
        'terms_clauses': [],
        'setup_fee_paid': False,
        'is_active': False,
        'is_default': False,
        'activated_at': None,
        'configured_by': None,
        'created_by': None,
        'cover_image_url': '',
        'font_family': '',
        'font_heading': 'Playfair Display',
        'font_body': 'Inter',
        'about_text': '',
        'why_choose_us': '',
        'gallery_images': [],
        'background_color': '#ffffff',
        'payment_terms': '',
        'cover_elements': [],
        'since_year': '2013',
        'sections_config': SECTIONS_CONFIG_DEFAULT,
        'template_schema': schema,
        'is_deleted': False,
        'deleted_at': None,
    }
    return filter_kwargs_for_model(QuotationTemplate, raw)


def _template_qs(*, all_objects: bool = False):
    mgr = QuotationTemplate.all_objects if all_objects else QuotationTemplate.objects
    return queryset_for_db(QuotationTemplate, mgr)


def get_or_create_default_template(tenant: Tenant, template_type: str) -> QuotationTemplate:
    """
    Return a non-deleted ``QuotationTemplate`` for ``template_type`` (creates / restores row if needed).
    Never raises — falls back to classic, then last-resort create/fetch.
    """
    tt = coerce_tenant_default_template_type(template_type)
    name = DEFAULT_TEMPLATE_NAMES[TemplateType(tt)]
    defaults = _row_defaults(tenant, tt)

    def _fetch(*, include_deleted: bool = False) -> QuotationTemplate | None:
        qs = _template_qs(all_objects=include_deleted).filter(tenant_id=tenant.pk, name=name)
        if column_on_db(QuotationTemplate, 'is_deleted') and not include_deleted:
            qs = qs.filter(is_deleted=False)
        return qs.order_by('-updated_at').first()

    try:
        obj, _ = _template_qs(all_objects=True).update_or_create(
            tenant_id=tenant.pk,
            name=name,
            defaults=defaults,
        )
        got = _template_qs().filter(pk=obj.pk)
        if column_on_db(QuotationTemplate, 'is_deleted'):
            got = got.filter(is_deleted=False)
        got = got.first()
        if got is not None:
            return got
    except Exception:
        logger.exception(
            'get_or_create_default_template update_or_create failed tenant=%s type=%s',
            tenant.pk,
            tt,
        )

    existing = _fetch()
    if existing is not None:
        return existing

    if tt != TemplateType.CLASSIC:
        return get_or_create_default_template(tenant, TemplateType.CLASSIC)

    try:
        return _template_qs(all_objects=True).create(tenant=tenant, name=name, **defaults)
    except IntegrityError:
        row = _template_qs(all_objects=True).filter(tenant_id=tenant.pk, name=name).first()
        if row is not None:
            _template_qs(all_objects=True).filter(pk=row.pk).update(**defaults)
            refreshed = _template_qs().filter(pk=row.pk)
            if column_on_db(QuotationTemplate, 'is_deleted'):
                refreshed = refreshed.filter(is_deleted=False)
            refreshed = refreshed.first()
            if refreshed is not None:
                return refreshed
        logger.exception('get_or_create_default_template integrity fallback failed tenant=%s', tenant.pk)
    except Exception:
        logger.exception('get_or_create_default_template bare create failed tenant=%s', tenant.pk)

    row = _template_qs(all_objects=True).filter(tenant_id=tenant.pk, name=name).first()
    if row is not None:
        return row
    alt_qs = _template_qs(all_objects=True).filter(tenant_id=tenant.pk)
    if column_on_db(QuotationTemplate, 'is_deleted'):
        alt_qs = alt_qs.filter(is_deleted=False)
    alt = alt_qs.first()
    if alt is not None:
        return alt
    cname = DEFAULT_TEMPLATE_NAMES[TemplateType.CLASSIC]
    cdef = _row_defaults(tenant, TemplateType.CLASSIC)
    try:
        return _template_qs(all_objects=True).create(tenant=tenant, name=cname, **cdef)
    except IntegrityError:
        last = _template_qs(all_objects=True).filter(tenant_id=tenant.pk, name=cname).first()
        if last is not None:
            return last
    last_any = _template_qs(all_objects=True).filter(tenant_id=tenant.pk).first()
    if last_any is not None:
        return last_any
    boot = f'Bootstrap-{uuid.uuid4().hex[:12]}'
    return _template_qs(all_objects=True).create(
        tenant=tenant,
        name=boot[:200],
        **_row_defaults(tenant, TemplateType.CLASSIC),
    )


def sync_default_quotation_templates_for_tenant(tenant: Tenant) -> None:
    """Ensure Classic / Premium / Minimal rows exist (management commands, ops)."""
    for ttm in TemplateType:
        get_or_create_default_template(tenant, ttm.value)


def ensure_tenant_default_quotation_template_fk(tenant: Tenant) -> QuotationTemplate:
    """
    Single source of truth: ``default_quotation_template`` always matches ``default_template`` (CharField).
    Auto-corrects mismatches, missing FK, or deleted FK targets. Never raises.
    """
    refresh_fields = ['default_template']
    if column_on_db(Tenant, 'default_quotation_template'):
        refresh_fields.append('default_quotation_template')
    tenant.refresh_from_db(fields=refresh_fields)
    desired = coerce_tenant_default_template_type(tenant.default_template)
    if tenant.default_template != desired:
        Tenant.objects.filter(pk=tenant.pk).update(default_template=desired)
        tenant.default_template = desired

    fk = None
    if column_on_db(Tenant, 'default_quotation_template') and tenant.default_quotation_template_id:
        fk = _template_qs(all_objects=True).filter(pk=tenant.default_quotation_template_id).first()

    fk_deleted = getattr(fk, 'is_deleted', False) if fk is not None else False
    aligned = (
        fk is not None
        and fk.tenant_id == tenant.pk
        and not fk_deleted
        and fk.template_type == desired
    )
    if aligned:
        expected_tpl = fk
    else:
        expected_tpl = get_or_create_default_template(tenant, desired)
        if expected_tpl is None:
            expected_tpl = get_or_create_default_template(tenant, TemplateType.CLASSIC)

    if expected_tpl is None:
        expected_tpl = get_or_create_default_template(tenant, TemplateType.CLASSIC)

    with transaction.atomic():
        if column_on_db(QuotationTemplate, 'is_default'):
            clear_qs = _template_qs().filter(tenant_id=tenant.pk).exclude(pk=expected_tpl.pk)
            if column_on_db(QuotationTemplate, 'is_deleted'):
                clear_qs = clear_qs.filter(is_deleted=False)
            clear_qs.update(is_default=False)
            if not getattr(expected_tpl, 'is_default', False):
                _template_qs().filter(pk=expected_tpl.pk).update(is_default=True)
                expected_tpl.is_default = True

        tenant_update = {'default_template': desired}
        if column_on_db(Tenant, 'default_quotation_template'):
            tenant_update['default_quotation_template'] = expected_tpl
        Tenant.objects.filter(pk=tenant.pk).update(**tenant_update)

    tenant.default_template = desired
    if column_on_db(Tenant, 'default_quotation_template'):
        tenant.default_quotation_template = expected_tpl
    return expected_tpl


def assign_tenant_default_quotation_template(tenant: Tenant) -> None:
    """Back-compat alias for code paths that only need side effects on the tenant row."""
    ensure_tenant_default_quotation_template_fk(tenant)


def resolve_default_quotation_template_row(tenant: Tenant) -> QuotationTemplate:
    """Return the tenant default template row; provisions and aligns FK if needed (never raises)."""
    tpl = ensure_tenant_default_quotation_template_fk(tenant)
    if tpl is not None:
        return tpl
    return get_or_create_default_template(tenant, TemplateType.CLASSIC)


def ensure_quotation_template_for_new_quote(
    tenant: Tenant,
    explicit: QuotationTemplate | None,
) -> QuotationTemplate:
    """Pick template for a new quotation; never returns ``None``."""
    if explicit is not None and not explicit.is_deleted and str(explicit.tenant_id) == str(tenant.pk):
        return explicit
    return ensure_tenant_default_quotation_template_fk(tenant)
