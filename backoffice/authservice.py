from django.contrib.auth import authenticate
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from db.models import UserMaster, UserRole, Organization


class AuthService:

    @staticmethod
    @transaction.atomic
    def create_super_admin(data):

        if UserMaster.objects.filter(
                organization__isnull=True,
                role=UserRole.OWNER
        ).exists():
            raise Exception("Super Admin already exists.")

        user = UserMaster.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data.get("phone"),
            role=UserRole.OWNER,
            organization=None,
        )
        return user

    @staticmethod
    def login(data):
        email = data.get("email")
        password = data.get("password")
        user = authenticate(
            email=email,
            password=password
        )
        if user is None:
            raise Exception("Invalid email or password.")
        if not user.is_active:
            raise Exception("User account is inactive.")
        if user.organization is not None:
            raise Exception("Invalid login.")
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": user
        }



class OrganizationService:

    @staticmethod
    @transaction.atomic
    def create(data):
        organization_data = data["organization"]
        owner_data = data["owner"]
        if UserMaster.objects.filter(
                email=owner_data["email"]
        ).exists():
            raise Exception("Owner email already exists.")
        organization = Organization.objects.create(
            name=organization_data["name"],
            email=organization_data["email"],
            phone=organization_data.get("phone"),
            website=organization_data.get("website")
        )
        owner = UserMaster.objects.create_user(
            organization=organization,
            first_name=owner_data["first_name"],
            last_name=owner_data["last_name"],
            email=owner_data["email"],
            phone=owner_data.get("phone"),
            password=owner_data["password"],
            role=UserRole.OWNER
        )
        return organization


    @staticmethod
    def get_organizations(request):
        queryset = Organization.objects.all().order_by("-created_at")
        search = request.get("search")
        if search:
            queryset = queryset.filter(
                name__icontains=search
            )
        # is_active = request.get("is_active")
        # if is_active is not None:
        #     queryset = queryset.filter(
        #         is_active=is_active.lower() == "true"
        #     )
        page = int(request.get("page", 1))
        page_size = int(request.get("page_size", 20))
        paginator = Paginator(queryset, page_size)
        organizations = paginator.get_page(page)
        results = []
        for organization in organizations:
            results.append({
                "id": str(organization.id),
                "name": organization.name,
                "email": organization.email,
                "phone": organization.phone,
                "website": organization.website,
                "status": organization.status,
                "created_at": organization.created_at
            })
        return {
            "count": paginator.count,
            "page": page,
            "page_size": page_size,
            "results": results
        }



