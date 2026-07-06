import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from crum import get_current_request
from django.template.defaultfilters import default


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
        verbose_name="Created By",
        null=True,
    )
    updated_by = models.CharField(
        max_length=255,
        verbose_name="Updated By",
        null=True,
    )

    class Meta:
        abstract = True


class AuditModel(TimeAuditModel, UserAuditModel):
    """To path when the record was created and last modified"""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        request = get_current_request()
        if request and hasattr(request, "user"):
            if not self.created_by:
                self.created_by = str(request.user.id)
            self.updated_by = str(request.user.id)

        super().save(*args, **kwargs)


class CustomUserManager(BaseUserManager):
    def create_user(self, mobile, password="password", **extra_fields):
        if not mobile:
            raise ValueError("The Mobile Number must be set")



        user = self.model(mobile=mobile, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class UserMaster(AbstractBaseUser):
    ROLE_CHOICES = (
        ("parent", "Parent"),
        ("admin", "Admin"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mobile = models.BigIntegerField(
        validators=[MinValueValidator(1000000000), MaxValueValidator(9999999999)], unique=True
    )
    full_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    gender = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    email = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    dob = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    profile_image = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )
    is_mobile_verified = models.BooleanField(default=False)
    user_role = ArrayField(models.CharField(
        max_length=50, ),
        default=list,
        blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(
        max_length=255,
        null=True,
    )
    last_login_at = models.DateTimeField(
        null=True,
        blank=True
    )
    updated_by = models.CharField(
        max_length=255,
        null=True,
    )
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        null=True,
        blank=True
    )

    coins = models.PositiveIntegerField(
        default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS = []

    @property
    def is_admin(self):
        return "admin" in (self.user_role or [])

    @property
    def is_parent(self):
        return "parent" in (self.user_role or [])

    @property
    def display_name(self):
        return self.full_name or str(self.mobile)

    @property
    def is_profile_completed(self):
        return bool(self.full_name)


    class Meta:
        db_table = "user_master"

    def __str__(self):
        return str(self.mobile)

