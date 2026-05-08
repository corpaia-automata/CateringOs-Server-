from copy import deepcopy
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Event, EventLog


def _decimal(value, default='0'):
    if value is None or value == '':
        return Decimal(default)
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f'Invalid numeric value: {value}')
    return value.quantize(Decimal('0.01'))


def _raw_decimal(value, default='0'):
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f'Invalid numeric value: {value}')


def _as_items(snapshot):
    if isinstance(snapshot, list):
        return snapshot
    if isinstance(snapshot, dict):
        items = snapshot.get('items')
        return items if isinstance(items, list) else []
    return []


def _line_total(item, quantity_keys=('quantity', 'qty'), price_keys=('price_per_unit', 'rate', 'price')):
    quantity = Decimal('0')
    price = Decimal('0')
    for key in quantity_keys:
        if key in item:
            quantity = _decimal(item.get(key))
            break
    for key in price_keys:
        if key in item:
            price = _decimal(item.get(key))
            break
    return quantity * price


def _money(value):
    return str(_decimal(value))


def _uuid_string(value):
    if value is None or value == '':
        return ''
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return ''


def _is_fixed_charge_category(category):
    return str(category or '').strip().lower() in {'rental', 'rentals', 'other', 'others'}


def recalculate_event(event_id):
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event_id)
        return EventExecutionService._recalculate_event_instance(event)


