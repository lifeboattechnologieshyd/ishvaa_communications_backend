import uuid
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from db.models import Organization, AuditModel

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.OWNER)
        return self.create_user(email, password, **extra_fields)

class UserRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    MEMBER = "MEMBER", "Member"


class UserMaster(AuditModel, AbstractBaseUser):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users"
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100,blank=True)
    email = models.EmailField(
        unique=True
    )
    phone = models.CharField(
        max_length=15,
        unique=True,
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.MEMBER,
        db_index=True
    )
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    avatar = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 path or image URL"
    )
    last_login = models.DateTimeField(
        blank=True,
        null=True
    )
    objects = CustomUserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    class Meta:
        db_table = "user_master"
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.email

