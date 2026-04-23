from django.db import models
from shared.mixins import BaseMixin


class Category(BaseMixin):
    """
    Global dish category — not tenant-scoped.
    Managed centrally via Django admin; all tenants share the same list.
    """
    name       = models.CharField(max_length=100, unique=True)
    slug       = models.SlugField(max_length=100, unique=True)
    is_active  = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Ingredient(BaseMixin):

    class Category(models.TextChoices):
        GROCERY    = 'GROCERY',    'Grocery'
        DISPOSABLE = 'DISPOSABLE', 'Disposable'
        VEGETABLE  = 'VEGETABLE',  'Vegetable'
        FRUIT      = 'FRUIT',      'Fruit'
        RENTAL     = 'RENTAL',     'Rental'
        CHICKEN    = 'CHICKEN',    'Chicken'
        BEEF       = 'BEEF',       'Beef'
        MUTTON     = 'MUTTON',     'Mutton'
        FISH       = 'FISH',       'Fish'
        MEAT       = 'MEAT',       'Meat'
        OTHER      = 'OTHER',      'Other'

    class UOM(models.TextChoices):
        KG     = 'kg',     'Kilogram'
        G      = 'g',      'Gram'
        LITRE  = 'litre',  'Litre'
        ML     = 'ml',     'Millilitre'
        PIECE  = 'piece',  'Piece'
        PACKET = 'packet', 'Packet'
        BOX    = 'box',    'Box'
        DOZEN  = 'dozen',  'Dozen'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='ingredients',
        db_column='tenant_id',
    )
    name            = models.CharField(max_length=255)
    category        = models.CharField(max_length=20, choices=Category.choices)
    unit_of_measure = models.CharField(max_length=10, choices=UOM.choices)
    # Current market price per unit_of_measure — used for live cost calculation
    unit_cost       = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    base_qty_ref    = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    is_active       = models.BooleanField(default=True)

    class Meta:
        db_table = 'ingredients'
        ordering = ['category', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_ingredient_name_per_tenant',
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.unit_of_measure})'


class DishCategory(BaseMixin):
    """
    Tenant-scoped dish category master — replaces the free-text Dish.category_text field.
    e.g. Starters, Main Course, Desserts, Beverages, Live Counter.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='dish_categories',
        db_column='tenant_id',
    )
    name       = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'dish_categories'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_dish_category_per_tenant',
            )
        ]

    def __str__(self):
        return self.name


class Dish(BaseMixin):

    class DishType(models.TextChoices):
        RECIPE       = 'recipe',       'Recipe'
        LIVE_COUNTER = 'live_counter', 'Live Counter'
        FIXED_PRICE  = 'fixed_price',  'Fixed Price'

    class VegNonVeg(models.TextChoices):
        VEG     = 'veg',     'Veg'
        NON_VEG = 'non_veg', 'Non-Veg'

    # Single unified serving unit — replaces both the legacy `unit_type` (engine) and
    # `price_unit` (pricing) fields which expressed the same concept with different values.
    class ServingUnit(models.TextChoices):
        PLATE   = 'PLATE',   'Per Plate'
        KG      = 'KG',      'Per KG'
        PIECE   = 'PIECE',   'Per Piece'
        LITRE   = 'LITRE',   'Per Litre'
        PORTION = 'PORTION', 'Per Portion'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='dishes',
        db_column='tenant_id',
    )
    name        = models.CharField(max_length=255)
    dish_type   = models.CharField(max_length=20, choices=DishType.choices, default=DishType.RECIPE)
    veg_non_veg = models.CharField(max_length=10, choices=VegNonVeg.choices, default=VegNonVeg.VEG)
    description = models.TextField(blank=True, default='')
    image_url   = models.URLField(max_length=500, blank=True, default='')
    base_price    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    labour_cost   = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # --- TRANSITIONAL FIELDS ---
    # category_text: stores original free-text category string. Kept during migration
    # period while category (FK) is being backfilled. Will be removed in migration 0011.
    # db_column='category' maps to the existing 'category' column in the DB.
    category_text = models.CharField(max_length=100, blank=True, default='', db_column='category')
    # unit_type: legacy engine field — kept during migration period.
    # Will be removed after serving_unit is backfilled.
    unit_type = models.CharField(max_length=10, blank=True, default='', db_column='unit_type')

    # --- NEW FIELDS (added via migration 0009, retargeted in 0012) ---
    # category: FK to global Category (not tenant-scoped).
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='dishes',
        null=True,
        blank=True,
        db_column='category_id',
    )
    serving_unit = models.CharField(
        max_length=10, choices=ServingUnit.choices, default=ServingUnit.PLATE
    )

    is_active  = models.BooleanField(default=True)
    has_recipe = models.BooleanField(default=False)
    notes      = models.TextField(blank=True)
    batch_size = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    batch_unit = models.CharField(max_length=20, default='KG')

    class Meta:
        db_table = 'dishes'
        ordering = ['category', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                condition=models.Q(is_deleted=False),
                name='unique_active_dish_name_per_tenant',
            )
        ]

    def __str__(self):
        return self.name

    @property
    def estimated_cost_per_serving(self):
        from decimal import Decimal
        ingredient_cost = sum(
            (line.qty_per_unit * line.ingredient.unit_cost)
            for line in self.recipe_lines.select_related('ingredient').all()
        )
        # labour_cost may be NULL in DB for dishes migrated before the field had a default
        labour = self.labour_cost if self.labour_cost is not None else Decimal('0')
        return (ingredient_cost or Decimal('0')) + labour


class DishRecipe(BaseMixin):
    """
    Single source of truth for both CalculationEngine (quantities) and
    cost estimation (qty_per_unit × ingredient.unit_cost).
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='dish_recipes',
        db_column='tenant_id',
    )
    dish = models.ForeignKey(
        Dish, on_delete=models.CASCADE, related_name='recipe_lines'
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name='used_in_recipes'
    )
    qty_per_unit       = models.DecimalField(max_digits=12, decimal_places=4)
    unit               = models.CharField(max_length=10)
    # Snapshot of ingredient.unit_cost at time of recipe save.
    # Protects historical quotation cost even if master price changes later.
    unit_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        db_table = 'dish_recipes'
        unique_together = [('dish', 'ingredient')]

    def save(self, *args, **kwargs):
        # Always keep unit_cost_snapshot in sync when saving individual lines.
        # bulk_create bypasses this — see DishRecipeViewSet.replace_all for bulk handling.
        self.unit_cost_snapshot = self.ingredient.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.dish.name} — {self.ingredient.name}'
