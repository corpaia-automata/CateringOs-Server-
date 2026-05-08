from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from copy import deepcopy
from shared.mixins import BaseMixin


VALID_TRANSITIONS = {
    'DRAFT':       ['CONFIRMED', 'CANCELLED'],
    'CONFIRMED':   ['IN_PROGRESS', 'CANCELLED'],
    'IN_PROGRESS': ['COMPLETED', 'CANCELLED'],
    'COMPLETED':   [],
    'CANCELLED':   [],
}


class Event(BaseMixin):

    class ServiceType(models.TextChoices):
        BUFFET        = 'BUFFET',        'Buffet'
        BOX_COUNTER   = 'BOX_COUNTER',   'Box Counter'
        TABLE_SERVICE = 'TABLE_SERVICE', 'Table Service'
        OTHER         = 'OTHER',         'Other'

    class Status(models.TextChoices):
        DRAFT       = 'DRAFT',       'Draft'
        CONFIRMED   = 'CONFIRMED',   'Confirmed'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED   = 'COMPLETED',   'Completed'
        CANCELLED   = 'CANCELLED',   'Cancelled'

    class PaymentStatus(models.TextChoices):
        ADVANCE_PAID = 'ADVANCE_PAID', 'Advance Paid'
        PARTIAL      = 'PARTIAL',      'Partial'
        PENDING      = 'PENDING',      'Pending'
        FULLY_PAID   = 'FULLY_PAID',   'Fully Paid'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='events',
        db_column='tenant_id',
    )
    inquiry = models.ForeignKey(
        'inquiries.Inquiry',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='events',
        db_column='inquiry_id',
    )
    quotation = models.OneToOneField(
        'quotations.Quotation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='event',
        db_column='quotation_id',
    )
    event_code              = models.CharField(max_length=30, unique=True, editable=False)
    customer_name           = models.CharField(max_length=255)
    contact_number          = models.CharField(max_length=20, blank=True)
    event_type              = models.CharField(max_length=100, blank=True)
    event_date              = models.DateField(db_index=True, null=True, blank=True)
    event_time              = models.TimeField(null=True, blank=True)
    venue                   = models.CharField(max_length=255, blank=True)
    guest_count             = models.PositiveIntegerField()
    service_type            = models.CharField(max_length=15, choices=ServiceType.choices)
    service_type_narration  = models.CharField(max_length=255, blank=True)
    status                  = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    payment_status          = models.CharField(max_length=15, choices=PaymentStatus.choices, blank=True)
    total_amount            = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    advance_amount          = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    credited_amount         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    extra_charges           = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    menu_locked             = models.BooleanField(default=False)
    menu_snapshot           = models.JSONField(default=dict, blank=True)
    services_snapshot       = models.JSONField(default=list, blank=True)
    costing_snapshot        = models.JSONField(default=dict, blank=True)
    grocery_snapshot        = models.JSONField(default=dict, blank=True)
    pricing_snapshot        = models.JSONField(default=dict, blank=True)
    notes                   = models.TextField(blank=True)

    class Meta:
        db_table = 'events'
        ordering = ['event_date', 'event_time']
        indexes = [
            models.Index(fields=['event_date', 'status']),
        ]

    def __str__(self):
        return f'{self.event_code} — {self.customer_name}'

    def save(self, *args, **kwargs):
        if not self.event_code:
            self.event_code = self._generate_event_code()
        super().save(*args, **kwargs)

    def _generate_event_code(self):
        from django.utils import timezone
        date_str = timezone.now().strftime('%Y%m%d')
        prefix = f'EVT-{date_str}-'
        # select_for_update on matching rows prevents two concurrent saves from
        # counting the same value and racing to INSERT the same code.
        last = (
            Event.all_objects
            .select_for_update()
            .filter(event_code__startswith=prefix)
            .count()
        )
        return f'{prefix}{str(last + 1).zfill(4)}'

    def transition_to(self, new_status):
        allowed = VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from '{self.status}' to '{new_status}'. "
                f"Allowed: {allowed or 'none (terminal state)'}."
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

    def set_snapshot_data(self, *, menu_data, services_data, costing_data, grocery_data, pricing_data):
        # Defensive deep copy ensures no in-memory shared references are kept.
        self.menu_snapshot = deepcopy(menu_data) if menu_data is not None else {}
        self.services_snapshot = deepcopy(services_data) if services_data is not None else []
        self.costing_snapshot = deepcopy(costing_data) if costing_data is not None else {}
        self.grocery_snapshot = deepcopy(grocery_data) if grocery_data is not None else {}
        self.pricing_snapshot = deepcopy(pricing_data) if pricing_data is not None else {}


class EventLog(BaseMixin):

    class ActionType(models.TextChoices):
        ADD_DISH = 'ADD_DISH', 'Add Dish'
        UPDATE_DISH = 'UPDATE_DISH', 'Update Dish'
        REMOVE_DISH = 'REMOVE_DISH', 'Remove Dish'
        UPDATE_QTY = 'UPDATE_QTY', 'Update Quantity'
        ADD_SERVICE = 'ADD_SERVICE', 'Add Service'
        UPDATE_SERVICE = 'UPDATE_SERVICE', 'Update Service'
        REMOVE_SERVICE = 'REMOVE_SERVICE', 'Remove Service'
        COST_CHANGE = 'COST_CHANGE', 'Cost Change'
        PRICE_CHANGE = 'PRICE_CHANGE', 'Price Change'
        EXTRA_CHARGE = 'EXTRA_CHARGE', 'Extra Charge'

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='logs',
        db_column='event_id',
    )
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    description = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='event_logs',
        db_column='user_id',
    )

    class Meta:
        db_table = 'event_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', 'created_at']),
            models.Index(fields=['action_type']),
        ]

    def __str__(self):
        return f'{self.event_id} — {self.action_type}'
