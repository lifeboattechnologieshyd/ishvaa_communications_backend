from django.urls import path

from public.views import SendEmailApiView

urlpatterns = [
    path("v1/email/send", SendEmailApiView.as_view()),
]