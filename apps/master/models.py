from django.db import models
from shared.mixins import BaseMixin


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
        KG = 'kg', 'Kilogram'
        G = 'g', 'Gram'
        LITRE = 'litre', 'Litre'
        ML = 'ml', 'Millilitre'
        PIECE = 'piece', 'Piece'

    name = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    unit_of_measure = models.CharField(max_length=10, choices=UOM.choices)
    base_qty_ref = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'ingredients'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.unit_of_measure})'


class Dish(BaseMixin):

    class UnitType(models.TextChoices):
        PLATE = 'PLATE', 'Plate'
        KG = 'KG', 'Kilogram'
        PIECE = 'PIECE', 'Piece'
        LITRE = 'LITRE', 'Litre'
        PORTION = 'PORTION', 'Portion'

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    unit_type = models.CharField(max_length=10, choices=UnitType.choices)
    is_active = models.BooleanField(default=True)
    has_recipe = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    # Recipe batch size — "this recipe (ingredient list) produces X <unit> of the dish"
    batch_size = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    batch_unit = models.CharField(max_length=20, default='KG')

    class Meta:
        db_table = 'dishes'
        ordering = ['category', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(is_deleted=False),
                name='unique_active_dish_name',
            )
        ]

    def __str__(self):
        return self.name


class DishRecipe(BaseMixin):

    dish = models.ForeignKey(
        Dish, on_delete=models.CASCADE, related_name='recipe_lines'
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name='used_in_recipes'
    )
    qty_per_unit = models.DecimalField(max_digits=12, decimal_places=4)
    unit = models.CharField(max_length=10)

    class Meta:
        db_table = 'dish_recipes'
        unique_together = [('dish', 'ingredient')]

    def __str__(self):
        return f'{self.dish.name} — {self.ingredient.name}'
