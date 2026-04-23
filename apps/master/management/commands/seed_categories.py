from django.core.management.base import BaseCommand
from apps.master.models import DishCategory
from apps.tenants.models import Tenant

DEFAULT_CATEGORIES = [
    ('Starters',      0),
    ('Main Course',   1),
    ('Breads',        2),
    ('Rice & Biryani', 3),
    ('Dal & Curries', 4),
    ('Desserts',      5),
    ('Beverages',     6),
    ('Live Counter',  7),
    ('Snacks',        8),
    ('Salads',        9),
]


class Command(BaseCommand):
    help = 'Seed default dish categories for all tenants (skips existing)'

    def add_arguments(self, parser):
        parser.add_argument('--slug', type=str, help='Seed only for this tenant slug')

    def handle(self, *args, **options):
        slug = options.get('slug')
        tenants = Tenant.objects.filter(slug=slug) if slug else Tenant.objects.all()

        for tenant in tenants:
            created = 0
            for name, sort_order in DEFAULT_CATEGORIES:
                _, was_created = DishCategory.objects.get_or_create(
                    tenant=tenant,
                    name=name,
                    defaults={'sort_order': sort_order},
                )
                if was_created:
                    created += 1
            self.stdout.write(
                self.style.SUCCESS(f'[{tenant.slug}] {created} categories created')
            )
