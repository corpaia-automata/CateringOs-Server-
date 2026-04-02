from django.db import models
from shared.mixins import BaseMixin


class Quotation(BaseMixin):

    class Status(models.TextChoices):
        DRAFT    = 'DRAFT',    'Draft'
        SENT     = 'SENT',     'Sent'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'

    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='quotations',
    )
    version_number  = models.PositiveIntegerField(default=1)
    status          = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)

    # Snapshot of menu at time of generation / refresh
    # [{dish_name, quantity, unit, category}]
    line_items      = models.JSONField(default=list)
    manual_costs    = models.JSONField(default=list)   # [{label, amount}]

    subtotal        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_charge  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes           = models.TextField(blank=True)

    class Meta:
        db_table = 'quotations'
        ordering = ['-version_number']

    def __str__(self):
        return f'Quotation v{self.version_number} — {self.event}'
