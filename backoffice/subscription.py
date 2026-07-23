from rest_framework.views import APIView

from db.models import Organization
from db.models.subscription import SubscriptionPlan, PlanFeature, OrganizationSubscription, SubscriptionStatus
from shared.utils import CustomResponse


class SubscriptionPlanAPIView(APIView):

    def post(self, request):
        data = request.data

        if not data.get("name"):
            return CustomResponse().errorResponse(
                data={},
                description="Name is required."
            )

        if not data.get("code"):
            return CustomResponse().errorResponse(
                data={},
                description="Code is required."
            )

        if data.get("amount") is None:
            return CustomResponse().errorResponse(
                data={},
                description="Amount is required."
            )

        if not data.get("billing_cycle"):
            return CustomResponse().errorResponse(
                data={},
                description="Billing cycle is required."
            )

        if data.get("emails_per_month") is None:
            return CustomResponse().errorResponse(
                data={},
                description="Emails per month is required."
            )

        try:
            plan = SubscriptionPlan.objects.create(
                name=data.get("name"),
                code=data.get("code"),
                amount=data.get("amount"),
                billing_cycle=data.get("billing_cycle"),
                emails_per_month=data.get("emails_per_month"),
                is_active=data.get("is_active", True),
            )

            return CustomResponse().successResponse(
                data={
                    "id": str(plan.id)
                },
                description="Subscription plan created successfully."
            )

        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )

    def get(self, request):
        plans = SubscriptionPlan.objects.all().values(
            "id",
            "name",
            "code",
            "amount",
            "billing_cycle",
            "emails_per_month",
            "is_active",
        )

        return CustomResponse().successResponse(
            data=list(plans),
            description="Subscription plans fetched successfully."
        )


class PlanFeatureAPIView(APIView):

    def post(self, request):
        data = request.data

        if not data.get("plan_id"):
            return CustomResponse().errorResponse(
                data={},
                description="Plan ID is required."
            )

        if not data.get("feature"):
            return CustomResponse().errorResponse(
                data={},
                description="Feature is required."
            )

        if data.get("value") is None:
            return CustomResponse().errorResponse(
                data={},
                description="Value is required."
            )

        try:
            plan = SubscriptionPlan.objects.get(
                id=data.get("plan_id")
            )

            feature = PlanFeature.objects.create(
                plan=plan,
                feature=data.get("feature"),
                value=data.get("value"),
            )

            return CustomResponse().successResponse(
                data={
                    "id": str(feature.id)
                },
                description="Plan feature created successfully."
            )

        except SubscriptionPlan.DoesNotExist:
            return CustomResponse().errorResponse(
                data={},
                description="Subscription plan not found."
            )

        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )

    def get(self, request):
        features = PlanFeature.objects.select_related("plan").values(
            "id",
            "plan_id",
            "plan__name",
            "feature",
            "value",
        )

        return CustomResponse().successResponse(
            data=list(features),
            description="Plan features fetched successfully."
        )


class OrganizationSubscriptionAPIView(APIView):

    def post(self, request):
        data = request.data

        required_fields = [
            "organization_id",
            "plan_id",
        ]

        for field in required_fields:
            if data.get(field) in [None, ""]:
                return CustomResponse().errorResponse(
                    data={},
                    description=f"{field.replace('_', ' ').title()} is required."
                )

        try:
            organization = Organization.objects.get(
                id=data.get("organization_id")
            )

            plan = SubscriptionPlan.objects.get(
                id=data.get("plan_id"),
                is_active=True
            )

            subscription = OrganizationSubscription.objects.create(
                organization=organization,
                plan=plan,
                status=SubscriptionStatus.PENDING,
                auto_renew=data.get("auto_renew", True),
            )

            return CustomResponse().successResponse(
                data={
                    "id": str(subscription.id)
                },
                description="Subscription created successfully."
            )

        except Organization.DoesNotExist:
            return CustomResponse().errorResponse(
                data={},
                description="Organization not found."
            )

        except SubscriptionPlan.DoesNotExist:
            return CustomResponse().errorResponse(
                data={},
                description="Subscription plan not found."
            )

        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )

    def get(self, request):

        organization_id = request.query_params.get("organization_id")

        subscriptions = OrganizationSubscription.objects.filter(
            organization_id=organization_id
        ).select_related(
            "organization",
            "plan"
        )

        data = []

        for subscription in subscriptions:
            data.append({
                "id": str(subscription.id),
                "organization": subscription.organization.name,
                "plan": subscription.plan.name,
                "status": subscription.status,
                "auto_renew": subscription.auto_renew,
                "starts_at": subscription.starts_at,
                "expires_at": subscription.expires_at,
                "next_billing_at": subscription.next_billing_at,
            })

        return CustomResponse().successResponse(
            data=data,
            description="Subscriptions fetched successfully."
        )