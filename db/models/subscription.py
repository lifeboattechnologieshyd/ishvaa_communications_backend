from django.db import models

from db.models import AuditModel, Organization


class BillingCycle(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    YEARLY = "YEARLY", "Yearly"


class SubscriptionPlan(AuditModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices
    )

    emails_per_month = models.PositiveIntegerField()

    is_active = models.BooleanField(
        default=True,
        db_index=True
    )

    class Meta:
        db_table = "subscription_plans"


class SubscriptionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"
    PAUSED = "PAUSED", "Paused"


class OrganizationSubscription(AuditModel):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
        db_index=True,
    )

    auto_renew = models.BooleanField(default=True)

    starts_at = models.DateTimeField()

    expires_at = models.DateTimeField()

    next_billing_at = models.DateTimeField()

    class Meta:
        db_table = "organization_subscriptions"
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["next_billing_at"]),
            models.Index(fields=["plan", "status"]),
        ]


class PhonePeMandate(AuditModel):
    class MandateStatus(models.TextChoices):
        CREATED = "CREATED", "Created"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"
        EXPIRED = "EXPIRED", "Expired"

    subscription = models.OneToOneField(
        OrganizationSubscription,
        on_delete=models.CASCADE,
        related_name="mandate"
    )

    mandate_id = models.CharField(
        max_length=150,
        unique=True,
    )

    merchant_subscription_id = models.CharField(
        max_length=150,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=MandateStatus.choices,
        db_index=True
    )

    raw_response = models.JSONField(default=dict)

    class Meta:
        db_table = "phonepe_mandates"
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["status"]),
        ]


class PaymentStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


class SubscriptionPayment(AuditModel):
    subscription = models.ForeignKey(
        OrganizationSubscription,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    transaction_id = models.CharField(
        max_length=150,
        unique=True,
    )

    phonepe_transaction_id = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_index=True,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        db_index=True,
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True
    )
    failure_reason = models.TextField(
        blank=True,
        null=True
    )
    response_code = models.CharField(
        max_length=50,
        blank=True
    )

    response = models.JSONField(default=dict)

    class Meta:
        db_table = "subscription_payments"
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["subscription", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payment_date"]),
        ]


class PlanFeature(AuditModel):

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name="features"
    )

    feature = models.CharField(max_length=100)

    value = models.CharField(max_length=100)

    class Meta:
        db_table = "subscription_plan_features"

        indexes = [
            models.Index(fields=["plan", "feature"])
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["plan", "feature"],
                name="unique_plan_feature"
            )
        ]