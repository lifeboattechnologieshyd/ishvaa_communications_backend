from django.urls import path
from backoffice.auth import SuperAdminApiView, LoginApiView, CreateOrganizationApiView, ListOrganizationsApiView
from backoffice.subscription import SubscriptionPlanAPIView, PlanFeatureAPIView, OrganizationSubscriptionAPIView

urlpatterns = [
    path("v1/setup-super-admin",SuperAdminApiView.as_view()),
    path("v1/login",LoginApiView.as_view()),


    #######################################
    ##  Organizations
    #######################################
    path("v1/organizations",CreateOrganizationApiView.as_view()),
    path("v1/organizations/list",ListOrganizationsApiView.as_view()),

    path("subscription/plan",SubscriptionPlanAPIView.as_view()),
    path("feature/plan",PlanFeatureAPIView.as_view()),
    path("organization-subscription",OrganizationSubscriptionAPIView.as_view()),
]