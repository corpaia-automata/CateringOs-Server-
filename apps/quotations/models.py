from django.db import models
from shared.mixins import BaseMixin


class Quotation(BaseMixin):

    class Status(models.TextChoices):
        DRAFT    = 'DRAFT',    'Draft'
        SENT     = 'SENT',     'Sent'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='quotations',
        db_column='tenant_id',
    )
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

    quote_number = models.CharField(max_length=20, unique=True, blank=True, editable=False)

    class Meta:
        db_table = 'quotations'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.quote_number} v{self.version_number} — {self.event}'

    def save(self, *args, **kwargs):
        if not self.quote_number:
            self.quote_number = self._generate_quote_number()
        super().save(*args, **kwargs)

    def _generate_quote_number(self):
        last = Quotation.all_objects.count()
        return f'QTN-{str(last + 1).zfill(5)}'
