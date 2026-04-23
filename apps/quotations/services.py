import base64
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.master.models import DishRecipe
from shared.exports.excel_service import create_workbook, workbook_to_bytes
from shared.exports.pdf_service import generate_pdf

# ─── Category → section title mapping ────────────────────────────────────────

CATEGORY_TITLES = {
    'Welcome Drink': 'WELCOME DRINK',
    'Herbal Tea':    'HERBAL TEA',
    'Main Course':   'MAIN COURSE CELEBRATION WITH RICE',
    'Biryani':       'MAIN COURSE CELEBRATION WITH RICE',
    'Fry':           'FRY',
    'Salads':        'SALADS',
    'Veg':           'VEG.',
    'Vegetarian':    'VEG.',
    'Drinks':        'DRINKS',
    'Desserts':      'PARADISE OF FINAL TOUCH',
    'Sweets':        'PARADISE OF FINAL TOUCH',
}

# ─── Benefits by service type ─────────────────────────────────────────────────

BENEFITS = {
    'BUFFET': [
        'Welcome Counter',
        'Serving Equipment',
        'Service Staffs',
        'House Keeping',
        'Hand Wash',
        'Tissue Papers',
    ],
    'BOX_COUNTER': [
        'Welcome Counter',
        'Ceramic Plates',
        'All Service Equipment',
        'Box Counter (6)',
        'Service Staffs',
        'Hosting Boys',
        'House Keeping',
        'Toothpick',
        'Sweet Saunf',
        'Table Mat',
        'Waste Cover',
        'Hand Wash',
        'Tissue Papers',
    ],
    'TABLE_SERVICE': [
        'Welcome Counter',
        'Table Setup',
        'Ceramic Plates',
        'Service Staffs',
        'House Keeping',
        'Hand Wash',
        'Tissue Papers',
    ],
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _logo_data_uri() -> str:
    """Return the logo as a base64 data URI so xhtml2pdf can embed it inline."""
    logo_path = Path(settings.BASE_DIR).parent.joinpath('frontend', 'public', 'afsal.png')
    try:
        data = logo_path.read_bytes()
        b64 = base64.b64encode(data).decode('ascii')
        return f'data:image/png;base64,{b64}'
    except FileNotFoundError:
        return ''


def _build_menu_sections(line_items: list) -> list:
    sections: OrderedDict = OrderedDict()
    for item in line_items:
        cat = item.get('category', 'Main Course')
        title = CATEGORY_TITLES.get(cat, cat.upper())
        sections.setdefault(title, []).append(item)
    return [{'title': title, 'dishes': dishes} for title, dishes in sections.items()]


# ─── Main service function ────────────────────────────────────────────────────

def generate_quotation_pdf(quotation, design: str = 'classic') -> bytes:
    """
    Build context from quotation + linked inquiry + current menu snapshot.
    Always called fresh — never cached.
    """
    inquiry = quotation.inquiry
    dishes = list(quotation.menu_dishes or [])
    services = list(quotation.menu_services or [])

    if inquiry and inquiry.tentative_date:
        event_date_str = inquiry.tentative_date.strftime('%d.%m.%y')
        event_day = inquiry.tentative_date.strftime('%A').upper()
    else:
        event_date_str = 'TBD'
        event_day = ''

    service_type = services[0].get('name') if services else 'Catering'
    service_key = str(service_type or '').replace(' ', '_').upper()

    menu_rows = []
    dish_subtotal = Decimal('0')
    for dish in dishes:
        qty = _decimal(dish.get('qty'), '0')
        rate = _decimal(dish.get('rate'), '0')
        subtotal = _decimal(dish.get('subtotal'), '0') or (qty * rate)
        dish_subtotal += subtotal
        menu_rows.append({
            'name': dish.get('name') or 'Dish',
            'qty_text': f"{qty.normalize()} {dish.get('unit') or 'unit'}",
            'amount': subtotal,
            'kind': 'dish',
        })

    service_subtotal = Decimal('0')
    for service in services:
        qty = _decimal(service.get('qty'), '0')
        rate = _decimal(service.get('rate'), '0')
        subtotal = _decimal(service.get('subtotal'), '0') or (qty * rate)
        service_subtotal += subtotal
        menu_rows.append({
            'name': service.get('name') or 'Service',
            'qty_text': f"{qty.normalize()} units",
            'amount': subtotal,
            'kind': 'service',
        })

    estimated_total = dish_subtotal + service_subtotal
    menu_sections = _build_menu_sections(dishes)
    service_names = [str(service.get('name') or 'Service') for service in services]

    context = {
        'quote_number': quotation.quote_number,
        'customer_name': inquiry.customer_name if inquiry else '\u2014',
        'contact_number': inquiry.contact_number if inquiry and inquiry.contact_number else '\u2014',
        'venue': inquiry.notes if inquiry and inquiry.notes else '\u2014',
        'event_type': inquiry.event_type if inquiry and inquiry.event_type else '\u2014',
        'guest_count': inquiry.guest_count if inquiry else 0,
        'service_type': str(service_type or 'Catering'),
        'event_date': event_date_str,
        'event_day': event_day,
        'event_time': 'TBD',
        'generated_at': timezone.localtime().strftime('%d.%m.%y & %A'),
        'menu_rows': menu_rows,
        'menu_sections': menu_sections,
        'service_names': service_names,
        'dish_subtotal': dish_subtotal,
        'service_subtotal': service_subtotal,
        'estimated_total': estimated_total,
        'benefits': BENEFITS.get(service_key, BENEFITS['BUFFET']),
        'logo_path': _logo_data_uri(),
    }
    template_name = 'quotation_pdf_premium.html' if str(design).strip().lower() == 'premium' else 'quotation_pdf.html'
    return generate_pdf(template_name, context)


def _decimal(value, default: str = '0') -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _normalized_unit(unit: str) -> str:
    value = (unit or '').strip().lower()
    if value in {'kg', 'kilogram', 'kilograms'}:
        return 'kg'
    if value in {'g', 'gram', 'grams'}:
        return 'g'
    if value in {'litre', 'liter', 'l', 'litres', 'liters'}:
        return 'litre'
    if value in {'ml', 'millilitre', 'milliliter'}:
        return 'ml'
    return value or 'unit'


def _to_base_unit(quantity: Decimal, unit: str) -> tuple[Decimal, str]:
    normalized = _normalized_unit(unit)
    if normalized == 'kg':
        return quantity * Decimal('1000'), 'g'
    if normalized == 'litre':
        return quantity * Decimal('1000'), 'ml'
    return quantity, normalized


def _to_display_unit(quantity: Decimal, base_unit: str) -> tuple[Decimal, str]:
    if base_unit == 'g' and quantity >= Decimal('1000'):
        return (quantity / Decimal('1000')), 'kg'
    if base_unit == 'ml' and quantity >= Decimal('1000'):
        return (quantity / Decimal('1000')), 'litre'
    return quantity, base_unit


def generate_grocery_sheet(quotation) -> dict:
    """
    Build an aggregated grocery sheet from quotation.menu_dishes.
    Scaling: (required_qty / base_recipe_qty) * ingredient_qty_per_unit
    """
    dishes = list(quotation.menu_dishes or [])
    dish_ids = [str(d.get('id')).strip() for d in dishes if d.get('id')]
    if not dish_ids:
        return {
            'quotation_id': str(quotation.id),
            'client_name': quotation.inquiry.customer_name if quotation.inquiry_id else '',
            'event_date': str(quotation.inquiry.tentative_date) if quotation.inquiry_id else None,
            'total_guests': quotation.inquiry.guest_count if quotation.inquiry_id else None,
            'generated_at': timezone.now().isoformat(),
            'items': [],
        }

    recipe_lines = (
        DishRecipe.objects
        .filter(tenant_id=quotation.tenant_id, dish_id__in=dish_ids)
        .select_related('ingredient')
    )

    recipe_by_dish: dict[str, list] = {}
    for line in recipe_lines:
        recipe_by_dish.setdefault(str(line.dish_id), []).append(line)

    aggregated: dict[tuple[str, str], dict] = {}
    for dish in dishes:
        dish_id = str(dish.get('id') or '').strip()
        if not dish_id:
            continue
        required_qty = _decimal(dish.get('qty'), '0')
        base_recipe_qty = _decimal(dish.get('base_recipe_qty') or 1, '1')
        if required_qty <= 0 or base_recipe_qty <= 0:
            continue
        scale_factor = required_qty / base_recipe_qty
        for line in recipe_by_dish.get(dish_id, []):
            scaled_qty = _decimal(line.qty_per_unit, '0') * scale_factor
            if scaled_qty <= 0:
                continue
            qty_in_base, base_unit = _to_base_unit(scaled_qty, line.unit)
            ingredient_name = (line.ingredient.name or '').strip()
            normalized_name = ingredient_name.lower()
            category = (line.ingredient.category or '').upper()
            key = (normalized_name, category)
            if key not in aggregated:
                aggregated[key] = {
                    'ingredient_name': ingredient_name,
                    'quantity_base': Decimal('0'),
                    'base_unit': base_unit,
                    'category': category,
                }
            current = aggregated[key]
            if current['base_unit'] != base_unit:
                # Fallback: keep separate rows if units are fundamentally incompatible.
                key = (f'{normalized_name}__{base_unit}', category)
                if key not in aggregated:
                    aggregated[key] = {
                        'ingredient_name': ingredient_name,
                        'quantity_base': Decimal('0'),
                        'base_unit': base_unit,
                        'category': category,
                    }
                current = aggregated[key]
            current['quantity_base'] += qty_in_base

    items = []
    for row in aggregated.values():
        display_qty, display_unit = _to_display_unit(row['quantity_base'], row['base_unit'])
        items.append({
            'ingredient_name': row['ingredient_name'],
            'total_quantity': float(display_qty),
            'unit': display_unit,
            'category': row['category'],
        })
    items.sort(key=lambda item: ((item.get('category') or ''), (item.get('ingredient_name') or '').lower()))

    return {
        'quotation_id': str(quotation.id),
        'client_name': quotation.inquiry.customer_name if quotation.inquiry_id else '',
        'event_date': str(quotation.inquiry.tentative_date) if quotation.inquiry_id else None,
        'total_guests': quotation.inquiry.guest_count if quotation.inquiry_id else None,
        'generated_at': timezone.now().isoformat(),
        'items': items,
    }


def export_grocery_sheet_excel(sheet: dict) -> bytes:
    wb = create_workbook()
    ws = wb.active
    ws.title = 'Grocery Sheet'
    ws.append(['Client Name', sheet.get('client_name') or ''])
    ws.append(['Event Date', sheet.get('event_date') or ''])
    ws.append(['Total Guests', sheet.get('total_guests') or ''])
    ws.append([])
    ws.append(['Category', 'Ingredient Name', 'Total Quantity', 'Unit'])
    for item in sheet.get('items', []):
        ws.append([
            item.get('category') or 'OTHER',
            item.get('ingredient_name') or '',
            item.get('total_quantity') or 0,
            (item.get('unit') or '').upper(),
        ])
    return workbook_to_bytes(wb)


def export_grocery_sheet_pdf(sheet: dict) -> bytes:
    return generate_pdf('quotation_grocery_sheet_pdf.html', {
        'client_name': sheet.get('client_name') or '—',
        'event_date': sheet.get('event_date') or '—',
        'total_guests': sheet.get('total_guests') or '—',
        'items': sheet.get('items', []),
        'generated_at': timezone.now().strftime('%d %b %Y, %I:%M %p'),
    })
