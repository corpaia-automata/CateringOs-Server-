import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .models import Inquiry, PreEstimate, PreEstimateCategory

logger = logging.getLogger(__name__)

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


def _qty_positive(raw) -> bool:
    if raw is None or raw == '':
        return False
    try:
        return Decimal(str(raw)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def filter_quotation_dishes_for_convert(menu_dishes):
    """Return rows safe for EventExecutionService.replace_menu (drops invalid / dup names)."""
    if not isinstance(menu_dishes, list):
        return []
    seen_casefold = set()
    out = []
    for row in menu_dishes:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or row.get('dish_name') or '').strip()
        if not name:
            continue
        qty = row.get('quantity', row.get('qty'))
        if not _qty_positive(qty):
            continue
        key = name.casefold()
        if key in seen_casefold:
            continue
        seen_casefold.add(key)
        out.append(row)
    return out


def _enrich_service_row_for_execution(row: dict) -> dict:
    """Ensure rate/price exists so replace_services can compute line totals (quotation may only store subtotal)."""
    r = dict(row)
    try:
        qty = Decimal(str(r.get('quantity', r.get('qty', 1)) or '1'))
    except (InvalidOperation, TypeError, ValueError):
        qty = Decimal('1')
    if qty <= 0:
        qty = Decimal('1')
    try:
        rate = Decimal(str(r.get('rate', r.get('price', r.get('price_per_unit', 0))) or '0'))
    except (InvalidOperation, TypeError, ValueError):
        rate = Decimal('0')
    if rate <= 0 and r.get('subtotal') is not None:
        try:
            st = Decimal(str(r.get('subtotal')))
            if st > 0:
                r['rate'] = str((st / qty).quantize(Decimal('0.01')))
        except (InvalidOperation, TypeError, ValueError):
            pass
    return r


def filter_quotation_services_for_convert(menu_services):
    """Return rows safe for EventExecutionService.replace_services."""
    if not isinstance(menu_services, list):
        return []
    out = []
    for row in menu_services:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or row.get('service_name') or '').strip()
        if not name:
            continue
        qty = row.get('quantity', row.get('qty', 1))
        if not _qty_positive(qty):
            continue
        out.append(_enrich_service_row_for_execution(row))
    return out


def seed_event_execution_from_quotation(event, quotation, user=None):
    """
    Copies quotation menu rows into event execution snapshots via EventExecutionService.
    Snapshot line items drive breakdown; reconcile totals with apply_quotation_pricing_to_event.
    """
    from apps.events.services import EventExecutionService

    dishes = filter_quotation_dishes_for_convert(quotation.menu_dishes)
    services = filter_quotation_services_for_convert(quotation.menu_services)
    ev = event
    if dishes:
        try:
            ev = EventExecutionService.replace_menu(ev, dishes, user)
        except ValidationError as exc:
            logger.warning(
                'convert: skipped menu snapshot seed for inquiry-linked quotation %s: %s',
                quotation.pk,
                exc,
            )
    if services:
        try:
            ev = EventExecutionService.replace_services(ev, services, user)
        except ValidationError as exc:
            logger.warning(
                'convert: skipped services snapshot seed for inquiry-linked quotation %s: %s',
                quotation.pk,
                exc,
            )
    return ev


def apply_quotation_pricing_to_event(event, quotation, user=None):
    """
    Line-item breakdown comes from seeded snapshots; quotation final/advance wins when provided.
    """
    from apps.events.services import EventExecutionService

    payload = {}
    if quotation.final_selling_price > 0:
        payload['final_selling_price'] = str(quotation.final_selling_price)
    payload['advance_amount'] = str(quotation.advance_amount)
    return EventExecutionService.update_pricing(event, payload, user)


def _costing_derived_empty(event) -> bool:
    cs = event.costing_snapshot if isinstance(event.costing_snapshot, dict) else {}
    di = cs.get('derived_items')
    if isinstance(di, list):
        return len(di) == 0
    return True