class EventExecutionService:
    MUTATION_SAVE_FIELDS = [
        'menu_snapshot',
        'services_snapshot',
        'costing_snapshot',
        'grocery_snapshot',
        'pricing_snapshot',
        'extra_charges',
        'total_cost',
        'total_amount',
        'advance_amount',
        'credited_amount',
        'updated_at',
    ]

    @staticmethod
    def ensure_editable(event):
        if event.status == Event.Status.COMPLETED:
            raise ValidationError('Completed events are locked and cannot be edited.')
        if event.menu_locked:
            raise ValidationError('Event menu is locked and cannot be edited.')

    @staticmethod
    def normalize_menu_items(items):
        normalized = []
        seen = set()
        for index, item in enumerate(items or []):
            if not isinstance(item, dict):
                raise ValidationError('Each dish must be an object.')
            name = str(item.get('name') or item.get('dish_name') or '').strip()
            if not name:
                raise ValidationError('Dish name is required.')
            key = name.casefold()
            if key in seen:
                raise ValidationError(f'Duplicate dish name: {name}')
            seen.add(key)

            item_id = str(item.get('id') or item.get('dish_id') or f'dish-{index + 1}')
            dish_id = _uuid_string(item.get('dish_id') or item.get('id'))
            quantity = _decimal(item.get('quantity', item.get('qty', 0)))
            price = _decimal(item.get('price_per_unit', item.get('rate', item.get('price', 0))))
            if quantity <= 0:
                raise ValidationError('Dish quantity must be greater than zero.')
            if price < 0:
                raise ValidationError('Dish price cannot be negative.')
            total = quantity * price
            normalized.append({
                'id': item_id,
                'name': name,
                'category': str(item.get('category') or 'Dishes'),
                'quantity': str(quantity),
                'qty': str(quantity),
                'unit': str(item.get('unit') or 'plate'),
                'price_per_unit': str(price),
                'price': str(price),
                'total': str(total.quantize(Decimal('0.01'))),
            })
            if dish_id:
                normalized[-1]['dish_id'] = dish_id
        return normalized

    @staticmethod
    def normalize_service_items(items):
        normalized = []
        for index, item in enumerate(items or []):
            if not isinstance(item, dict):
                raise ValidationError('Each service must be an object.')
            name = str(item.get('name') or item.get('service_name') or '').strip()
            if not name:
                raise ValidationError('Service name is required.')
            quantity = _decimal(item.get('quantity', item.get('qty', 1)))
            price = _decimal(item.get('price_per_unit', item.get('rate', item.get('price', 0))))
            if quantity <= 0:
                raise ValidationError('Service quantity must be greater than zero.')
            if price < 0:
                raise ValidationError('Service price cannot be negative.')
            total = quantity * price
            normalized.append({
                'id': str(item.get('id') or f'service-{index + 1}'),
                'name': name,
                'quantity': str(quantity),
                'qty': str(quantity),
                'unit': str(item.get('unit') or 'unit'),
                'price_per_unit': str(price),
                'rate': str(price),
                'price': str(price),
                'subtotal': str(total.quantize(Decimal('0.01'))),
                'total': str(total.quantize(Decimal('0.01'))),
            })
        return normalized

    @staticmethod
    def derive_grocery_snapshot(event, menu_items):
        from apps.master.models import DishRecipe

        dish_ids = [
            dish_id
            for dish_id in (_uuid_string(item.get('dish_id') or item.get('id')) for item in menu_items)
            if dish_id
        ]
        if not dish_ids:
            return {'items': [], 'generated_at': timezone.now().isoformat()}

        recipe_lines = (
            DishRecipe.objects
            .filter(tenant_id=event.tenant_id, dish_id__in=dish_ids)
            .select_related('ingredient', 'dish')
        )
        recipe_by_dish = {}
        for line in recipe_lines:
            recipe_by_dish.setdefault(str(line.dish_id), []).append(line)

        totals = {}
        for item in menu_items:
            dish_id = _uuid_string(item.get('dish_id') or item.get('id'))
            if not dish_id:
                continue
            quantity = _decimal(item.get('quantity', item.get('qty', 0)))
            if quantity <= 0:
                continue

            for line in recipe_by_dish.get(dish_id, []):
                category = getattr(line.ingredient, 'category', '')
                batch_size = _raw_decimal(getattr(line.dish, 'batch_size', 1) or 1)
                if batch_size <= 0:
                    continue
                scale = Decimal('1') if _is_fixed_charge_category(category) else quantity / batch_size
                raw_quantity = _raw_decimal(line.qty_per_unit) * scale
                if raw_quantity <= 0:
                    continue
                line_unit = str(line.unit or getattr(line.ingredient, 'unit_of_measure', '') or '').strip()
                if not line_unit:
                    continue
                ingredient_id = str(line.ingredient_id)
                key = (ingredient_id, line_unit.lower())
                if key not in totals:
                    totals[key] = {
                        'ingredient_id': ingredient_id,
                        'ingredient_name': line.ingredient.name,
                        'category': category,
                        'total_quantity': Decimal('0'),
                        'unit': line_unit,
                    }
                totals[key]['total_quantity'] += raw_quantity

        items = []
        for index, row in enumerate(totals.values()):
            items.append({
                'id': f"grocery-{row['ingredient_id']}-{index}",
                'ingredient_id': row['ingredient_id'],
                'ingredient_name': row['ingredient_name'],
                'name': row['ingredient_name'],
                'category': row['category'],
                'total_quantity': str(row['total_quantity'].quantize(Decimal('0.001'))),
                'quantity': str(row['total_quantity'].quantize(Decimal('0.001'))),
                'unit': row['unit'],
            })

        items.sort(key=lambda item: ((item.get('category') or ''), (item.get('ingredient_name') or '').lower()))
        return {
            'items': items,
            'generated_at': timezone.now().isoformat(),
            'source': 'menu_snapshot',
        }

    @staticmethod
    def _manual_cost_items(snapshot):
        if isinstance(snapshot, dict):
            manual_items = snapshot.get('manual_items')
            if isinstance(manual_items, list):
                return manual_items
            items = snapshot.get('items')
            if isinstance(items, list):
                return [
                    item for item in items
                    if isinstance(item, dict) and item.get('source') != 'derived'
                ]
        if isinstance(snapshot, list):
            return snapshot
        return []

    @staticmethod
    def _recipe_costing(event, menu_items):
        from apps.engine.calculation import normalise
        from apps.master.models import DishRecipe

        dish_ids = [
            dish_id
            for dish_id in (_uuid_string(item.get('dish_id') or item.get('id')) for item in menu_items)
            if dish_id
        ]
        if not dish_ids:
            return [], [], [], Decimal('0')

        recipe_lines = (
            DishRecipe.objects
            .filter(tenant_id=event.tenant_id, dish_id__in=dish_ids)
            .select_related('ingredient', 'dish')
        )
        recipe_by_dish = {}
        for line in recipe_lines:
            recipe_by_dish.setdefault(str(line.dish_id), []).append(line)

        totals = {}
        for item in menu_items:
            dish_id = _uuid_string(item.get('dish_id') or item.get('id'))
            if not dish_id:
                continue
            dish_quantity = _decimal(item.get('quantity', item.get('qty', 0)))
            if dish_quantity <= 0:
                continue

            for line in recipe_by_dish.get(dish_id, []):
                category = str(getattr(line.ingredient, 'category', '') or '').strip()
                batch_size = _raw_decimal(getattr(line.dish, 'batch_size', 1) or 1)
                if batch_size <= 0:
                    continue
                scale = Decimal('1') if _is_fixed_charge_category(category) else dish_quantity / batch_size
                raw_quantity = _raw_decimal(line.qty_per_unit) * scale
                if raw_quantity <= 0:
                    continue

                normalized_quantity, base_unit = normalise(raw_quantity, line.unit)
                ingredient_id = str(line.ingredient_id)
                line_unit = str(line.unit or getattr(line.ingredient, 'unit_of_measure', '') or '').strip()
                if not line_unit:
                    continue
                key = (ingredient_id, line_unit.lower())
                existing = totals.get(key)

                snap = getattr(line, 'unit_cost_snapshot', None)
                snap_nonzero = snap is not None and _raw_decimal(snap) != Decimal('0')
                if snap_nonzero:
                    unit_cost = _raw_decimal(snap)
                    cost_unit = (
                        str(line.unit or '').strip()
                        or str(getattr(line.ingredient, 'unit_of_measure', '') or '').strip()
                    )
                else:
                    unit_cost = _raw_decimal(getattr(line.ingredient, 'unit_cost', 0))
                    cost_unit = (
                        str(getattr(line.ingredient, 'unit_of_measure', '') or '').strip()
                        or str(line.unit or '').strip()
                    )
                if not cost_unit:
                    continue
                line_u = str(line.unit or '').strip().lower()
                ing_u = str(getattr(line.ingredient, 'unit_of_measure', '') or '').strip().lower()
                bulk_snap = snap_nonzero and (
                    (line_u in ('g', 'gram') and ing_u == 'kg')
                    or (line_u in ('ml', 'millilitre', 'milliliter') and ing_u in ('litre', 'liter', 'ltr'))
                )
                # gram/ml unit cost conversion: bulk snapshot is ₹ per kg / per litre; normalise() yields qty in that base
                if bulk_snap:
                    cost_per_base_unit = unit_cost
                else:
                    cost_unit_quantity, cost_base_unit = normalise(Decimal('1'), cost_unit)
                    if cost_unit_quantity > 0 and cost_base_unit == base_unit:
                        cost_per_base_unit = unit_cost / cost_unit_quantity
                    else:
                        cost_per_base_unit = unit_cost

                if not existing:
                    totals[key] = {
                        'ingredient_id': ingredient_id,
                        'ingredient_name': line.ingredient.name,
                        'category': category,
                        'quantity': Decimal('0'),
                        'unit': line_unit,
                        'cost': Decimal('0'),
                    }
                totals[key]['quantity'] += raw_quantity
                totals[key]['cost'] += normalized_quantity * cost_per_base_unit

        derived_items = []
        grocery_items = []
        event_ingredient_rows = []
        derived_total = Decimal('0')
        for index, row in enumerate(totals.values()):
            if row['quantity'] < Decimal('0.001'):
                continue
            total_cost = row['cost'].quantize(Decimal('0.01'))
            display_rate = Decimal('0')
            if row['quantity'] > 0:
                display_rate = (total_cost / row['quantity']).quantize(Decimal('0.01'))
            derived_total += total_cost
            derived_items.append({
                'id': f"derived-{row['ingredient_id']}-{str(row['unit']).lower()}",
                'source': 'derived',
                'ingredient_id': row['ingredient_id'],
                'ingredient_name': row['ingredient_name'],
                'name': row['ingredient_name'],
                'category': row['category'],
                'quantity': str(row['quantity'].quantize(Decimal('0.001'))),
                'qty': str(row['quantity'].quantize(Decimal('0.001'))),
                'unit': row['unit'],
                'rate': str(display_rate),
                'unit_rate': str(display_rate),
                'total': str(total_cost),
                'total_cost': str(total_cost),
                'amount': str(total_cost),
            })
            grocery_items.append({
                'id': f"grocery-{row['ingredient_id']}-{index}",
                'ingredient_id': row['ingredient_id'],
                'ingredient_name': row['ingredient_name'],
                'name': row['ingredient_name'],
                'category': row['category'],
                'total_quantity': str(row['quantity'].quantize(Decimal('0.001'))),
                'quantity': str(row['quantity'].quantize(Decimal('0.001'))),
                'unit': row['unit'],
                'rate': str(display_rate),
                'total_cost': str(total_cost),
            })
            event_ingredient_rows.append({
                'ingredient_id': row['ingredient_id'],
                'ingredient_name': row['ingredient_name'],
                'category': row['category'],
                'total_quantity': row['quantity'],
                'unit': row['unit'],
            })

        sort_key = lambda item: ((item.get('category') or ''), (item.get('ingredient_name') or '').lower())
        derived_items.sort(key=sort_key)
        grocery_items.sort(key=sort_key)
        event_ingredient_rows.sort(key=sort_key)
        return derived_items, grocery_items, event_ingredient_rows, derived_total

    @staticmethod
    def _refresh_event_ingredients(event, rows):
        from apps.engine.models import EventIngredient

        EventIngredient.objects.filter(event=event).delete()
        if not rows:
            return 0
        EventIngredient.objects.bulk_create([
            EventIngredient(
                tenant_id=event.tenant_id,
                event_id=event.id,
                ingredient_id=row['ingredient_id'],
                ingredient_name=row['ingredient_name'],
                category=row['category'],
                total_quantity=row['total_quantity'],
                unit=row['unit'],
            )
            for row in rows
        ])
        return len(rows)

    @staticmethod
    def normalize_costing_items(items):
        normalized = []
        for index, item in enumerate(items or []):
            if not isinstance(item, dict):
                raise ValidationError('Each cost item must be an object.')
            name = str(item.get('name') or item.get('ingredient_name') or '').strip()
            if not name:
                raise ValidationError('Cost item name is required.')
            quantity = _decimal(item.get('quantity', item.get('qty', 0)))
            rate = _decimal(item.get('rate', item.get('unit_rate', item.get('price', 0))))
            if quantity < 0 or rate < 0:
                raise ValidationError('Cost quantity and rate cannot be negative.')
            total = quantity * rate
            normalized.append({
                'id': str(item.get('id') or f'cost-{index + 1}'),
                'name': name,
                'ingredient_name': name,
                'category': str(item.get('category') or 'OTHER'),
                'quantity': str(quantity),
                'qty': str(quantity),
                'unit': str(item.get('unit') or 'unit'),
                'rate': str(rate),
                'unit_rate': str(rate),
                'total': str(total.quantize(Decimal('0.01'))),
                'total_cost': str(total.quantize(Decimal('0.01'))),
                'amount': str(total.quantize(Decimal('0.01'))),
                'source': 'manual',
            })
        return normalized

    @staticmethod
    def recalculate(event):
        return EventExecutionService._recalculate_event_instance(event)

    @staticmethod
    def _recalculate_event_instance(event):
        menu_items = _as_items(event.menu_snapshot)
        service_items = _as_items(event.services_snapshot)
        manual_items = EventExecutionService.normalize_costing_items(
            EventExecutionService._manual_cost_items(event.costing_snapshot)
        )
        derived_items, grocery_items, event_ingredient_rows, derived_cost = EventExecutionService._recipe_costing(event, menu_items)

        menu_total = sum((_line_total(item) for item in menu_items), Decimal('0'))
        service_total = sum((_line_total(item) for item in service_items), Decimal('0'))
        manual_cost = sum((_line_total(item, price_keys=('rate', 'unit_rate', 'price')) for item in manual_items), Decimal('0'))
        internal_cost = derived_cost + manual_cost
        extra_charges = _decimal(event.extra_charges or 0)
        final_total = menu_total + service_total + extra_charges
        advance_amount = _decimal(event.advance_amount or 0)
        if advance_amount > final_total:
            advance_amount = final_total
        balance_amount = final_total - advance_amount
        margin = Decimal('0')
        if final_total > 0:
            margin = ((final_total - internal_cost) / final_total * Decimal('100')).quantize(Decimal('0.01'))

        existing_pricing = event.pricing_snapshot if isinstance(event.pricing_snapshot, dict) else {}
        original_quote = existing_pricing.get('original_quote') or existing_pricing.get('quote_total') or event.total_amount or final_total
        event.extra_charges = extra_charges
        event.total_cost = internal_cost.quantize(Decimal('0.01'))
        event.total_amount = final_total.quantize(Decimal('0.01'))
        event.advance_amount = advance_amount.quantize(Decimal('0.01'))
        event.credited_amount = event.advance_amount
        event.costing_snapshot = {
            'items': derived_items + manual_items,
            'derived_items': derived_items,
            'manual_items': manual_items,
            'totals': {
                'derived_cost': _money(derived_cost),
                'manual_cost': _money(manual_cost),
                'internal_cost': _money(internal_cost),
            },
            'generated_at': timezone.now().isoformat(),
            'source': 'menu_snapshot',
        }
        event.grocery_snapshot = {
            'items': grocery_items,
            'generated_at': timezone.now().isoformat(),
            'source': 'menu_snapshot',
        }
        event.pricing_snapshot = {
            **existing_pricing,
            'original_quote': _money(original_quote),
            'menu_total': _money(menu_total),
            'service_total': _money(service_total),
            'derived_cost': _money(derived_cost),
            'manual_cost': _money(manual_cost),
            'internal_cost': _money(internal_cost),
            'total_cost': _money(internal_cost),
            'extra_charges': _money(extra_charges),
            'final_total': _money(final_total),
            'final_selling_price': _money(final_total),
            'selling_price': _money(final_total),
            'advance_amount': _money(advance_amount),
            'credited_amount': _money(advance_amount),
            'balance_amount': _money(balance_amount),
            'margin_percentage': str(margin),
        }
        event.save(update_fields=EventExecutionService.MUTATION_SAVE_FIELDS)
        EventExecutionService._refresh_event_ingredients(event, event_ingredient_rows)
        return event

    @staticmethod
    def log(event, action_type, description, user=None):
        EventLog.objects.create(
            event=event,
            action_type=action_type,
            description=description,
            user=user if getattr(user, 'is_authenticated', False) else None,
        )

    @staticmethod
    def replace_menu(event, dishes, user=None):
        EventExecutionService.ensure_editable(event)
        before = {str(item.get('name', '')).casefold(): item for item in _as_items(event.menu_snapshot)}
        normalized = EventExecutionService.normalize_menu_items(dishes)
        after = {item['name'].casefold(): item for item in normalized}
        event.menu_snapshot = {'items': normalized}
        event = EventExecutionService.recalculate(event)
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        updated = sorted(name for name in set(after) & set(before) if after[name] != before[name])
        if added:
            EventExecutionService.log(event, EventLog.ActionType.ADD_DISH, f'Added dishes: {", ".join(added)}', user)
        if updated:
            EventExecutionService.log(event, EventLog.ActionType.UPDATE_QTY, f'Updated dishes: {", ".join(updated)}', user)
        if removed:
            EventExecutionService.log(event, EventLog.ActionType.REMOVE_DISH, f'Removed dishes: {", ".join(removed)}', user)
        return event

    @staticmethod
    def replace_services(event, services, user=None):
        EventExecutionService.ensure_editable(event)
        before = deepcopy(_as_items(event.services_snapshot))
        normalized = EventExecutionService.normalize_service_items(services)
        event.services_snapshot = {'items': normalized}
        event = EventExecutionService.recalculate(event)
        action = EventLog.ActionType.ADD_SERVICE if len(normalized) > len(before) else EventLog.ActionType.UPDATE_SERVICE
        EventExecutionService.log(event, action, 'Updated event services.', user)
        return event

    @staticmethod
    def replace_costing(event, items, user=None):
        EventExecutionService.ensure_editable(event)
        normalized = EventExecutionService.normalize_costing_items(items)
        event.costing_snapshot = {'manual_items': normalized}
        event = EventExecutionService.recalculate(event)
        EventExecutionService.log(event, EventLog.ActionType.COST_CHANGE, 'Updated event costing breakdown.', user)
        return event

    @staticmethod
    def update_pricing(event, payload, user=None):
        EventExecutionService.ensure_editable(event)
        if 'final_selling_price' in payload or 'final_total' in payload:
            final_total = _decimal(payload.get('final_selling_price', payload.get('final_total')))
            if final_total < 0:
                raise ValidationError('Final selling price cannot be negative.')
            menu_total = sum((_line_total(item) for item in _as_items(event.menu_snapshot)), Decimal('0'))
            service_total = sum((_line_total(item) for item in _as_items(event.services_snapshot)), Decimal('0'))
            extra_charges = final_total - menu_total - service_total
            if extra_charges < 0:
                raise ValidationError('Final selling price cannot be less than menu and service total.')
            event.extra_charges = extra_charges
        if 'advance_amount' in payload:
            advance = _decimal(payload.get('advance_amount'))
            if advance < 0:
                raise ValidationError('Advance amount cannot be negative.')
            event.advance_amount = advance
        existing = event.pricing_snapshot if isinstance(event.pricing_snapshot, dict) else {}
        if 'payment_terms' in payload:
            existing['payment_terms'] = str(payload.get('payment_terms') or '')
        event.pricing_snapshot = existing
        event = EventExecutionService.recalculate(event)
        EventExecutionService.log(event, EventLog.ActionType.PRICE_CHANGE, 'Updated event pricing.', user)
        return event

    @staticmethod
    def add_extra_charge(event, payload, user=None):
        EventExecutionService.ensure_editable(event)
        amount = _decimal(payload.get('amount', payload.get('extra_charge', 0)))
        if amount < 0:
            raise ValidationError('Extra charge cannot be negative.')
        reason = str(payload.get('description') or payload.get('reason') or 'Additional charge').strip()
        event.extra_charges = _decimal(event.extra_charges or 0) + amount
        existing = event.pricing_snapshot if isinstance(event.pricing_snapshot, dict) else {}
        charges = existing.get('extra_charge_items')
        if not isinstance(charges, list):
            charges = []
        charges.append({'description': reason, 'amount': str(amount)})
        event.pricing_snapshot = {**existing, 'extra_charge_items': charges}
        event = EventExecutionService.recalculate(event)
        EventExecutionService.log(event, EventLog.ActionType.EXTRA_CHARGE, f'{reason}: {amount}', user)
        return event


class EventService:

    @staticmethod
    def transition_status(event_id, new_status):
        """
        Validates new_status against VALID_TRANSITIONS and applies it.
        Raises ValidationError if the transition is not allowed.
        Returns the updated Event instance.
        """
        try:
            event = Event.objects.get(pk=event_id)
        except Event.DoesNotExist:
            raise ValidationError(f'Event {event_id} not found.')

        event.transition_to(new_status)
        return event
