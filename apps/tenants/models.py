import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

class SubscriptionStatus(models.TextChoices):
    TRIAL = 'TRIAL', 'Trial'
    ACTIVE = 'ACTIVE', 'Active'
    EXPIRED = 'EXPIRED', 'Expired'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Tenant(models.Model):
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug                = models.SlugField(max_length=100, unique=True)
    name                = models.CharField(max_length=255)
    plan                = models.CharField(max_length=20, default='starter')   # starter | growth | enterprise
    status              = models.CharField(max_length=20, default='active')
    config              = models.JSONField(default=dict)                        # branding, locale, tax, features
    created_at          = models.DateTimeField(auto_now_add=True)
    trial_started_at    = models.DateTimeField(null=True, blank=True)
    trial_ends_at       = models.DateTimeField(null=True, blank=True)
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIAL,
    )
    default_template = models.CharField(
        max_length=20,
        choices=[
            ('classic', 'Classic'),
            ('premium', 'Premium'),
            ('minimal', 'Minimal'),
        ],
        default='classic',
    )
    default_quotation_template = models.ForeignKey(
        'quotations.QuotationTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='default_for_tenants',
    )

    class Meta:
        db_table = 'tenants'

    def __str__(self):
        return f'{self.name} ({self.slug})'

    def start_trial(self):
        now = timezone.now()
        self.trial_started_at = now
        self.trial_ends_at = now + timedelta(days=7)
        self.subscription_status = SubscriptionStatus.TRIAL
        self.save(update_fields=['trial_started_at', 'trial_ends_at', 'subscription_status'])

    @property
    def trial_days_left(self):
        if self.subscription_status != SubscriptionStatus.TRIAL:
            return 0
        if self.trial_ends_at is None:
            return 0
        return max(0, (self.trial_ends_at - timezone.now()).days)

    @property
    def is_trial_expired(self):
        return (
            self.subscription_status == SubscriptionStatus.TRIAL
            and self.trial_ends_at is not None
            and timezone.now() > self.trial_ends_at
        )

    @property
    def has_active_access(self):
        if self.subscription_status == SubscriptionStatus.ACTIVE:
            return True
        if self.subscription_status == SubscriptionStatus.TRIAL:
            return not self.is_trial_expired
        return False
