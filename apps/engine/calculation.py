import logging
from collections import defaultdict
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unit normalisation map
# ---------------------------------------------------------------------------
UNIT_NORMALISATION = {
    # Mass — all gram variants → kg (format_quantity handles display: <1 kg shown as gram)
    'g':      ('kg', Decimal('0.001')),
    'gram':   ('kg', Decimal('0.001')),
    'grams':  ('kg', Decimal('0.001')),
    'gm':     ('kg', Decimal('0.001')),
    'kg':     ('kg', Decimal('1')),

    # Volume → litre
    'ml':     ('litre', Decimal('0.001')),
    'ltr':    ('litre', Decimal('1')),
    'litre':  ('litre', Decimal('1')),
    'liter':  ('litre', Decimal('1')),

    # Count
    'piece':  ('piece', Decimal('1')),
    'pieces': ('piece', Decimal('1')),
    'pcs':    ('piece', Decimal('1')),
    'nos':    ('piece', Decimal('1')),
    'no':     ('piece', Decimal('1')),
    'dozen':  ('piece', Decimal('12')),
    'packet': ('packet', Decimal('1')),
    'box':    ('box', Decimal('1')),
    'unit':   ('piece', Decimal('1')),
}


# ---------------------------------------------------------------------------
# NORMALISE FUNCTION (ENGINE LEVEL — KEEP THIS)
# ---------------------------------------------------------------------------
def normalise(qty: Decimal, unit: str) -> tuple[Decimal, str]:
    entry = UNIT_NORMALISATION.get(unit.lower())
    if entry:
        base_unit, factor = entry
        return qty * factor, base_unit
    return qty, unit


# ---------------------------------------------------------------------------
# FORMAT FUNCTION (UI / RESPONSE LEVEL)
# ---------------------------------------------------------------------------
def format_quantity(qty: Decimal, unit: str) -> tuple[Decimal, str]:
    """
    Convert base units into human-readable format.
    """

    if unit == 'kg':
        if qty < Decimal('1'):
            return (qty * Decimal('1000'), 'gram')
        return (qty, 'kg')

    if unit == 'litre':
        if qty < Decimal('1'):
            return (qty * Decimal('1000'), 'ml')
        return (qty, 'litre')

    return (qty, unit)


class CalculationEngine:
    """
    Core engine:
    - Expands recipes
    - Normalises units
    - Aggregates ingredients
    - Writes EventIngredient
    """

    @staticmethod
    @transaction.atomic
    def run(event_id) -> int:
        from django.apps import apps
        from apps.master.models import Ingredient

        Event           = apps.get_model('events', 'Event')
        EventMenuItem   = apps.get_model('menu', 'EventMenuItem')
        EventIngredient = apps.get_model('engine', 'EventIngredient')

        # Acquire row-level lock on the event for the duration of this transaction.
        # Prevents two concurrent runs for the same event from interleaving
        # their delete + bulk_create and producing a corrupt/empty grocery list.
        Event.objects.select_for_update().get(pk=event_id)

        menu_items = (
            EventMenuItem.objects
            .filter(event_id=event_id, is_deleted=False)
        )

        totals = defaultdict(lambda: {
            'total': Decimal('0'),
            'unit':  '',
            'name':  '',
        })

        for item in menu_items:
            dish_qty = item.quantity
            if dish_qty <= 0:
                logger.warning(
                    "engine: skipping menu item %s in event %s — dish_qty is %s",
                    item.pk, event_id, dish_qty,
                )
                continue

            for line in item.recipe_snapshot:
                # Fix 2: strip + lower; model stores 'RENTAL'/'OTHER' (not 'rentals'/'others')
                category = str(line.get('category', '')).strip().lower()
                if category in ('rental', 'rentals', 'other', 'others'):
                    continue

                # Fix 3: guard against batch_size = 0 or missing
                raw_batch = str(line.get('batch_size') or '1')
                batch_size = Decimal(raw_batch)
                if batch_size <= 0:
                    logger.warning(
                        "engine: skipping line '%s' in event %s — batch_size is %s",
                        line.get('name', '?'), event_id, batch_size,
                    )
                    continue

                qty_per_unit = Decimal(str(line['qty_per_unit']))
                if qty_per_unit <= 0:
                    logger.warning(
                        "engine: skipping line '%s' in event %s — qty_per_unit is %s",
                        line.get('name', '?'), event_id, qty_per_unit,
                    )
                    continue

                # Flat-charge units (Labour, Fuel, Kitchen, etc.) are fixed costs
                # that do not scale with portion size — always use factor 1.
                FLAT_CHARGE_UNITS = {'unit', 'nos', 'no'}
                effective_scale = (
                    Decimal('1')
                    if line['unit'].lower() in FLAT_CHARGE_UNITS
                    else dish_qty / batch_size
                )
                raw_qty = qty_per_unit * effective_scale
                norm_qty, base_unit = normalise(raw_qty, line['unit'])

                # Fix 1: key is ingredient_id only — prevents unique_together violation
                # when the same ingredient appears with different (but compatible) unit aliases
                key = str(line['ingredient_id'])

                if key in totals and totals[key]['unit'] and totals[key]['unit'] != base_unit:
                    logger.warning(
                        "engine: ingredient '%s' (%s) has incompatible units '%s' vs '%s' "
                        "in event %s — skipping conflicting entry",
                        line.get('name', '?'), key, totals[key]['unit'], base_unit, event_id,
                    )
                    continue

                totals[key]['total'] += norm_qty
                totals[key]['unit']   = base_unit
                totals[key]['name']   = line['name']

        if not totals:
            EventIngredient.objects.filter(event_id=event_id).delete()
            return 0

        ingredient_ids = list(totals.keys())  # Fix 1: key is now ingredient_id directly

        category_map = {
            str(ing.id): ing.category
            for ing in Ingredient.objects.filter(id__in=ingredient_ids)
        }

        EventIngredient.objects.filter(event_id=event_id).delete()

        new_rows = [
            EventIngredient(
                event_id        = event_id,
                ingredient_id   = ingredient_id,
                ingredient_name = data['name'],
                category        = category_map.get(ingredient_id, ''),
                total_quantity  = data['total'],
                unit            = data['unit'],
            )
            for ingredient_id, data in totals.items()  # Fix 1: key is now ingredient_id only
            if data['total'] >= Decimal('0.001')          # skip negligible quantities (< 1 mg / 1 µl)
        ]

        EventIngredient.objects.bulk_create(new_rows)
        return len(new_rows)