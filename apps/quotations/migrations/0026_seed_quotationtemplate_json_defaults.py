"""Seed ``sections_config`` and per-type ``template_schema`` on all quotation templates."""

from django.db import migrations


SECTIONS_CONFIG_DEFAULT = {
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

TEMPLATE_SCHEMA_BY_TYPE = {
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


def seed_template_json(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    classic_schema = TEMPLATE_SCHEMA_BY_TYPE['classic']

    for row in QuotationTemplate.objects.all().iterator():
        tt = row.template_type or 'classic'
        if tt == 'standard':
            tt = 'classic'
        schema = TEMPLATE_SCHEMA_BY_TYPE.get(tt, classic_schema)
        row.sections_config = SECTIONS_CONFIG_DEFAULT
        row.template_schema = schema
        row.save(update_fields=['sections_config', 'template_schema'])


def reverse_seed_template_json(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    QuotationTemplate.objects.all().update(sections_config={}, template_schema={})


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0025_quotationtemplate_fields_quotation_status'),
    ]

    operations = [
        migrations.RunPython(seed_template_json, reverse_seed_template_json),
    ]
