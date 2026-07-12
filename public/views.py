from rest_framework.views import APIView

from public.service import EmailService
from shared.decorators import api_key_required
from shared.utils import CustomResponse


class SendEmailApiView(APIView):

    @api_key_required
    def post(self, request):
        print(request.organization)
        print(request.api_key)
        try:
            response = EmailService.send_email(
                organization=request.organization,
                api_key=request.api_key,
                data=request.data
            )

            return CustomResponse().successResponse(
                data=response,
                description="Email sent successfully."
            )

        except Exception as error:

            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )