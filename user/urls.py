from django.urls import path

from user.subscription import SubscriptionPaymentAPIView, PhonePeWebhookAPIView
from user.support import CreateSupportTicketAPIView, SupportTicketDetailAPIView, SendSupportMessageAPIView, \
    SubmitSupportTicketRatingAPIView
from user.views import LoginApiView, CreateApiKeyApiView, CreateDomainApiView, ListDomainApiView, VerifyDomainApiView, \
    ListApiKeyApiView

urlpatterns = [
    path("v1/login", LoginApiView.as_view()),
    path("v1/create-api-key", CreateApiKeyApiView.as_view()),
    path("v1/api-keys", ListApiKeyApiView.as_view()),

    path("v1/domain", CreateDomainApiView.as_view()),
    path("v1/domain/list", ListDomainApiView.as_view()),
    path("v1/domain/<uuid:domain_id>/verify", VerifyDomainApiView.as_view()),

    path("create/payment",SubscriptionPaymentAPIView.as_view()),
    path("webhook",PhonePeWebhookAPIView.as_view()),

    #############################################
    ## Support Urls
    #############################################

    path("support/tickets", CreateSupportTicketAPIView.as_view()),
    path("support/tickets/<uuid:ticket_id>/", SupportTicketDetailAPIView.as_view()),
    path("support/tickets/message", SendSupportMessageAPIView.as_view()),
    path("support/tickets/rate", SubmitSupportTicketRatingAPIView.as_view()),

]