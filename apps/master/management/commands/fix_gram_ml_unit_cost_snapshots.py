"""
Repair DishRecipe.unit_cost_snapshot for g/ml lines that were stored as (unit_cost/1000).

Run after reviewing the preview. Does not run automatically.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.master.models import DishRecipe


_SMALL_UNITS_Q = Q()
for _u in ('g', 'gram', 'ml', 'millilitre', 'milliliter'):
    _SMALL_UNITS_Q |= Q(unit__iexact=_u)


class Command(BaseCommand):
    help = (
        'Set unit_cost_snapshot to ingredient.unit_cost for g/ml recipe lines where '
        '0 < snapshot < 10 (fingerprint of erroneous ÷1000). Preview first; requires confirmation.'
    )

    def handle(self, *args, **options):
        qs = (
            DishRecipe.objects.filter(
                _SMALL_UNITS_Q,
                unit_cost_snapshot__gt=Decimal('0'),
                unit_cost_snapshot__lt=Decimal('10'),
                is_deleted=False,
            )
            .exclude(ingredient_id__isnull=True)
            .select_related('ingredient', 'dish')
            .order_by('dish__name', 'ingredient__name')
        )

        rows = list(qs)
        if not rows:
            self.stdout.write(self.style.SUCCESS('No matching DishRecipe rows (nothing to do).'))
            return

        self.stdout.write(
            self.style.WARNING(
                f'Found {len(rows)} row(s) with small-unit line UOM and 0 < unit_cost_snapshot < 10.\n'
            )
        )

        w_dish = max(len('dish name'), max(len(line.dish.name or '') for line in rows))
        w_ing = max(len('ingredient'), max(len(line.ingredient.name or '') for line in rows))

        header = (
            f'{"dish name".ljust(w_dish)} | {"ingredient".ljust(w_ing)} | '
            f'{"current_snapshot".rjust(16)} | {"ingredient.unit_cost".rjust(18)} | {"will_set_to".rjust(14)}'
        )
        self.stdout.write(header)
        self.stdout.write('-' * len(header))

        to_update = []
        for line in rows:
            ing = line.ingredient
            live = ing.unit_cost if ing.unit_cost is not None else Decimal('0')
            will_set = live
            self.stdout.write(
                f'{(line.dish.name or "").ljust(w_dish)} | {(ing.name or "").ljust(w_ing)} | '
                f'{str(line.unit_cost_snapshot).rjust(16)} | {str(live).rjust(18)} | {str(will_set).rjust(14)}'
            )
            line.unit_cost_snapshot = will_set
            to_update.append(line)

        self.stdout.write('')
        answer = input('Type YES to apply these updates (anything else aborts): ').strip()
        if answer != 'YES':
            self.stdout.write(self.style.WARNING('Aborted; no rows updated.'))
            return

        DishRecipe.objects.bulk_update(to_update, ['unit_cost_snapshot'])
        self.stdout.write(self.style.SUCCESS(f'Updated {len(to_update)} DishRecipe row(s).'))
