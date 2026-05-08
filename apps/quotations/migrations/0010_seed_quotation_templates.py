from django.db import migrations


def seed_quotation_templates(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')

    QuotationTemplate.objects.update_or_create(
        name='Classic',
        tier='classic',
        defaults={
            'brand_color': '#2C2C2A',
            'footer_text': 'Thank you for choosing our services',
            'layout_config': {
                'tier': 'classic',
                'background': 'warm',
                'font': 'serif',
                'pages': [
                    {
                        'page': 1,
                        'label': 'Event & Menu',
                        'sections': [
                            'client_details',
                            'event_details',
                            'menu_groups',
                        ],
                    },
                    {
                        'page': 2,
                        'label': 'Logistics',
                        'sections': [
                            'travel_schedule',
                            'rooms_schedule',
                        ],
                    },
                    {
                        'page': 3,
                        'label': 'Pricing & Terms',
                        'sections': [
                            'pricing_summary',
                            'special_info',
                            'terms',
                            'signature',
                        ],
                    },
                ],
            },
        },
    )

    QuotationTemplate.objects.update_or_create(
        name='Premium',
        tier='premium',
        defaults={
            'brand_color': '#C9952A',
            'footer_text': 'Premium Catering & Events',
            'layout_config': {
                'tier': 'premium',
                'background': 'white',
                'font': 'sans',
                'show_quantities': True,
                'pages': [
                    {
                        'page': 1,
                        'label': 'Cover',
                        'sections': ['branded_cover'],
                    },
                    {
                        'page': 2,
                        'label': 'About',
                        'sections': ['company_profile'],
                    },
                    {
                        'page': 3,
                        'label': 'Gallery',
                        'sections': ['gallery'],
                    },
                    {
                        'page': 4,
                        'label': 'Event Info',
                        'sections': ['client_details', 'event_summary'],
                    },
                    {
                        'page': 5,
                        'label': 'Menu',
                        'sections': ['menu_groups'],
                    },
                    {
                        'page': 6,
                        'label': 'Service',
                        'sections': ['service_settings'],
                    },
                    {
                        'page': 7,
                        'label': 'Pricing & Terms',
                        'sections': ['pricing_summary', 'terms'],
                    },
                ],
            },
        },
    )


def remove_quotation_templates(apps, schema_editor):
    QuotationTemplate = apps.get_model('quotations', 'QuotationTemplate')
    QuotationTemplate.objects.filter(
        name__in=['Classic', 'Premium'],
        tier__in=['classic', 'premium'],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0009_quotationtemplate_alter_quotation_managers_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_quotation_templates, remove_quotation_templates),
    ]
