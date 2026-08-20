import traceback

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from db.models import UserOTP
from shared.permissions import organization_management_required
from shared.utils import CustomResponse
from user.api_keys.keyservice import ApiKeyService
from user.domainservice import DomainService
from user.service import AuthService
import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone


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




class SendOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email")
        phone = request.data.get("phone")

        if not email and not phone:
            return CustomResponse().errorResponse(
                data={},
                description="Email or phone is required."
            )

        otp = str(random.randint(1000, 9999))

        try:

            with transaction.atomic():

                if email:

                    UserOTP.objects.filter(
                        email=email,
                        is_used=False,
                    ).delete()

                    UserOTP.objects.create(
                        email=email,
                        otp=otp,
                        expires_at=timezone.now() + timedelta(minutes=10),
                    )

                    # send_email(email, otp)

                    print("Email OTP:", otp)

                    response = {
                        "email": email,
                        "otp": otp,
                    }

                else:

                    UserOTP.objects.filter(
                        phone=phone,
                        is_used=False,
                    ).delete()

                    UserOTP.objects.create(
                        phone=phone,
                        otp=otp,
                        expires_at=timezone.now() + timedelta(minutes=10),
                    )

                    # send_sms(phone, otp)

                    print("Phone OTP:", otp)

                    response = {
                        "phone": phone,
                        "otp": otp,
                    }

            return CustomResponse().successResponse(
                data=response,
                description="OTP sent successfully."
            )

        except Exception as e:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description=str(e)
            )


class VerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email")
        phone = request.data.get("phone")
        otp = request.data.get("otp")

        if not otp:
            return CustomResponse().errorResponse(
                data={},
                description="OTP is required."
            )

        if not email and not phone:
            return CustomResponse().errorResponse(
                data={},
                description="Email or phone is required."
            )

        try:

            if email:

                otp_obj = UserOTP.objects.filter(
                    email=email,
                    otp=otp,
                    is_used=False,
                ).order_by("-created_at").first()

            else:

                otp_obj = UserOTP.objects.filter(
                    phone=phone,
                    otp=otp,
                    is_used=False,
                ).order_by("-created_at").first()

            if otp_obj is None:

                return CustomResponse().errorResponse(
                    data={},
                    description="Invalid OTP."
                )

            if otp_obj.expires_at < timezone.now():

                return CustomResponse().errorResponse(
                    data={},
                    description="OTP has expired."
                )

            otp_obj.is_used = True

            otp_obj.save(
                update_fields=[
                    "is_used",
                ]
            )

            if otp_obj.user:

                if email:

                    otp_obj.user.email_verified = True

                    otp_obj.user.save(
                        update_fields=[
                            "email_verified",
                        ]
                    )

                if phone:

                    otp_obj.user.phone_verified = True

                    otp_obj.user.save(
                        update_fields=[
                            "phone_verified",
                        ]
                    )

            return CustomResponse().successResponse(
                data={},
                description="OTP verified successfully."
            )

        except Exception as e:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description=str(e)
            )