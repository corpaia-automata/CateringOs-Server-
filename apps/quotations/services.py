"""
Quotation rendering context for `templates/quotation/quotation.html`.
"""
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone

TAX_RATE = Decimal('0.10')


def _money_str(value: Decimal) -> str:
    q = value.quantize(Decimal('0.01'))
    return f'{q:,.2f}'


def _qty_str(value: Decimal) -> str:
    q = value.quantize(Decimal('0.0001')).normalize()
    return format(q, 'f') if q == q.to_integral() else format(q, '.4f').rstrip('0').rstrip('.')


def _abs_media_url(path: str) -> str:
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    base = str(getattr(settings, 'PUBLIC_BASE_URL', '') or '').rstrip('/')
    if base:
        return f'{base}{path}' if path.startswith('/') else f'{base}/{path}'
    return path


def _decimal_val(v) -> Decimal:
    if v is None:
        return Decimal('0')
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


def next_quote_number(tenant_id) -> str:
    """Sequential QTN-00001 style per tenant (matches legacy seed migration)."""
    from apps.quotations.models import Quotation

    nums: list[int] = []
    for qn in Quotation.all_objects.filter(tenant_id=tenant_id).values_list('quote_number', flat=True):
        if not qn:
            continue
        if qn.startswith('QTN-') and qn[5:].isdigit():
            nums.append(int(qn[5:], 10))
    n = (max(nums) if nums else 0) + 1
    return f'QTN-{str(n).zfill(5)}'


def next_reference_number(tenant_id) -> str:
    """Deprecated alias — use :func:`next_quote_number`."""
    return next_quote_number(tenant_id)