def _quotation_lines_to_costing_payload(rows: list) -> list:
    """Map quotation costing_data.items rows into payloads for replace_costing / normalize_costing_items."""
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get('ingredient_name') or row.get('name') or '').strip()
        if not name:
            continue
        try:
            raw_q = row.get('quantity')
            if raw_q is None:
                raw_q = row.get('qty')
            qdec = Decimal(str(raw_q if raw_q is not None else '0'))
        except (InvalidOperation, TypeError, ValueError):
            qdec = Decimal('0')
        if qdec <= 0:
            continue
        try:
            raw_r = row.get('unit_rate')
            if raw_r is None:
                raw_r = row.get('rate')
            if raw_r is None:
                raw_r = row.get('price')
            rdec = Decimal(str(raw_r if raw_r is not None else '0'))
        except (InvalidOperation, TypeError, ValueError):
            rdec = Decimal('0')
        if rdec <= 0:
            try:
                tot_raw = row.get('total')
                if tot_raw is None:
                    tot_raw = row.get('amount')
                if tot_raw is not None:
                    tdec = Decimal(str(tot_raw))
                    if tdec > 0:
                        rdec = (tdec / qdec).quantize(Decimal('0.01'))
            except (InvalidOperation, TypeError, ValueError):
                pass
        if rdec < 0:
            continue
        out.append({
            'id': str(row.get('id') or f'qcost-{len(out)}'),
            'name': name,
            'ingredient_name': name,
            'quantity': str(qdec),
            'qty': str(qdec),
            'rate': str(rdec),
            'unit': str(row.get('unit') or 'unit'),
            'category': str(row.get('category') or 'OTHER'),
        })
    return out


def merge_quotation_snapshots_into_event_after_convert(event, quotation, user=None):
    """
    Backfill execution snapshots from quotation after pricing recalculate:
    missing services (e.g. subtotal-only rows), costing lines from costing_data when DB derivation
    misses recipe rows and/or manual lines, grocery list from quotation when empty.
    """
    from django.utils import timezone as django_timezone

    from apps.events.services import EventExecutionService, _as_items

    event.refresh_from_db()

    svc_q = filter_quotation_services_for_convert(quotation.menu_services)
    if svc_q and not _as_items(event.services_snapshot):
        try:
            event = EventExecutionService.replace_services(event, svc_q, user)
            event.refresh_from_db()
        except ValidationError as exc:
            logger.warning('convert: service backfill skipped: %s', exc)

    cd = quotation.costing_data if isinstance(quotation.costing_data, dict) else {}
    cd_items = cd.get('items')
    if not isinstance(cd_items, list):
        cd_items = []

    manual_rows = [r for r in cd_items if isinstance(r, dict) and str(r.get('source') or '').lower() == 'manual']
    recipe_rows = [r for r in cd_items if isinstance(r, dict) and str(r.get('source') or '').lower() == 'recipe']

    cost_lines = _quotation_lines_to_costing_payload(manual_rows)
    if _costing_derived_empty(event) and recipe_rows:
        cost_lines.extend(_quotation_lines_to_costing_payload(recipe_rows))

    if cost_lines:
        try:
            event = EventExecutionService.replace_costing(event, cost_lines, user)
            event.refresh_from_db()
        except ValidationError as exc:
            logger.warning('convert: costing backfill skipped: %s', exc)

    if not cost_lines and cd_items and _costing_derived_empty(event):
        fallback = _quotation_lines_to_costing_payload([r for r in cd_items if isinstance(r, dict)])
        if fallback:
            try:
                event = EventExecutionService.replace_costing(event, fallback, user)
                event.refresh_from_db()
            except ValidationError as exc:
                logger.warning('convert: costing fallback skipped: %s', exc)

    g_items = _as_items(event.grocery_snapshot)
    gd = quotation.grocery_data if isinstance(quotation.grocery_data, dict) else {}
    g_quote = gd.get('items')
    if not g_items and isinstance(g_quote, list) and len(g_quote) > 0:
        event.grocery_snapshot = {
            'items': g_quote,
            'generated_at': django_timezone.now().isoformat(),
            'source': 'quotation',
        }
        event.save(update_fields=['grocery_snapshot', 'updated_at'])

    return event


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

    tentative = inquiry.tentative_date
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
            'tentative_date': tentative.isoformat() if tentative else None,
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
