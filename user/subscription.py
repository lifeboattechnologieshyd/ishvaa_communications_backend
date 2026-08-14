import traceback
import uuid
from django.conf import settings

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from phonepe.sdk.pg.common.http_client_modules import phonepe_response

from db.models import OrganizationSubscription, Organization, OrganizationStatus
from db.models.subscription import SubscriptionPayment, PaymentStatus, SubscriptionStatus, SubscriptionPlan
from shared.clients.phonepe import phone_pe_initiate, create_upi_intent_mandate, create_upi_collect_mandate, \
    validate_subscription_webhook
from shared.clients.razorpay import create_razorpay_subscription
from shared.utils import CustomResponse
import json
import traceback

import razorpay

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

class SubscriptionPaymentAPIView(APIView):

    def post(self, request):

        organization_id = request.data.get("organization_id")
        plan_id = request.data.get("plan_id")

        if not organization_id:
            return CustomResponse().errorResponse(
                data={},
                description="Organization is required."
            )

        if not plan_id:
            return CustomResponse().errorResponse(
                data={},
                description="Plan is required."
            )

        subscription = None
        payment = None

        try:

            organization = Organization.objects.get(
                id=organization_id
            )

            plan = SubscriptionPlan.objects.get(
                id=plan_id,
                is_active=True,
            )

            print("========== CREATING RAZORPAY SUBSCRIPTION ==========")

            razorpay_response = create_razorpay_subscription(
                plan_id=plan.razorpay_plan_id,
            )

            print("========== RAZORPAY RESPONSE ==========")
            print(razorpay_response)

            razorpay_subscription_id = razorpay_response.get("id")

            with transaction.atomic():

                subscription = OrganizationSubscription.objects.create(
                    organization=organization,
                    plan=plan,
                    merchant_subscription_id=razorpay_subscription_id,
                    status=SubscriptionStatus.PENDING,
                )

                payment = SubscriptionPayment.objects.create(
                    subscription=subscription,
                    razorpay_subscription_id=razorpay_subscription_id,
                    amount=plan.amount,
                    status=PaymentStatus.INITIATED,
                    response=razorpay_response,
                )

            print("Subscription Created :", subscription.id)
            print("Payment Created :", payment.id)

            return CustomResponse().successResponse(
                data={
                    "subscription_id": str(subscription.id),
                    "payment_id": str(payment.id),
                    "checkout_data": razorpay_response,
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

        except Exception as exc:

            traceback.print_exc()

            print("========== RAZORPAY ERROR ==========")
            print(str(exc))

            if payment:

                payment.status = PaymentStatus.FAILED
                payment.failure_reason = str(exc)

                payment.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                    ]
                )

            if subscription:

                subscription.status = SubscriptionStatus.FAILED

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            return CustomResponse().errorResponse(
                data={},
                description=str(exc)
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

            callback_response = validate_subscription_webhook(
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





class RazorpayWebhookAPIView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):

        print("\n========== RAZORPAY WEBHOOK ==========")

        body = request.body.decode("utf-8")
        signature = request.headers.get("X-Razorpay-Signature")

        print("Signature:", signature)
        print("Body:", body)

        try:

            client = razorpay.Client(
                auth=(
                    settings.RAZORPAY_KEY_ID,
                    settings.RAZORPAY_KEY_SECRET,
                )
            )

            client.utility.verify_webhook_signature(
                body,
                signature,
                settings.RAZORPAY_WEBHOOK_SECRET,
            )

            print("Webhook Signature Verified")

        except Exception:

            print("========== INVALID SIGNATURE ==========")
            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description="Invalid webhook signature"
            )

        payload = json.loads(body)

        event = payload.get("event")

        print("Event:", event)

        subscription_entity = (
            payload.get("payload", {})
            .get("subscription", {})
            .get("entity", {})
        )

        payment_entity = (
            payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        merchant_subscription_id = subscription_entity.get("id")

        if not merchant_subscription_id:
            merchant_subscription_id = payment_entity.get("subscription_id")

        if not merchant_subscription_id:

            return CustomResponse().successResponse(
                data={},
                description="Subscription not found in webhook"
            )

        subscription = OrganizationSubscription.objects.filter(
            merchant_subscription_id=merchant_subscription_id
        ).first()

        if subscription is None:

            return CustomResponse().successResponse(
                data={},
                description="Subscription not found"
            )

        payment = SubscriptionPayment.objects.filter(
            subscription=subscription
        ).order_by("-created_at").first()

        try:

            if event == "subscription.authenticated":

                print("Subscription Authenticated")

                subscription.status = SubscriptionStatus.PENDING

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            elif event == "subscription.activated":

                print("Subscription Activated")

                subscription.status = SubscriptionStatus.ACTIVE
                subscription.starts_at = timezone.now()

                subscription.save(
                    update_fields=[
                        "status",
                        "starts_at",
                    ]
                )

            elif event == "subscription.charged":

                print("Subscription Charged")

                if payment:

                    payment.status = PaymentStatus.SUCCESS
                    payment.payment_date = timezone.now()
                    payment.response = payload

                    if payment_entity:
                        payment.razorpay_payment_id = payment_entity.get("id")

                    payment.save(
                        update_fields=[
                            "status",
                            "payment_date",
                            "response",
                            "razorpay_payment_id",
                        ]
                    )

            elif event == "payment.captured":

                print("Payment Captured")

                if payment:

                    payment.status = PaymentStatus.SUCCESS
                    payment.payment_date = timezone.now()
                    payment.response = payload
                    payment.razorpay_payment_id = payment_entity.get("id")

                    payment.save(
                        update_fields=[
                            "status",
                            "payment_date",
                            "response",
                            "razorpay_payment_id",
                        ]
                    )

            elif event == "payment.failed":

                print("Payment Failed")

                subscription.status = SubscriptionStatus.FAILED

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                if payment:

                    payment.status = PaymentStatus.FAILED
                    payment.failure_reason = payment_entity.get(
                        "error_description"
                    )
                    payment.response = payload

                    if payment_entity:
                        payment.razorpay_payment_id = payment_entity.get("id")

                    payment.save(
                        update_fields=[
                            "status",
                            "failure_reason",
                            "response",
                            "razorpay_payment_id",
                        ]
                    )

            elif event == "subscription.cancelled":

                print("Subscription Cancelled")

                subscription.status = SubscriptionStatus.CANCELLED
                subscription.auto_renew = False

                subscription.save(
                    update_fields=[
                        "status",
                        "auto_renew",
                    ]
                )

            elif event == "subscription.completed":

                print("Subscription Completed")

                subscription.status = SubscriptionStatus.EXPIRED
                subscription.expires_at = timezone.now()

                subscription.save(
                    update_fields=[
                        "status",
                        "expires_at",
                    ]
                )

            elif event == "subscription.paused":

                print("Subscription Paused")

                subscription.status = SubscriptionStatus.PAUSED

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            elif event == "subscription.resumed":

                print("Subscription Resumed")

                subscription.status = SubscriptionStatus.ACTIVE

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            else:

                print("Unhandled Event:", event)

        except Exception:

            print("========== WEBHOOK ERROR ==========")
            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description="Webhook processing failed"
            )

        print("========== WEBHOOK SUCCESS ==========")

        return CustomResponse().successResponse(
            data={},
            description="Webhook processed successfully"
        )


class SubscriptionPlanView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):

        try:

            plans = SubscriptionPlan.objects.filter(
                is_active=True
            ).order_by("amount")

            response = []

            for plan in plans:

                response.append({
                    "id": str(plan.id),
                    "name": plan.name,
                    "code": plan.code,
                    "amount": str(plan.amount),
                    "billing_cycle": plan.billing_cycle,
                    "emails_per_month": plan.emails_per_month,
                    "is_active": plan.is_active,
                })

            return CustomResponse().successResponse(
                data=response,
                description="Subscription plans fetched successfully."
            )

        except Exception as e:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description=str(e)
            )