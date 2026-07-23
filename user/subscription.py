import uuid

from dateutil.relativedelta import relativedelta
from django.utils import timezone
from rest_framework.views import APIView

from db.models import OrganizationSubscription, Organization, OrganizationStatus
from db.models.subscription import SubscriptionPayment, PaymentStatus, SubscriptionStatus, SubscriptionPlan
from shared.clients.phonepe import phone_pe_initiate, create_upi_intent_mandate, create_upi_collect_mandate, \
    validate_phonepe_webhook
from shared.utils import CustomResponse


class SubscriptionPaymentAPIView(APIView):

    def post(self, request):
        print("\n========== SUBSCRIPTION PAYMENT API ==========")

        data = request.data
        print("Request Data:", data)

        required_fields = [
            "organization_id",
            "plan_id",
        ]

        for field in required_fields:
            if data.get(field) in [None, ""]:
                print(f"{field} is missing.")
                return CustomResponse().errorResponse(
                    data={},
                    description=f"{field.replace('_', ' ').title()} is required."
                )

        try:
            print("\nFetching Organization...")
            organization = Organization.objects.get(
                id=data.get("organization_id")
            )
            print("Organization Found:", organization.id)

            print("\nFetching Subscription Plan...")
            plan = SubscriptionPlan.objects.get(
                id=data.get("plan_id"),
                is_active=True,
            )
            print("Plan Found:", plan.id)
            print("Plan Name:", plan.name)
            print("Plan Amount:", plan.amount)
            print("Plan Amount Type:", type(plan.amount))

            merchant_order_id = str(uuid.uuid4())
            merchant_subscription_id = str(uuid.uuid4())

            print("\nCreating Organization Subscription...")
            subscription = OrganizationSubscription.objects.create(
                organization=organization,
                plan=plan,
                status=SubscriptionStatus.PENDING,
                merchant_subscription_id=merchant_subscription_id,
            )
            print("Subscription Created:", subscription.id)



            print("\nGenerated IDs")
            print("Merchant Order ID:", merchant_order_id)
            print("Merchant Subscription ID:", merchant_subscription_id)

            print("\nCreating Subscription Payment...")
            payment = SubscriptionPayment.objects.create(
                subscription=subscription,
                merchant_subscription_id=merchant_subscription_id,
                transaction_id=merchant_order_id,
                amount=plan.amount,
                status=PaymentStatus.PENDING,
            )

            print("Payment Created:", payment.id)
            print("Payment Amount:", payment.amount)
            print("Payment Amount Type:", type(payment.amount))

            amount_in_paise = int(float(plan.amount) * 100)

            print("\nCalling PhonePe...")
            print("Merchant Order ID:", merchant_order_id)
            print("Merchant Subscription ID:", merchant_subscription_id)
            print("Amount (Rupees):", plan.amount)
            print("Amount (Paise):", amount_in_paise)
            print("VPA:", data.get("vpa"))

            phonepe_response = create_upi_collect_mandate(
                merchant_order_id=merchant_order_id,
                merchant_subscription_id=merchant_subscription_id,
                amount=amount_in_paise,
                vpa=data.get("vpa"),
            )
            payment.response = phonepe_response
            payment.status = PaymentStatus.PENDING  # pending user action now
            payment.save()

            print("\nPhonePe Response:")
            print(phonepe_response)

            print("\n========== PAYMENT INITIATED SUCCESSFULLY ==========\n")

            return CustomResponse().successResponse(
                data={
                    "subscription_id": str(subscription.id),
                    "payment_id": str(payment.id),
                    "phonepe_response": phonepe_response,
                },
                description="Payment initiated successfully."
            )

        except Organization.DoesNotExist:
            print("Organization not found.")
            return CustomResponse().errorResponse(
                data={},
                description="Organization not found."
            )

        except SubscriptionPlan.DoesNotExist:
            print("Subscription plan not found.")
            return CustomResponse().errorResponse(
                data={},
                description="Subscription plan not found."
            )

        except Exception as error:
            print("\n========== EXCEPTION ==========")
            print(type(error).__name__)
            print(str(error))
            print("================================\n")

            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )

class PhonePeWebhookAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            print("========== PHONEPE WEBHOOK RECEIVED ==========")

            auth_header = request.headers.get("Authorization")
            raw_body = request.body.decode("utf-8")

            print("Authorization Header :", auth_header)
            print("Raw Body :", raw_body)

            callback_response = validate_phonepe_webhook(
                auth_header=auth_header,
                raw_body=raw_body,
            )

            print("Webhook Validation Success")
            print("Callback Response :", callback_response)

            payload = request.data

            print("Payload :", payload)

            merchant_order_id = payload.get("merchantOrderId")
            payment_status = payload.get("state")
            phonepe_transaction_id = payload.get("transactionId")

            print("Merchant Order ID :", merchant_order_id)
            print("Payment Status :", payment_status)
            print("PhonePe Transaction ID :", phonepe_transaction_id)

            payment = SubscriptionPayment.objects.get(
                transaction_id=merchant_order_id
            )

            print("Payment Found :", payment.id)

            payment.phonepe_transaction_id = phonepe_transaction_id
            payment.response = payload
            payment.payment_date = timezone.now()

            if payment_status == "COMPLETED":

                print("Payment Successful")

                payment.status = PaymentStatus.SUCCESS
                payment.save()

                subscription = payment.subscription

                subscription.status = SubscriptionStatus.ACTIVE
                subscription.starts_at = timezone.now()
                subscription.expires_at = timezone.now() + relativedelta(months=1)
                subscription.next_billing_at = subscription.expires_at
                subscription.save()

                print("Subscription Activated")

                organization = subscription.organization
                organization.status = OrganizationStatus.ACTIVE
                organization.save()

                print("Organization Activated")

            elif payment_status == "FAILED":

                print("Payment Failed")

                payment.status = PaymentStatus.FAILED
                payment.save()

            elif payment_status == "PENDING":

                print("Payment Pending")

                payment.status = PaymentStatus.PENDING
                payment.save()

            print("Webhook Processed Successfully")

            return CustomResponse().successResponse(
                data={},
                description="Webhook processed successfully."
            )

        except SubscriptionPayment.DoesNotExist:

            print("Subscription Payment Not Found")

            return CustomResponse().errorResponse(
                data={},
                description="Subscription payment not found."
            )

        except Exception as error:

            print("Webhook Error :", str(error))

            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )



class OrganizationSubscriptionAPIView(APIView):

    def get(self, request):
        organization_id = request.query_params.get("organization_id")

        if not organization_id:
            return CustomResponse().errorResponse(
                data={},
                description="Organization Id is required."
            )

        try:
            subscriptions = OrganizationSubscription.objects.filter(
                organization_id=organization_id
            ).select_related(
                "plan"
            ).order_by("-created_at")

            data = []

            for subscription in subscriptions:
                data.append({
                    "id": str(subscription.id),
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

        except Exception as error:
            return CustomResponse().errorResponse(
                data={},
                description=str(error)
            )