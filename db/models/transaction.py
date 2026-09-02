import uuid

from django.db import models

from db.models import AuditModel, Organization, OrganizationSubscription


def generate_transaction_id():
    return f"TXN_{uuid.uuid4().hex[:20].upper()}"

class TransactionType(models.TextChoices):
    SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
    SMS = "SMS", "SMS"
    WHATSAPP = "WHATSAPP", "WhatsApp"


class TransactionStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class PaymentGateway(models.TextChoices):
    RAZORPAY = "RAZORPAY", "Razorpay"


class Transaction(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    transaction_id = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        default=generate_transaction_id,
        db_index=True,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    subscription = models.ForeignKey(
        OrganizationSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.CREATED,
        db_index=True,
    )

    payment_gateway = models.CharField(
        max_length=20,
        choices=PaymentGateway.choices,
        default=PaymentGateway.RAZORPAY,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=10,
        default="INR",
    )

    gateway_order_id = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_index=True,
    )

    gateway_payment_id = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_index=True,
    )

    gateway_subscription_id = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_index=True,
    )

    gateway_invoice_id = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_index=True,
    )

    payment_date = models.DateTimeField(
        null=True,
        blank=True,
    )

    failure_reason = models.TextField(
        null=True,
        blank=True,
    )

    response = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "transaction_type"]
            ),
            models.Index(
                fields=["organization", "status"]
            ),
            models.Index(
                fields=["status", "created_at"]
            ),
        ]

    def __str__(self):
        return self.transaction_id