from django.utils import timezone
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from db.models import SupportTickets, SupportTicketMessages, SupportTicketMessageAttachments, SupportTicketRatings
from shared.utils import CustomResponse


class CreateSupportTicketAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        title = request.data.get("title")
        description = request.data.get("description")
        if not title:
            return CustomResponse().errorResponse(data={}, description="Title is required")

        if not description:
            return CustomResponse().errorResponse(data={}, description="Description is required")

        ticket = SupportTickets.objects.create(
            user=request.user,
            title=title,
            description=description,
            last_message_at=timezone.now()
        )
        message = SupportTicketMessages.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_type="USER",
            message=description
        )
        files = request.data.get("attachments", [])
        for file in files:
            SupportTicketMessageAttachments.objects.create(
                message=message,
                file=file
            )
        return CustomResponse().successResponse(data={}, description="Ticket created successfully")

    def get(self, request):
        tickets = SupportTickets.objects.filter(
            user=request.user
        ).order_by("-updated_at")
        response = []
        for ticket in tickets:
            response.append({
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status,
                "created_at": ticket.created_at
            })
        return CustomResponse().successResponse(data=response)

class SupportTicketDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = get_object_or_404(
            SupportTickets,
            id=ticket_id,
            user=request.user
        )
        messages = []
        for msg in ticket.messages.all():
            messages.append({
                "id": msg.id,
                "sender_type": msg.sender_type,
                "message": msg.message,
                "attachments": [
                    attachment.file.url
                    for attachment in msg.attachments.all()
                ],
                "created_at": msg.created_at
            })
        return CustomResponse().successResponse(data={
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "messages": messages
        })

class SendSupportMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ticket_id = request.data["ticket_id"]
        ticket = get_object_or_404(
            SupportTickets,
            id=ticket_id,
            user=request.user
        )
        message_text = request.data.get("message")
        if not message_text:
            return CustomResponse().errorResponse(data={}, description="Message is required")
        message = SupportTicketMessages.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_type="USER",
            message=message_text
        )
        files = request.data.get("attachments", [])
        for file in files:
            SupportTicketMessageAttachments.objects.create(
                message=message,
                file=file
            )
        ticket.last_message_at = timezone.now()
        if ticket.status == "WAITING_FOR_USER":
            ticket.status = "IN_PROGRESS"
        ticket.save()
        return CustomResponse().successResponse(data={}, description="Message sent successfully")

class SubmitSupportTicketRatingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        ticket_id = request.data["ticket_id"]
        ticket = get_object_or_404(
            SupportTickets,
            id=ticket_id,
            user=request.user
        )
        if ticket.status not in ["RESOLVED", "CLOSED"]:
            return CustomResponse().errorResponse(data={}, description="Ticket is not resolved yet")

        rating = request.data.get("rating")
        feedback = request.data.get("feedback")

        if not rating:
            return CustomResponse().errorResponse(data={}, description="Rating is required")
        if int(rating) < 1 or int(rating) > 5:
            return CustomResponse().errorResponse(data={},
                                                  description="Rating must be between 1 and 5")
        SupportTicketRatings.objects.update_or_create(
            ticket=ticket,
            defaults={
                "rating": rating,
                "feedback": feedback
            }
        )
        return CustomResponse().successResponse(data={}, description="Rating submitted successfully")


