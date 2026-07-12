from rest_framework.views import APIView
from backoffice.authservice import AuthService, OrganizationService
from shared.permissions import super_admin_required
from shared.utils import CustomResponse

class SuperAdminApiView(APIView):

    def post(self, request):
        data = request.data
        required_fields = ["first_name","last_name","email","password"]
        for field in required_fields:
            if not data.get(field):
                return CustomResponse().errorResponse(data={},
                                                      description=f"{field} is required.")
        try:
            user = AuthService.create_super_admin(data)
            return CustomResponse().successResponse(data={
                "id": str(user.id),
                "email": user.email,
                "name": user.full_name
            },
            description="Super Admin created successfully.")
        except Exception as error:
            return CustomResponse().errorResponse(data={},
                                                  description=str(error))

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


class CreateOrganizationApiView(APIView):
    @super_admin_required
    def post(self, request):
        data = request.data
        organization = data.get("organization")
        owner = data.get("owner")
        if not organization:
            return CustomResponse().errorResponse(
                data={},
                description="Organization details are required."
            )
        if not owner:
            return CustomResponse().errorResponse(
                data={},
                description="Owner details are required."
            )
        try:
            organization = OrganizationService.create(
                data=data,
            )
            return CustomResponse().successResponse(
                data={
                    "id": str(organization.id)
                },
                description="Organization created successfully."
            )
        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )

class ListOrganizationsApiView(APIView):
    @super_admin_required
    def get(self, request):
        try:
            data = OrganizationService.get_organizations(request.GET)
            return CustomResponse().successResponse(
                data=data,
                description="Organizations fetched successfully."
            )
        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )