from django.db import models


class EventIngredient(models.Model):
    """
    Computed output table — written ONLY by CalculationEngine.run().
    Does NOT inherit BaseMixin (no UUID PK, no soft delete, no timestamps).
    calculated_at is refreshed on every engine run via auto_now=True.
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='event_ingredients',
        db_column='tenant_id',
    )
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='ingredients',
    )
    ingredient = models.ForeignKey(
        'master.Ingredient',
        on_delete=models.CASCADE,
        related_name='event_totals',
    )
    # Denormalised for fast reads — no joins needed on the grocery list
    ingredient_name = models.CharField(max_length=255)
    category        = models.CharField(max_length=20, db_index=True)
    total_quantity  = models.DecimalField(max_digits=14, decimal_places=6)
    unit            = models.CharField(max_length=20)
    calculated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'event_ingredients'
        unique_together = [('event', 'ingredient')]
        indexes = [
            models.Index(fields=['event', 'category']),
        ]

    def __str__(self):
        return f'{self.event} | {self.ingredient_name} — {self.total_quantity} {self.unit}'
