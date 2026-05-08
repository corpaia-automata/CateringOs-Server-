"""Presentation helpers for Django quotation templates."""

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _indian_group_intdigits(digits: str) -> str:
    """Group digits Indian-style: last 3, then pairs (e.g. 200000 -> 2,00,000)."""
    digits = digits.strip()
    if not digits.lstrip('-').isdigit():
        return digits
    neg = digits.startswith('-')
    core = digits[1:] if neg else digits
    if len(core) <= 3:
        grouped = core
    else:
        last_three = core[-3:]
        rest = core[:-3]
        chunks = []
        while rest:
            chunks.insert(0, rest[-2:])
            rest = rest[:-2]
        grouped = ','.join(chunks + [last_three])
    return f'-{grouped}' if neg else grouped


@register.filter(name='indian_currency')
def indian_currency(value, currency_prefix='Rs.'):
    """
    Format a number with Indian comma grouping and a rupee prefix.
    Example: 200000 -> Rs. 2,00,000
    """
    if value is None or value == '':
        return ''
    try:
        dec = Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    sign = '-' if dec < 0 else ''
    dec = abs(dec)
    int_part, frac_part = format(dec, 'f').split('.')
    grouped = _indian_group_intdigits(int_part)
    # Omit .00 for whole amounts
    frac = int(frac_part)
    body = grouped if frac == 0 else f'{grouped}.{frac_part}'
    prefix = (currency_prefix + ' ') if currency_prefix else ''
    return f'{sign}{prefix}{body}'.strip()


@register.filter(name='pax_display')
def pax_display(value, suffix='Pax'):
    """Example: 1500 -> 1,500 Pax (uses Western grouping for headcount)."""
    if value is None or value == '':
        return ''
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    txt = f'{n:,}'
    return f'{txt} {suffix}'.strip()


def _status_style(status: str) -> tuple[str, str]:
    key = (status or '').strip().lower()
    mapping = {
        'draft': ('#64748b', '#f1f5f9'),
        'sent': ('#1d4ed8', '#dbeafe'),
        'viewed': ('#7c3aed', '#ede9fe'),
        'accepted': ('#166534', '#dcfce7'),
        'rejected': ('#b91c1c', '#fee2e2'),
    }
    if key in mapping:
        return mapping[key]
    u = (status or '').strip().upper()
    legacy_upper = {
        'DRAFT': ('#64748b', '#f1f5f9'),
        'SENT': ('#1d4ed8', '#dbeafe'),
        'ACCEPTED': ('#166534', '#dcfce7'),
        'REJECTED': ('#b91c1c', '#fee2e2'),
    }
    return legacy_upper.get(u, ('#334155', '#f8fafc'))


@register.simple_tag
def quotation_status_badge(quotation):
    """Render a styled span for a quotation ``status``."""
    if quotation is None:
        return mark_safe('')
    raw = getattr(quotation, 'status', '') or ''
    try:
        label = quotation.get_status_display()
    except Exception:
        label = str(raw).replace('_', ' ').title()
    bg, fg = _status_style(str(raw))
    html = (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:999px;'
        f'font-size:12px;font-weight:600;background:{bg};color:{fg};">{label}</span>'
    )
    return mark_safe(html)


@register.inclusion_tag('quotations/tags/quotation_activity_log.html')
def quotation_activity_log(quotation, limit=50):
    """Timeline when ``quotation`` exposes ``activities`` (optional)."""
    activities = []
    if quotation is not None and hasattr(quotation, 'activities'):
        activities = list(quotation.activities.select_related('created_by').all()[:limit])
    return {'activities': activities, 'quotation': quotation}
