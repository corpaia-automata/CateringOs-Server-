from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Tenant


@receiver(post_save, sender=Tenant)
def start_tenant_trial(sender, instance, created, **kwargs):
    if created and not instance.trial_started_at:
        instance.start_trial()
