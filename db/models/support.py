import uuid

from django.db import models

from db.models import AuditModel, UserMaster


class SupportTickets(AuditModel):

    STATUS = (
        ("OPEN", "OPEN"),
        ("IN_PROGRESS", "IN_PROGRESS"),
        ("WAITING_FOR_USER", "WAITING_FOR_USER"),
        ("RESOLVED", "RESOLVED"),
        ("CLOSED", "CLOSED"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="support_tickets"
    )

    title = models.CharField(
        max_length=255
    )

    description = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=STATUS,
        default="OPEN"
    )

    assigned_to = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    last_message_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = "support_tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title}"


class SupportTicketMessages(AuditModel):

    SENDER_TYPE = (
        ("USER", "USER"),
        ("ADMIN", "ADMIN"),
        ("SYSTEM", "SYSTEM"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    ticket = models.ForeignKey(
        SupportTickets,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender_type = models.CharField(
        max_length=20,
        choices=SENDER_TYPE
    )

    sender = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    message = models.TextField(
        blank=True,
        default=""
    )

    class Meta:
        db_table = "support_ticket_messages"
        ordering = ["created_at"]

    def __str__(self):
        return str(self.id)

class SupportTicketMessageAttachments(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    message = models.ForeignKey(
        SupportTicketMessages,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    file = models.CharField(max_length=500)

    class Meta:
        db_table = "support_ticket_message_attachments"

    def __str__(self):
        return str(self.id)


class SupportTicketRatings(AuditModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    ticket = models.OneToOneField(
        SupportTickets,
        on_delete=models.CASCADE,
        related_name="rating"
    )
    rating = models.PositiveSmallIntegerField()
    feedback = models.TextField(null=True,blank=True)
    class Meta:
        db_table = "support_ticket_ratings"

    def __str__(self):
        return str(self.rating)