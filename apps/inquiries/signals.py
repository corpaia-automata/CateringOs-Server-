from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PreEstimate
from .services import initialize_default_categories


@receiver(post_save, sender=PreEstimate)
def create_default_categories(sender, instance, created, **kwargs):
    if created:
        initialize_default_categories(instance)
