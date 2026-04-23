from decimal import Decimal

from .models import Inquiry, PreEstimate, PreEstimateCategory

DEFAULT_CATEGORIES = [
    'Food & Beverage',
    'Labor',
    'Stage, Decor & Lighting',
    'Equipment & Rentals',
    'Logistics & Fuel',
    'Utilities',
    'Disposables',
    'Misc & Contingency',
]


def initialize_default_categories(pre_estimate: PreEstimate) -> None:
    PreEstimateCategory.objects.bulk_create([
        PreEstimateCategory(
            pre_estimate=pre_estimate,
            name=name,
            order=idx,
        )
        for idx, name in enumerate(DEFAULT_CATEGORIES)
    ])


class InquiryService:
    pass


def export_pre_estimate_json(pre_estimate_id) -> dict:
    pre_estimate = (
        PreEstimate.objects
        .select_related('inquiry')
        .prefetch_related('categories__items')
        .get(pk=pre_estimate_id)
    )
    inquiry = pre_estimate.inquiry

    categories = []
    for category in pre_estimate.categories.all():
        items = [
            {
                'name':     item.name,
                'unit':     item.unit,
                'quantity': str(item.quantity),
                'rate':     str(item.rate),
                'total':    str(item.total),
            }
            for item in category.items.all()
        ]
        categories.append({
            'name':       category.name,
            'order':      category.order,
            'items':      items,
            'subtotal':   str(sum(item.total for item in category.items.all())),
        })

    return {
        'meta': {
            'pre_estimate_id': str(pre_estimate.pk),
            'generated_at':    pre_estimate.updated_at.isoformat(),
        },
        'event': {
            'customer_name':  inquiry.customer_name,
            'contact_number': inquiry.contact_number,
            'email':          inquiry.email,
            'event_type':     pre_estimate.event_type,
            'service_type':   pre_estimate.service_type,
            'location':       pre_estimate.location,
            'guest_count':    pre_estimate.guest_count,
            'tentative_date': inquiry.tentative_date.isoformat(),
        },
        'categories': categories,
        'totals': {
            'total_cost':    str(pre_estimate.total_cost),
            'total_quote':   str(pre_estimate.total_quote),
            'total_profit':  str(pre_estimate.total_profit),
            'target_margin': str(pre_estimate.target_margin),
        },
    }


class PreEstimateService:

    @staticmethod
    def calculate_totals(pre_estimate_id) -> PreEstimate:
        pre_estimate = (
            PreEstimate.objects
            .prefetch_related('categories__items')
            .get(pk=pre_estimate_id)
        )

        total_cost = Decimal('0')
        for category in pre_estimate.categories.all():
            for item in category.items.all():
                total_cost += item.total

        margin = pre_estimate.target_margin / Decimal('100')
        # total_quote = cost / (1 - margin)  →  margin is on selling price
        total_quote = total_cost / (Decimal('1') - margin)
        total_profit = total_quote - total_cost

        pre_estimate.total_cost   = total_cost.quantize(Decimal('0.01'))
        pre_estimate.total_quote  = total_quote.quantize(Decimal('0.01'))
        pre_estimate.total_profit = total_profit.quantize(Decimal('0.01'))
        pre_estimate.save(update_fields=['total_cost', 'total_quote', 'total_profit', 'updated_at'])

        return pre_estimate