def build_quotation_context(quotation) -> dict[str, Any]:
    """
    Context for `quotation/quotation.html` — flat pre-formatted values only, no raw model objects.

    Branding priority: template_snapshot → BrandingProfile for tenant → empty string.
    Tax priority:      template_snapshot.tax_percent → live QuotationTemplate.tax_percent → 10%.
    """
    snap = quotation.template_snapshot if isinstance(quotation.template_snapshot, dict) else {}

    # ── Branding fallback: snapshot → BrandingProfile → defaults ──────────────
    bp = None
    try:
        from apps.quotations.models import BrandingProfile
        bp = BrandingProfile.objects.filter(tenant_id=quotation.tenant_id).first()
    except Exception:
        pass

    def _s(snap_key: str, bp_attr: str = '', default: str = '') -> str:
        v = snap.get(snap_key)
        if v:
            return str(v).strip()
        if bp and bp_attr:
            bv = getattr(bp, bp_attr, None)
            if bv:
                return str(bv).strip()
        return default

    def _logo() -> str:
        v = snap.get('logo_url')
        if v:
            return _abs_media_url(str(v))
        if bp and bp.logo:
            try:
                return _abs_media_url(bp.logo.url)
            except Exception:
                pass
        return ''

    business_name = _s('business_name', 'business_name')
    primary_color = _s('primary_color', 'primary_color', '#1A1A1A')
    accent_color  = _s('accent_color',  'accent_color',  '#C9A84C')
    brand_phone   = _s('phone',         'phone')
    brand_email   = _s('email',         'email')
    footer_text   = _s('footer_text',   'footer_text')
    tagline       = _s('tagline')
    cover_image_url = _abs_media_url(str(snap.get('cover_image_url') or ''))
    logo_url      = _logo()

    # ── Tax rate: snapshot → live template → 10% ──────────────────────────────
    tax_percent_raw = snap.get('tax_percent')
    if tax_percent_raw is None and getattr(quotation, 'template_id', None):
        try:
            from apps.quotations.models import QuotationTemplate
            row = QuotationTemplate.objects.filter(pk=quotation.template_id).values('tax_percent').first()
            if row:
                tax_percent_raw = row['tax_percent']
        except Exception:
            pass
    try:
        tax_rate = Decimal(str(tax_percent_raw)) / Decimal('100') if tax_percent_raw is not None else TAX_RATE
    except Exception:
        tax_rate = TAX_RATE
    tax_percent_str = str((tax_rate * 100).quantize(Decimal('0.1')).normalize())

    # ── Line items ─────────────────────────────────────────────────────────────
    # Path A: quotation.line_items has priced rows → use them (manual quotations).
    # Path B: quotation.menu_dishes + menu_services → build from menu data (fallback).
    # Stored model totals always override recomputed values when non-zero.

    _LI_CATS = {'food', 'drink', 'service', 'other'}

    li_groups: dict[str, list[dict[str, str]]] = {
        'food': [], 'drink': [], 'service': [], 'other': [],
    }
    li_subtotal = Decimal('0')

    for row in (quotation.line_items or []):
        if not isinstance(row, dict):
            continue
        qty   = _decimal_val(row.get('quantity'))
        price = _decimal_val(row.get('unit_price') or row.get('price'))
        line_total = (qty * price).quantize(Decimal('0.01'))
        li_subtotal += line_total
        cat = str(row.get('category') or 'other').lower()
        if cat not in _LI_CATS:
            cat = 'other'
        li_groups[cat].append({
            'description':    str(row.get('description') or row.get('name') or ''),
            'quantity_str':   _qty_str(qty),
            'unit_price_str': _money_str(price),
            'line_total_str': _money_str(line_total),
            'note':           str(row.get('note') or ''),
        })

    if li_subtotal > 0:
        # Path A — traditional line items have priced rows
        computed_subtotal = li_subtotal.quantize(Decimal('0.01'))
        _use_li = True
    else:
        # Path B — build from menu_dishes (grouped by category) + menu_services
        _use_li = False
        md_groups: dict[str, list[dict[str, str]]] = {}
        md_subtotal = Decimal('0')

        for row in (quotation.menu_dishes or []):
            if not isinstance(row, dict):
                continue
            qty   = _decimal_val(row.get('qty') or row.get('quantity'))
            price = _decimal_val(row.get('rate') or row.get('unit_price'))
            line_total = (
                _decimal_val(row.get('subtotal'))
                if row.get('subtotal')
                else (qty * price).quantize(Decimal('0.01'))
            )
            md_subtotal += line_total
            cat = str(row.get('category') or 'Food').strip() or 'Food'
            if cat not in md_groups:
                md_groups[cat] = []
            note = 'Complimentary' if row.get('is_complimentary') else ''
            md_groups[cat].append({
                'description':    str(row.get('name') or ''),
                'quantity_str':   _qty_str(qty),
                'unit_price_str': _money_str(price),
                'line_total_str': _money_str(line_total),
                'note':           note,
            })

        svc_items: list[dict[str, str]] = []
        for row in (quotation.menu_services or []):
            if not isinstance(row, dict):
                continue
            qty   = _decimal_val(row.get('qty') or row.get('quantity') or 1)
            price = _decimal_val(row.get('rate') or row.get('unit_price'))
            line_total = (
                _decimal_val(row.get('subtotal'))
                if row.get('subtotal')
                else (qty * price).quantize(Decimal('0.01'))
            )
            md_subtotal += line_total
            svc_items.append({
                'description':    str(row.get('name') or ''),
                'quantity_str':   _qty_str(qty),
                'unit_price_str': _money_str(price),
                'line_total_str': _money_str(line_total),
                'note':           '',
            })

        computed_subtotal = md_subtotal.quantize(Decimal('0.01'))

    # ── Pricing: stored model values override recomputed when non-zero ─────────
    stored_sub   = _decimal_val(quotation.subtotal)
    stored_total = _decimal_val(quotation.total_amount)

    subtotal    = (stored_sub if stored_sub > 0 else computed_subtotal).quantize(Decimal('0.01'))
    tax_amount  = (subtotal * tax_rate).quantize(Decimal('0.01'))
    grand_total = (subtotal + tax_amount).quantize(Decimal('0.01'))

    if stored_total > 0:
        grand_total = stored_total.quantize(Decimal('0.01'))
        derived_tax = (grand_total - subtotal).quantize(Decimal('0.01'))
        if derived_tax >= 0:
            tax_amount = derived_tax

    # ── Inquiry fields ─────────────────────────────────────────────────────────
    inquiry = getattr(quotation, 'inquiry', None)
    client_name    = str(getattr(inquiry, 'customer_name',  '') or '') if inquiry else ''
    client_email   = str(getattr(inquiry, 'email',          '') or '') if inquiry else ''
    client_phone   = str(getattr(inquiry, 'contact_number', '') or '') if inquiry else ''
    event_name     = str(getattr(inquiry, 'event_type',     '') or '') if inquiry else ''
    event_location = str(getattr(inquiry, 'venue',          '') or '') if inquiry else ''
    event_date_str = ''
    guest_count_str = ''
    if inquiry:
        td = getattr(inquiry, 'tentative_date', None)
        if td:
            event_date_str = td.strftime('%d %b %Y')
        gc = getattr(inquiry, 'guest_count', None)
        if gc is not None:
            guest_count_str = str(int(gc))

    # ── Valid until: created_at + 15 days ─────────────────────────────────────
    try:
        valid_until_str = (quotation.created_at.date() + timedelta(days=15)).strftime('%d %b %Y')
    except Exception:
        valid_until_str = ''

    # ── Notes / terms ──────────────────────────────────────────────────────────
    notes      = (quotation.notes or '').strip()
    terms_text = (quotation.payment_terms or '').strip()

    # special_notes / terms_clauses from template snapshot (lists) — only if non-empty
    raw_special = snap.get('special_notes')
    special_notes: list = raw_special if isinstance(raw_special, list) and raw_special else []

    raw_clauses = snap.get('terms_clauses')
    terms_clauses: list = raw_clauses if isinstance(raw_clauses, list) and raw_clauses else []

    show_notes       = bool(notes or special_notes)
    show_terms       = bool(terms_text or terms_clauses)
    show_second_page = show_notes or show_terms

    # ── Line item sections ─────────────────────────────────────────────────────
    if _use_li:
        line_item_sections: list[dict[str, Any]] = [
            {'title': title, 'items': li_groups[key]}
            for key, title in (
                ('food',    'Food'),
                ('drink',   'Drink'),
                ('service', 'Service'),
                ('other',   'Other'),
            )
            if li_groups[key]
        ]
    else:
        line_item_sections = [
            {'title': cat, 'items': items}
            for cat, items in md_groups.items()
            if items
        ]
        if svc_items:
            line_item_sections.append({'title': 'Services', 'items': svc_items})

    generated_date_str = timezone.now().strftime('%d %B %Y')

    return {
        # Branding
        'primary_color':   primary_color,
        'accent_color':    accent_color,
        'logo_url':        logo_url,
        'cover_image_url': cover_image_url,
        'business_name':   business_name,
        'brand_phone':     brand_phone,
        'brand_email':     brand_email,
        'footer_text':     footer_text,
        'tagline':         tagline,
        # Client & Event
        'client_name':     client_name,
        'client_email':    client_email,
        'client_phone':    client_phone,
        'event_name':      event_name,
        'event_date_str':  event_date_str,
        'event_location':  event_location,
        'guest_count_str': guest_count_str,
        # Line items
        'line_item_sections': line_item_sections,
        # Pricing
        'subtotal_str':        _money_str(subtotal),
        'tax_amount_str':      _money_str(tax_amount),
        'tax_percent_str':     tax_percent_str,
        'grand_total_str':     _money_str(grand_total),
        'service_charge_str':  _money_str(_decimal_val(quotation.service_charge)),
        'advance_amount_str':  _money_str(_decimal_val(quotation.advance_amount)),
        'balance_due_str':     _money_str(
            max(Decimal('0'), grand_total - _decimal_val(quotation.advance_amount)).quantize(Decimal('0.01'))
        ),
        'valid_until_str':  valid_until_str,
        # Meta
        'reference_number':  quotation.quote_number or '',
        'generated_date_str': generated_date_str,
        # Conditional flags
        'show_notes':       show_notes,
        'show_terms':       show_terms,
        'show_second_page': show_second_page,
        'notes':            notes,
        'terms_text':       terms_text,
        'special_notes':    special_notes,
        'terms_clauses':    terms_clauses,
    }


