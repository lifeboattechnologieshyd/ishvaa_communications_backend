import uuid

from crum import get_current_request
from django.db import models


class TimeAuditModel(models.Model):
    """To path when the record was created and last modified"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Modified At")

    class Meta:
        abstract = True


class UserAuditModel(models.Model):
    """To path when the record was created and last modified"""
    created_by = models.CharField(
        max_length=255,
        default="SYSTEM",
    )
    updated_by = models.CharField(
        max_length=255,
        default="SYSTEM",
    )

    class Meta:
        abstract = True


class AuditModel(TimeAuditModel, UserAuditModel):
    """To path when the record was created and last modified"""
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        request = get_current_request()
        if request and hasattr(request, "user") and request.user and request.user.is_authenticated:
            if self.created_by == "SYSTEM":
                self.created_by = str(request.user.id)
            self.updated_by = str(request.user.id)

        super().save(*args, **kwargs)
