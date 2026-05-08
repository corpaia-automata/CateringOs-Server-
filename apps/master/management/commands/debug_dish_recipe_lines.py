from django.core.management.base import BaseCommand

from apps.master.models import Dish, DishRecipe


class Command(BaseCommand):
    help = 'Print recipe lines for a dish (default: Chicken Fried Rice) for verification.'

    def add_arguments(self, parser):
        parser.add_argument(
            'dish_name',
            nargs='?',
            default='Chicken Fried Rice',
            help='Dish name (case-insensitive match)',
        )

    def handle(self, *args, **options):
        name = options['dish_name']

        dishes = Dish.all_objects.filter(name__iexact=name.strip(), is_deleted=False)
        if not dishes.exists():
            dishes = Dish.all_objects.filter(name__icontains=name.strip(), is_deleted=False)

        if not dishes.exists():
            self.stdout.write(self.style.WARNING(f'No dish matching "{name}"'))
            return

        for dish in dishes.order_by('tenant_id', 'name'):
            self.stdout.write(
                f'\n--- Dish: {dish.name!r} (id={dish.id}, tenant_id={dish.tenant_id}) ---'
            )
            lines = (
                DishRecipe.objects.filter(dish=dish)
                .select_related('ingredient')
                .order_by('ingredient__name')
            )
            if not lines:
                self.stdout.write('  (no recipe lines)')
                continue

            w_name = max(len('ingredient_name'), max(len(l.ingredient.name) for l in lines))
            header = f'  {"ingredient_name".ljust(w_name)}  qty_per_unit  unit  unit_cost_snapshot  ing.unit_cost  ing.uom'
            self.stdout.write(header)
            self.stdout.write('  ' + '-' * (len(header) - 2))

            for line in lines:
                ing = line.ingredient
                self.stdout.write(
                    f'  {ing.name.ljust(w_name)}  {str(line.qty_per_unit).rjust(12)}  {line.unit!s:4}  '
                    f'{str(line.unit_cost_snapshot).rjust(18)}  {str(ing.unit_cost).rjust(12)}  {ing.unit_of_measure}'
                )

            self.stdout.write('')
