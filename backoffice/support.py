from django.db.models import Q
from django.utils import timezone
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

# from config.firebase import send_visible_push_notification
from db.models import SupportTickets, SupportTicketMessages, SupportTicketMessageAttachments
from shared.utils import CustomResponse


class AdminSupportTicketsAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        tickets = SupportTickets.objects.all()

        status_filter = request.GET.get("status")
        search = request.GET.get("search")

        if status_filter:
            tickets = tickets.filter(status=status_filter)

        if search:
            tickets = tickets.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )

        tickets = tickets.order_by("-last_message_at")

        response = []

        for ticket in tickets:

            response.append({
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status,
                "user_id": ticket.user.id,
                "user_name": getattr(ticket.user, "name", ""),
                "assigned_to": (
                    ticket.assigned_to.id
                    if ticket.assigned_to
                    else None
                ),
                "created_at": ticket.created_at,
            })
        return CustomResponse().successResponse(data=response)


class AdminSupportTicketDetailAPIView(APIView):

    def get(self, request):
        ticket_id = request.GET.get("ticket_id")
        ticket = get_object_or_404(
            SupportTickets,
            id=ticket_id
        )
        messages = []
        for msg in ticket.messages.all():
            messages.append({
                "id": msg.id,
                "sender_type": msg.sender_type,
                "message": msg.message,
                "attachments": [
                    attachment.file
                    for attachment in msg.attachments.all()
                ],
                "created_at": msg.created_at
            })
        rating = None
        if hasattr(ticket, "rating"):
            rating = {
                "rating": ticket.rating.rating,
                "feedback": ticket.rating.feedback
            }
        return CustomResponse().successResponse(data={
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "user_id": ticket.user.id,
            "user_name": getattr(ticket.user, "name", ""),
            "assigned_to": (
                ticket.assigned_to.id
                if ticket.assigned_to
                else None
            ),
            "messages": messages,
            "rating": rating
        })


class AdminReplySupportTicketAPIView(APIView):

    def post(self, request):
        ticket_id = request.data["ticket_id"]
        ticket = get_object_or_404(
            SupportTickets,
            id=ticket_id
        )
        message_text = request.data.get("message")
        if not message_text:
            return CustomResponse().errorResponse(data={}, description="Message is required")
        message = SupportTicketMessages.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_type="ADMIN",
            message=message_text
        )
        files = request.FILES.getlist("attachments")
        for file in files:
            SupportTicketMessageAttachments.objects.create(
                message=message,
                file=file
            )

        ticket.last_message_at = timezone.now()
        if ticket.status == "IN_PROGRESS":
            ticket.status = "WAITING_FOR_USER"
        ticket.save()
        print("we are sending push notification to user")
        # resp = send_visible_push_notification(
        #     user=ticket.user,
        #     title="Support Team Replied",
        #     body="We have replied to your support ticket.",
        #     notification_type="SUPPORT_REPLY",
        #     payload={
        #         "ticket_id": str(ticket.id)
        #     }
        # )
        # print(resp)
        print("we sent push notification to user")
        return CustomResponse().successResponse(data={
            "message": "Reply sent successfully"
        }, description="")

class AdminUpdateSupportTicketStatusAPIView(APIView):

    def post(self, request):
        ticket_id = request.data["ticket_id"]
        ticket = get_object_or_404(
            SupportTickets,
            id=ticket_id
        )
        status_value = request.data.get("status")
        allowed_statuses = [
            "OPEN",
            "IN_PROGRESS",
            "WAITING_FOR_USER",
            "RESOLVED",
            "CLOSED"
        ]

        if status_value not in allowed_statuses:
            return CustomResponse().errorResponse(data={},
                                                  description="Invalid status")
        ticket.status = status_value
        if status_value == "RESOLVED":
            ticket.resolved_at = timezone.now()
        if status_value == "CLOSED":
            ticket.closed_at = timezone.now()
        ticket.save()
        SupportTicketMessages.objects.create(
            ticket=ticket,
            sender_type="SYSTEM",
            message=f"Ticket status changed to {status_value}"
        )
        return CustomResponse().successResponse(
            data={
                "message": "Status updated successfully"
            },
            description="Status updated successfully")