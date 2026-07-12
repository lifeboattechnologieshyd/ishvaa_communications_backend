from django.db import models

class PortalType(models.TextChoices):
    BACKOFFICE = "BACKOFFICE", "Backoffice"
    PORTAL = "PORTAL", "Portal"