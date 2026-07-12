from rest_framework.views import APIView

from shared.permissions import organization_management_required
from shared.utils import CustomResponse
from user.api_keys.keyservice import ApiKeyService
from user.domainservice import DomainService
from user.service import AuthService

class LoginApiView(APIView):
    def post(self, request):
        data = request.data
        required_fields = [
            "email",
            "password"
        ]
        for field in required_fields:
            if not data.get(field):
                return CustomResponse().errorResponse(
                    data={},
                    description=f"{field} is required."
                )
        try:
            response = AuthService.login(data)
            user = response["user"]
            return CustomResponse().successResponse(
                data={
                    "access_token": response["access_token"],
                    "refresh_token": response["refresh_token"],
                    "user": {
                        "id": str(user.id),
                        "name": user.full_name,
                        "email": user.email,
                        "role": user.role,
                        "organization_id": str(user.organization.id) if user.organization else None
                    }
                },
                description="Login successful."
            )
        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )


class CreateApiKeyApiView(APIView):

    @organization_management_required
    def post(self, request):
        data = request.data
        if not data.get("name"):
            return CustomResponse().errorResponse(
                data={},
                description="Name is required."
            )
        try:
            response = ApiKeyService.create_api_key(
                request.user,
                data
            )
            return CustomResponse().successResponse(
                data=response,
                description="API Key generated successfully."
            )
        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=f"{error}"
            )

class ListApiKeyApiView(APIView):
    @organization_management_required
    def get(self, request):
        response = ApiKeyService.list_api_keys(
            request.user
        )
        return CustomResponse().successResponse(
            data=response,
            description="API Keys fetched successfully."
        )

class CreateDomainApiView(APIView):
    @organization_management_required
    def post(self, request):
        data = request.data
        if not data.get("domain"):
            return CustomResponse().errorResponse(
                data={},
                description="Domain is required."
            )
        try:
            response = DomainService.create_domain(
                request.user,
                data
            )
            return CustomResponse().successResponse(
                data=response,
                description="Domain added successfully."
            )
        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )

class ListDomainApiView(APIView):
    @organization_management_required
    def get(self, request):
        response = DomainService.list_domains(
            request.user
        )
        return CustomResponse().successResponse(
            data=response,
            description="Domains fetched successfully."
        )

class VerifyDomainApiView(APIView):

    @organization_management_required
    def post(self, request, domain_id):
        try:
            response = DomainService.verify_domain(
                request.user,
                domain_id
            )
            return CustomResponse().successResponse(
                data=response,
                description="Domain verification checked successfully."
            )
        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )