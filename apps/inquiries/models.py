from django.db import models

from shared.mixins import BaseMixin


class Inquiry(BaseMixin):

    class SourceChannel(models.TextChoices):
        PHONE_CALL = 'PHONE_CALL', 'Phone Call'
        WHATSAPP   = 'WHATSAPP',   'WhatsApp'
        WALK_IN    = 'WALK_IN',    'Walk-In'

    class Status(models.TextChoices):
        NEW       = 'NEW',       'New'
        QUALIFIED = 'QUALIFIED', 'Qualified'
        FOLLOW_UP = 'FOLLOW_UP', 'Follow Up'
        CONVERTED = 'CONVERTED', 'Converted'
        LOST      = 'LOST',      'Lost'

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
    converted_event = models.OneToOneField(
        'events.Event',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='source_inquiry',
    )

    class Meta:
        db_table = 'inquiries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.customer_name} — {self.tentative_date} ({self.status})'
