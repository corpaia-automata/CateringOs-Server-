import uuid
from django.db import models


class Tenant(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug          = models.SlugField(max_length=100, unique=True)
    name          = models.CharField(max_length=255)
    plan          = models.CharField(max_length=20, default='starter')   # starter | growth | enterprise
    status        = models.CharField(max_length=20, default='active')
    config        = models.JSONField(default=dict)                        # branding, locale, tax, features
    created_at    = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tenants'

    def __str__(self):
        return f'{self.name} ({self.slug})'
