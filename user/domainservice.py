from django.utils import timezone

from db.models import Domain, DomainStatus
from shared.clients.email import ses_provider


class DomainService:

    @staticmethod
    def create_domain(user, data):
        domain = data["domain"].lower().strip()
        if Domain.objects.filter(domain=domain).exists():
            raise Exception("Domain already exists.")
        aws_response = ses_provider.create_email_identity(
            domain
        )
        domain_object = Domain.objects.create(
            organization=user.organization,
            domain=domain
        )
        return {
            "id": str(domain_object.id),
            "domain": domain_object.domain,
            "status": domain_object.status,
            **aws_response
        }

    @staticmethod
    def list_domains(user):
        domains = Domain.objects.filter(
            organization=user.organization
        ).values(
            "id",
            "domain",
            "status",
            "verified_at",
            "created_at"
        ).order_by("domain")
        return list(domains)

    @staticmethod
    def verify_domain(user, domain_id):
        domain = Domain.objects.filter(
            id=domain_id,
            organization=user.organization
        ).first()
        if not domain:
            raise Exception("Domain not found.")

        provider_response = ses_provider.get_email_identity(
            domain.domain
        )
        if provider_response["verified"]:
            domain.status = DomainStatus.VERIFIED
            domain.verified_at = timezone.now()
            domain.save()
        return {
            "id": str(domain.id),
            "domain": domain.domain,
            "status": domain.status,
            "verified": provider_response["verified"],
            "verification_status": provider_response["verification_status"],
            "dkim_status": provider_response["dkim_status"]
        }