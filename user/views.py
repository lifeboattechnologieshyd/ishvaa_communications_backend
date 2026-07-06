from django.urls import path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class TestAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "success": True,
                "message": "Ishvaa Communications API is working successfully.",
                "environment": "development",
            },
            status=status.HTTP_200_OK,
        )