# ─── Grocery sheet (aggregated recipe quantities for a quotation menu) ─────────

_FIXED_ING_CATEGORIES = frozenset({'rental', 'rentals', 'other', 'others'})


def _is_fixed_charge_ingredient_category(raw) -> bool:
    k = str(raw or '').strip().lower()
    return k in _FIXED_ING_CATEGORIES


def _dec(v, default='0'):
    try:
        return Decimal(str(v)) if v not in (None, '') else Decimal(default)
    except Exception:
        return Decimal(default)


def _norm_sheet_category(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return 'Other'
    parts = (
        raw.lower()
        .replace('_', ' ')
        .replace('-', ' ')
        .split()
    )
    if not parts:
        return 'Other'
    return ' '.join((p[:1].upper() + p[1:]) if p else '' for p in parts)


def _recipe_line_unit_rate(line_unit: str, ingredient_uom: str, unit_cost_snapshot) -> Decimal:
    line_unit = (line_unit or '').lower()
    ing_uom = (ingredient_uom or '').lower()
    snap = _dec(unit_cost_snapshot)
    bulk_small = (
        (line_unit in ('g', 'gram') and ing_uom == 'kg')
        or (
            line_unit in ('ml', 'millilitre', 'milliliter')
            and ing_uom in ('litre', 'liter', 'ltr')
        )
    )
    return (snap / Decimal('1000')) if bulk_small else snap


def build_grocery_sheet_payload(quotation, tenant_id) -> dict[str, Any]:
    """
    Roll up master recipe lines for each menu dish into grocery list items.
    Mirrors frontend `recipeCostRowsFromApi` scaling (fixed vs per-portion ingredients).
    """
    from apps.inquiries.models import Inquiry
    from apps.master.models import Dish, DishRecipe

    menu = quotation.menu_dishes or []
    if not isinstance(menu, list):
        menu = []

    client_name = ''
    event_date = None
    total_guests = None
    if quotation.inquiry_id:
        inv = (
            Inquiry.objects.filter(pk=quotation.inquiry_id, tenant_id=tenant_id)
            .only('customer_name', 'tentative_date', 'guest_count')
            .first()
        )
        if inv:
            client_name = inv.customer_name or ''
            event_date = inv.tentative_date
            total_guests = inv.guest_count

    # key -> { name, unit, category, qty, amount (qty * rate) }
    cells: dict[tuple, dict] = {}

    for row in menu:
        if not isinstance(row, dict):
            continue
        dish_id = row.get('id')
        if not dish_id:
            continue
        dish = Dish.objects.filter(pk=dish_id, tenant_id=tenant_id).first()
        if not dish:
            continue

        dish_qty = _dec(row.get('qty'))
        batch_size = _dec(
            row.get('batch_size') or row.get('base_recipe_qty') or dish.batch_size,
            '1',
        )
        if batch_size <= 0:
            batch_size = Decimal('1')

        lines = (
            DishRecipe.objects.filter(dish=dish, ingredient__isnull=False)
            .select_related('ingredient')
        )
        for line in lines:
            ing = line.ingredient
            if not ing:
                continue
            raw_cat = str(ing.category or '').strip()
            scale = Decimal('1') if _is_fixed_charge_ingredient_category(raw_cat) else (
                dish_qty / batch_size
            )
            qty_scaled = scale * _dec(line.qty_per_unit)
            rate = _recipe_line_unit_rate(
                line.unit or '',
                ing.unit_of_measure,
                line.unit_cost_snapshot,
            )
            name = ing.name or ''
            unit = line.unit or ing.unit_of_measure or 'unit'
            cat = _norm_sheet_category(raw_cat)
            key = (str(ing.id), str(unit).lower(), cat)
            cell = cells.get(key)
            if cell is None:
                cells[key] = {
                    'ingredient_name': name,
                    'unit': unit,
                    'category': cat,
                    'qty': qty_scaled,
                    'amount': qty_scaled * rate,
                }
            else:
                cell['qty'] += qty_scaled
                cell['amount'] += qty_scaled * rate

    items: list[dict[str, Any]] = []
    for key in sorted(cells.keys(), key=lambda k: cells[k]['ingredient_name'].lower()):
        c = cells[key]
        q = c['qty']
        rate = (c['amount'] / q) if q > 0 else Decimal('0')
        rq = q.quantize(Decimal('0.0001'))
        items.append(
            {
                'ingredient_name': c['ingredient_name'],
                'total_quantity': float(rq),
                'unit': c['unit'],
                'category': c['category'],
                'rate': float(rate.quantize(Decimal('0.0001'))),
                'unit_cost': float(rate.quantize(Decimal('0.0001'))),
            }
        )

    return {
        'quotation_id': str(quotation.pk),
        'client_name': client_name,
        'event_date': event_date.isoformat() if event_date else None,
        'total_guests': total_guests,
        'generated_at': timezone.now().isoformat(),
        'items': items,
    }


def grocery_sheet_workbook_bytes(quotation, tenant_id) -> bytes:
    data = build_grocery_sheet_payload(quotation, tenant_id)
    from shared.exports.excel_service import create_workbook, workbook_to_bytes

    wb = create_workbook()
    ws = wb.active
    ws.title = 'Grocery'
    ws.append(['Ingredient', 'Category', 'Quantity', 'Unit', 'Est. unit rate (₹)'])
    for it in data['items']:
        ws.append(
            [
                it['ingredient_name'],
                it.get('category', ''),
                it['total_quantity'],
                it['unit'],
                it.get('rate', ''),
            ]
        )
    return workbook_to_bytes(wb)


def grocery_sheet_pdf_bytes(quotation, tenant_id) -> bytes:
    from html import escape
    from io import BytesIO

    from xhtml2pdf import pisa

    data = build_grocery_sheet_payload(quotation, tenant_id)
    rows = []
    for it in data['items']:
        rows.append(
            '<tr>'
            f'<td>{escape(str(it["ingredient_name"]))}</td>'
            f'<td>{escape(str(it.get("category") or ""))}</td>'
            f'<td>{escape(str(it["total_quantity"]))}</td>'
            f'<td>{escape(str(it["unit"]))}</td>'
            '</tr>'
        )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt; }}
      h1 {{ font-size: 14pt; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
      th, td {{ border: 1px solid #444; padding: 4px 6px; text-align: left; }}
      th {{ background: #eee; }}
    </style></head><body>
    <h1>Grocery sheet</h1>
    <p><b>Client:</b> {escape(data["client_name"])} &nbsp; | &nbsp;
    <b>Event date:</b> {escape(str(data.get("event_date") or "—"))} &nbsp; | &nbsp;
    <b>Guests:</b> {escape(str(data.get("total_guests") or "—"))}</p>
    <table>
      <thead><tr><th>Ingredient</th><th>Category</th><th>Qty</th><th>Unit</th></tr></thead>
      <tbody>{"".join(rows) or '<tr><td colspan="4">No menu items with recipes.</td></tr>'}</tbody>
    </table>
    </body></html>"""
    out = BytesIO()
    pisa.CreatePDF(src=html, dest=out, encoding='utf-8')
    return out.getvalue()
