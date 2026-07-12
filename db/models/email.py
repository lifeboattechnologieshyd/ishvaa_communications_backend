from django.db import models

from db.models import Organization, AuditModel, ApiKey


class EmailStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class EmailLog(AuditModel):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="emails",
        db_index=True
    )

    api_key = models.ForeignKey(
        ApiKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emails"
    )

    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    sender = models.EmailField()

    recipients = models.JSONField()

    subject = models.CharField(
        max_length=500
    )

    html = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
        db_index=True
    )

    error_message = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "email_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject