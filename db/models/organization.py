from django.db import models
from db.models import AuditModel


class OrganizationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"


class Organization(AuditModel):
    name = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
    )
    email = models.EmailField(
        unique=True,
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )
    website = models.CharField(
        max_length=40,
        blank=True,
        null=True,
    )
    logo = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 object path or public URL",
    )
    timezone = models.CharField(
        max_length=100,
        default="Asia/Kolkata",
    )
    currency = models.CharField(
        max_length=10,
        default="INR",
    )
    language = models.CharField(
        max_length=10,
        default="en",
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    class Meta:
        db_table = "organizations"
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ApiKey(AuditModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="api_keys"
    )
    name = models.CharField(
        max_length=100
    )
    prefix = models.CharField(
        max_length=20,
        db_index=True
    )
    secret_hash = models.CharField(
        max_length=255
    )
    is_active = models.BooleanField(
        default=True
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.name} - {self.name}"
    
class DomainStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    FAILED = "FAILED", "Failed"

class Domain(AuditModel):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="domains",
        db_index=True
    )

    domain = models.CharField(
        max_length=255,
        unique=True,
        db_index=True
    )

    status = models.CharField(
        max_length=20,
        choices=DomainStatus.choices,
        default=DomainStatus.PENDING,
        db_index=True
    )
    provider_status = models.CharField(
        max_length=30,
        default="PENDING"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )
    class Meta:
        db_table = "organization_domains"
        ordering = ["domain"]

    def __str__(self):
        return self.domain