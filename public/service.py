from db.models import Domain, DomainStatus, EmailLog, EmailStatus
from shared.clients.email import ses_provider


class EmailService:

    @staticmethod
    def send_email(organization, api_key, data):
        sender = data.get("from")
        recipients = data.get("to")
        subject = data.get("subject")
        html = data.get("html")
        reply_to = data.get("reply-to", None)

        if not sender:
            raise Exception("From email is required.")

        if not recipients:
            raise Exception("Recipients are required.")

        if not subject:
            raise Exception("Subject is required.")

        if not html:
            raise Exception("HTML content is required.")

        sender_domain = sender.split("@")[1].lower()

        domain = Domain.objects.filter(
            organization=organization,
            domain=sender_domain,
            status=DomainStatus.VERIFIED
        ).first()

        if not domain:
            raise Exception("Sender domain is not verified.")

        response = ses_provider.send(
            sender=sender,
            recipients=recipients,
            subject=subject,
            html=html,
            reply_to=reply_to
        )

        email = EmailLog.objects.create(
            organization=organization,
            api_key=api_key,
            provider_message_id=response["message_id"],
            sender=sender,
            recipients=recipients,
            subject=subject,
            html=html,
            status=EmailStatus.SENT
        )

        return {
            "id": str(email.id),
            "message_id": response["message_id"],
            "status": email.status
        }