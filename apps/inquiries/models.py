from django.db import models

from shared.mixins import BaseMixin


class Inquiry(BaseMixin):

    class SourceChannel(models.TextChoices):
        PHONE_CALL = 'PHONE_CALL', 'Phone Call'
        WHATSAPP   = 'WHATSAPP',   'WhatsApp'
        WALK_IN    = 'WALK_IN',    'Walk-In'

    class Status(models.TextChoices):
        PLANNING  = 'PLANNING',  'Planning'
        NEW       = 'NEW',       'New'
        QUALIFIED = 'QUALIFIED', 'Qualified'
        FOLLOW_UP = 'FOLLOW_UP', 'Follow Up'
        QUOTED    = 'QUOTED',    'Quoted'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        REJECTED  = 'REJECTED',  'Rejected'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='inquiries',
        db_column='tenant_id',
    )
    customer_name   = models.CharField(max_length=255)
    contact_number  = models.CharField(max_length=20, blank=True)
    email           = models.EmailField(blank=True, default='')
    source_channel  = models.CharField(max_length=15, choices=SourceChannel.choices)
    event_type      = models.CharField(max_length=100)
    tentative_date  = models.DateField()
    guest_count        = models.PositiveIntegerField(default=1)
    estimated_budget   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes              = models.TextField(blank=True)
    status          = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    converted_event = models.ForeignKey(
        'events.Event',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='source_inquiries',
        db_column='converted_event_id',
    )
    converted_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'inquiries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.customer_name} — {self.tentative_date} ({self.status})'


class PreEstimate(BaseMixin):

    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.CASCADE,
        related_name='pre_estimates',
        db_column='inquiry_id',
    )
    event_type     = models.CharField(max_length=100)
    service_type   = models.CharField(max_length=100)
    location       = models.CharField(max_length=255)
    guest_count    = models.PositiveIntegerField()
    target_margin  = models.DecimalField(max_digits=5, decimal_places=2)
    total_cost   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_quote  = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_profit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'pre_estimates'
        ordering = ['-created_at']

    def __str__(self):
        return f'PreEstimate #{self.pk} — {self.inquiry}'


class PreEstimateCategory(BaseMixin):

    pre_estimate = models.ForeignKey(
        PreEstimate,
        on_delete=models.CASCADE,
        related_name='categories',
        db_column='pre_estimate_id',
    )
    name  = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'pre_estimate_categories'
        ordering = ['order']

    def __str__(self):
        return f'{self.name} (PreEstimate #{self.pre_estimate_id})'


class PreEstimateItem(BaseMixin):

    category = models.ForeignKey(
        PreEstimateCategory,
        on_delete=models.CASCADE,
        related_name='items',
        db_column='category_id',
    )
    name     = models.CharField(max_length=255)
    unit     = models.CharField(max_length=50)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    rate     = models.DecimalField(max_digits=12, decimal_places=2)
    total    = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = 'pre_estimate_items'
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.total = (self.quantity or Decimal('0')) * (self.rate or Decimal('0'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} × {self.quantity} {self.unit} @ {self.rate}'
