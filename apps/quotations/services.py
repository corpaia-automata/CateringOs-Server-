import base64
from collections import OrderedDict
from pathlib import Path

from django.conf import settings

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

def generate_quotation_pdf(quotation) -> bytes:
    """
    Build context from quotation + related event, render template, return PDF bytes.
    Always called fresh — never cached.
    """
    event = quotation.event

    # Format date fields (event_date may be None for draft events)
    if event.event_date:
        event_date_str = event.event_date.strftime('%d.%m.%y')
        event_day = event.event_date.strftime('%A').upper()
    else:
        event_date_str = 'TBD'
        event_day = ''

    if event.event_time:
        event_time_str = event.event_time.strftime('%I.%M %p')
    else:
        event_time_str = 'TBD'

    context = {
        'customer_name':  event.customer_name,
        'contact_number': event.contact_number or '\u2014',
        'venue':          event.venue or '\u2014',
        'event_type':     event.event_type or '\u2014',
        'guest_count':    event.guest_count,
        'service_type':   event.service_type.replace('_', ' '),
        'event_date':     event_date_str,
        'event_day':      event_day,
        'event_time':     event_time_str,
        'menu_sections':  _build_menu_sections(quotation.line_items),
        'benefits':       BENEFITS.get(event.service_type, BENEFITS['BUFFET']),
        'logo_path':      _logo_data_uri(),
    }
    return generate_pdf('quotation_pdf.html', context)
