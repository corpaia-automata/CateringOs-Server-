import uuid
from django.db import models


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class UUIDPrimaryKeyMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone
        now = timezone.now()
        self.is_deleted = True
        self.deleted_at = now
        self.updated_at = now
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class BaseMixin(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Combines UUID PK + timestamps + soft delete.
    All models must inherit from this class.
    """

    class Meta:
        abstract = True
        # Use the unfiltered manager for FK lookups and related object access.
        # Without this, Django may use ActiveManager for FK traversal, causing
        # DoesNotExist when accessing soft-deleted related objects.
        base_manager_name = 'all_objects'
