from rest_framework.views import APIView

from db.models.subscription import SubscriptionPlan, PlanFeature
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