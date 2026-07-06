from django.urls import path

from user.views import TestAPIView

urlpatterns = [
    path("test/", TestAPIView.as_view(), name="test-api"),


]