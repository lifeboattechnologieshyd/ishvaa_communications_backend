from django.urls import path
from backoffice.auth import SuperAdminApiView, LoginApiView, CreateOrganizationApiView, ListOrganizationsApiView

urlpatterns = [
    path("v1/setup-super-admin",SuperAdminApiView.as_view()),
    path("v1/login",LoginApiView.as_view()),


    #######################################
    ##  Organizations
    #######################################
    path("v1/organizations",CreateOrganizationApiView.as_view()),
    path("v1/organizations/list",ListOrganizationsApiView.as_view()),
]