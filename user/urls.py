from django.urls import path

from user.views import LoginApiView, CreateApiKeyApiView, CreateDomainApiView, ListDomainApiView, VerifyDomainApiView, \
    ListApiKeyApiView

urlpatterns = [
    path("v1/login", LoginApiView.as_view()),
    path("v1/create-api-key", CreateApiKeyApiView.as_view()),
    path("v1/api-keys", ListApiKeyApiView.as_view()),

    path("v1/domain", CreateDomainApiView.as_view()),
    path("v1/domain/list", ListDomainApiView.as_view()),
    path("v1/domain/<uuid:domain_id>/verify", VerifyDomainApiView.as_view()),

]