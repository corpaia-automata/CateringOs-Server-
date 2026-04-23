from django.conf import settings
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
    inquiry = models.ForeignKey(
        'inquiries.Inquiry',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='quotations',
        db_column='inquiry_id',
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
    final_selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    internal_cost       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margin              = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    advance_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_terms       = models.TextField(blank=True)
    is_locked           = models.BooleanField(default=False)
    notes           = models.TextField(blank=True)

    # Menu tab UI state — full frontend dish/service objects
    menu_dishes   = models.JSONField(default=list)
    menu_services = models.JSONField(default=list)

    quote_number = models.CharField(max_length=20, blank=True, editable=False)
    quoted_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='quotations_created',
        db_column='quoted_by_id',
    )
    sent_at     = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'quotations'
        ordering = ['-created_at']
        unique_together = [('tenant', 'quote_number')]

    def __str__(self):
        return f'{self.quote_number} v{self.version_number} — {self.inquiry}'

    def save(self, *args, **kwargs):
        if not self.quote_number:
            self.quote_number = self._generate_quote_number()
        super().save(*args, **kwargs)

    def _generate_quote_number(self):
        from django.db import transaction
        # Lock all existing quotations for this tenant to prevent concurrent
        # saves from computing the same sequence number.
        with transaction.atomic():
            last = (
                Quotation.all_objects
                .select_for_update()
                .filter(tenant_id=self.tenant_id)
                .count()
            )
        return f'QTN-{str(last + 1).zfill(5)}'
