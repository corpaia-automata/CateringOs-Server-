from django.db import models
from shared.mixins import BaseMixin


class EventMenuItem(BaseMixin):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='menu_items',
        db_column='tenant_id',
    )
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='menu_items',
    )
    dish = models.ForeignKey(
        'master.Dish',
        on_delete=models.PROTECT,
        related_name='event_appearances',
    )

    # --- Snapshot fields (frozen at first save, never updated after) ---
    dish_name_snapshot    = models.CharField(max_length=255, blank=True)
    # serving_unit replaces unit_type_snapshot — single unified field
    serving_unit_snapshot = models.CharField(max_length=10, blank=True)
    # Format: [{ingredient_id, name, category, qty_per_unit (str), unit,
    #           unit_cost_snapshot (str), batch_size (str)}]
    # unit_cost_snapshot enables historical cost recovery even if ingredient prices change.
    recipe_snapshot       = models.JSONField(default=list, blank=True)

    quantity      = models.DecimalField(max_digits=10, decimal_places=2)
    # quantity_unit defaults to dish.serving_unit at first save
    quantity_unit = models.CharField(max_length=10, blank=True)
    sort_order    = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'event_menu_items'
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f'{self.event} | {self.dish_name_snapshot or self.dish.name}'

    def save(self, *args, **kwargs):
        if not self.dish_name_snapshot:
            self.dish_name_snapshot = self.dish.name
        if not self.serving_unit_snapshot:
            self.serving_unit_snapshot = self.dish.serving_unit
        if not self.quantity_unit:
            self.quantity_unit = self.dish.serving_unit
        # Use _state.adding so an empty recipe list [] doesn't trigger
        # re-snapshot on every subsequent save ([] is falsy — old guard was broken).
        if self._state.adding:
            self.recipe_snapshot = self._build_recipe_snapshot()
        super().save(*args, **kwargs)

    def _build_recipe_snapshot(self) -> list:
        batch_size = str(self.dish.batch_size)
        return [
            {
                'ingredient_id':     str(line.ingredient.id),
                'name':              line.ingredient.name,
                'category':          line.ingredient.category,
                'qty_per_unit':      str(line.qty_per_unit),
                'unit':              line.unit,
                'unit_cost_snapshot': str(line.unit_cost_snapshot),
                'batch_size':        batch_size,
            }
            for line in self.dish.recipe_lines.select_related('ingredient').all()
        ]
