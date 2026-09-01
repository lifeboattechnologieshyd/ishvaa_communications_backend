import traceback
import uuid
from django.conf import settings
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from phonepe.sdk.pg.common.http_client_modules import phonepe_response
from razorpay.errors import SignatureVerificationError
from django.db.models import OuterRef, Subquery, Prefetch

from db.models import OrganizationSubscription, Organization, OrganizationStatus
from db.models.subscription import SubscriptionPayment, PaymentStatus, SubscriptionStatus, SubscriptionPlan, \
    BillingCycle
from shared.clients.phonepe import phone_pe_initiate, create_upi_intent_mandate, create_upi_collect_mandate, \
    validate_subscription_webhook
from shared.clients.razorpay import create_razorpay_subscription, get_razorpay_client
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

    def get_organizations(self):
        organizations = Organization.objects.prefetch_related(
            Prefetch(
                "subscriptions",
                queryset=OrganizationSubscription.objects.select_related(
                    "plan"
                ).order_by("-created_at"),
                to_attr="latest_subscriptions",
            )
        )

        data = []

        for organization in organizations:
            subscription = (
                organization.latest_subscriptions[0]
                if organization.latest_subscriptions
                else None
            )

            data.append({
                "id": str(organization.id),
                "name": organization.name,
                "email": organization.email,
                "phone": organization.phone,
                "website": organization.website,
                "logo": organization.logo,
                "status": organization.status,

                "subscription_id": (
                    str(subscription.id)
                    if subscription else None
                ),

                "subscription_status": (
                    subscription.status
                    if subscription else None
                ),

                "plan_name": (
                    subscription.plan.name
                    if subscription else None
                ),
            })

        return data

    def get(self, request):

        organizations = self.get_organizations()

        return CustomResponse().successResponse(
            data=organizations,
            description="Organizations fetched successfully."
        )

    def post(self, request):

        data = request.data

        organization_name = data.get("organization_name")
        email = data.get("email")
        phone = data.get("phone")
        website = data.get("website")
        logo = data.get("logo")
        plan_id = data.get("plan_id")

        if not organization_name:
            return CustomResponse().errorResponse(
                data={},
                description="Organization name is required."
            )

        if not email:
            return CustomResponse().errorResponse(
                data={},
                description="Email is required."
            )

        if not plan_id:
            return CustomResponse().errorResponse(
                data={},
                description="Plan is required."
            )

        organization = None
        subscription = None
        payment = None

        try:

            # Check whether organization name or email already exists
            organization_exists = Organization.objects.filter(
                name__iexact=organization_name
            ).exists()

            email_exists = Organization.objects.filter(
                email__iexact=email
            ).exists()

            if organization_exists or email_exists:

                organizations = self.get_organizations()

                return CustomResponse().successResponse(
                    data=organizations,
                    description="Organization already exists. Existing organizations fetched successfully."
                )

            plan = SubscriptionPlan.objects.get(
                id=plan_id,
                is_active=True,
            )

            print(
                "========== CREATING RAZORPAY SUBSCRIPTION =========="
            )

            razorpay_response = create_razorpay_subscription(
                plan_id=plan.razorpay_plan_id,
            )

            print(
                "========== RAZORPAY RESPONSE =========="
            )
            print(razorpay_response)

            razorpay_subscription_id = razorpay_response["id"]

            with transaction.atomic():

                organization = Organization.objects.create(
                    name=organization_name,
                    email=email,
                    phone=phone,
                    website=website,
                    logo=logo,
                )

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

            print(
                "Organization Created :",
                organization.id
            )

            print(
                "Subscription Created :",
                subscription.id
            )

            print(
                "Payment Created :",
                payment.id
            )

            return CustomResponse().successResponse(
                data={
                    "organization_id": str(organization.id),
                    "subscription_id": str(subscription.id),
                    "payment_id": str(payment.id),
                    "checkout_data": razorpay_response,
                },
                description="Subscription created successfully."
            )

        except SubscriptionPlan.DoesNotExist:

            return CustomResponse().errorResponse(
                data={},
                description="Subscription plan not found."
            )

        except Exception as exc:

            traceback.print_exc()

            print(
                "========== RAZORPAY ERROR =========="
            )
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

            if organization:
                organization.delete()

            return CustomResponse().errorResponse(
                data={},
                description=str(exc)
            )



class VerifySubscriptionPaymentAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        razorpay_payment_id = request.data.get("payment_id")
        razorpay_subscription_id = request.data.get("subscription_id")
        razorpay_signature = request.data.get("signature")

        if not razorpay_payment_id:
            return CustomResponse().errorResponse(
                data={},
                description="Razorpay payment id is required."
            )

        if not razorpay_subscription_id:
            return CustomResponse().errorResponse(
                data={},
                description="Razorpay subscription id is required."
            )

        if not razorpay_signature:
            return CustomResponse().errorResponse(
                data={},
                description="Razorpay signature is required."
            )

        try:

            client = get_razorpay_client()

            client.utility.verify_subscription_payment_signature(
                {
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_subscription_id": razorpay_subscription_id,
                    "razorpay_signature": razorpay_signature,
                }
            )

            subscription = OrganizationSubscription.objects.filter(
                merchant_subscription_id=razorpay_subscription_id
            ).first()

            if subscription is None:
                return CustomResponse().errorResponse(
                    data={},
                    description="Subscription not found."
                )

            payment = SubscriptionPayment.objects.filter(
                razorpay_subscription_id=razorpay_subscription_id
            ).first()

            if payment is None:
                return CustomResponse().errorResponse(
                    data={},
                    description="Payment not found."
                )

            payment.razorpay_payment_id = razorpay_payment_id
            payment.status = PaymentStatus.SUCCESS
            payment.payment_date = timezone.now()

            payment.save(
                update_fields=[
                    "razorpay_payment_id",
                    "status",
                    "payment_date",
                ]
            )

            subscription.status = SubscriptionStatus.ACTIVE
            subscription.starts_at = timezone.now()

            if subscription.plan.billing_cycle == BillingCycle.MONTHLY:
                subscription.next_billing_at = timezone.now() + relativedelta(months=1)
                subscription.expires_at = timezone.now() + relativedelta(months=1)
            else:
                subscription.next_billing_at = timezone.now() + relativedelta(years=1)
                subscription.expires_at = timezone.now() + relativedelta(years=1)

            subscription.save(
                update_fields=[
                    "status",
                    "starts_at",
                    "next_billing_at",
                    "expires_at",
                ]
            )

            return CustomResponse().successResponse(
                data={
                    "subscription_id": str(subscription.id),
                    "payment_id": str(payment.id),
                },
                description="Subscription verified successfully."
            )

        except SignatureVerificationError:

            return CustomResponse().errorResponse(
                data={},
                description="Invalid Razorpay signature."
            )

        except Exception as e:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description=str(e)
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

        client = get_razorpay_client()

        try:
            client.utility.verify_webhook_signature(
                body,
                signature,
                settings.RAZORPAY_WEBHOOK_SECRET,
            )

            print("Webhook Signature Verified")

        except Exception:
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

        subscription = None

        if subscription_entity:

            razorpay_subscription_id = subscription_entity.get("id")

            subscription = OrganizationSubscription.objects.filter(
                merchant_subscription_id=razorpay_subscription_id
            ).first()

            if not subscription:

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found"
                )

        # ---------------------------------------------------------
        # SUBSCRIPTION ACTIVATED
        # ---------------------------------------------------------

        if event == "subscription.activated":

            subscription.status = SubscriptionStatus.ACTIVE

            if subscription_entity.get("current_start"):
                subscription.starts_at = datetime.fromtimestamp(
                    subscription_entity["current_start"],
                    tz=timezone.get_current_timezone(),
                )

            if subscription_entity.get("current_end"):
                subscription.expires_at = datetime.fromtimestamp(
                    subscription_entity["current_end"],
                    tz=timezone.get_current_timezone(),
                )

            if subscription_entity.get("charge_at"):
                subscription.next_billing_at = datetime.fromtimestamp(
                    subscription_entity["charge_at"],
                    tz=timezone.get_current_timezone(),
                )

            subscription.save(
                update_fields=[
                    "status",
                    "starts_at",
                    "expires_at",
                    "next_billing_at",
                ]
            )

            payment = subscription.payments.order_by(
                "-created_at"
            ).first()

            if payment:

                payment.status = PaymentStatus.SUCCESS
                payment.payment_date = timezone.now()
                payment.response = payload

                payment.save(
                    update_fields=[
                        "status",
                        "payment_date",
                        "response",
                    ]
                )

            print("Subscription Activated")

        # ---------------------------------------------------------
        # SUBSCRIPTION AUTHENTICATED
        # ---------------------------------------------------------

        elif event == "subscription.authenticated":

            subscription.response = payload if hasattr(subscription, "response") else None

            print("Subscription Authenticated")

        # ---------------------------------------------------------
        # SUBSCRIPTION CANCELLED
        # ---------------------------------------------------------

        elif event == "subscription.cancelled":

            subscription.status = SubscriptionStatus.CANCELLED

            subscription.save(
                update_fields=[
                    "status",
                ]
            )

            print("Subscription Cancelled")

        # ---------------------------------------------------------
        # SUBSCRIPTION PAUSED
        # ---------------------------------------------------------

        elif event == "subscription.paused":

            subscription.status = SubscriptionStatus.PAUSED

            subscription.save(
                update_fields=[
                    "status",
                ]
            )

            print("Subscription Paused")

        # ---------------------------------------------------------
        # SUBSCRIPTION RESUMED
        # ---------------------------------------------------------

        elif event == "subscription.resumed":

            subscription.status = SubscriptionStatus.ACTIVE

            subscription.save(
                update_fields=[
                    "status",
                ]
            )

            print("Subscription Resumed")

        # ---------------------------------------------------------
        # SUBSCRIPTION COMPLETED
        # ---------------------------------------------------------

        elif event == "subscription.completed":

            subscription.status = SubscriptionStatus.EXPIRED

            subscription.save(
                update_fields=[
                    "status",
                ]
            )

            print("Subscription Completed")

        # ---------------------------------------------------------
        # PAYMENT CAPTURED
        # ---------------------------------------------------------

        elif event == "payment.captured":

            payment_id = payment_entity.get("id")

            payment = SubscriptionPayment.objects.filter(
                subscription=subscription
            ).order_by("-created_at").first()

            if payment:

                payment.phonepe_transaction_id = payment_id
                payment.status = PaymentStatus.SUCCESS
                payment.payment_date = timezone.now()
                payment.response = payload

                payment.save(
                    update_fields=[
                        "phonepe_transaction_id",
                        "status",
                        "payment_date",
                        "response",
                    ]
                )

            print("Payment Captured")

        # ---------------------------------------------------------
        # PAYMENT FAILED
        # ---------------------------------------------------------

        elif event == "payment.failed":

            payment = SubscriptionPayment.objects.filter(
                subscription=subscription
            ).order_by("-created_at").first()

            if payment:

                payment.status = PaymentStatus.FAILED
                payment.failure_reason = payment_entity.get(
                    "error_description"
                )
                payment.response = payload

                payment.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "response",
                    ]
                )

            print("Payment Failed")

        print("========== WEBHOOK SUCCESS ==========")

        return CustomResponse().successResponse(
            data={},
            description="Webhook processed successfully."
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
                    "max_verified_domains":plan.max_verified_domains,
                    "max_api_keys":plan.max_api_keys,
                    "analytics_level":plan.analytics_level,
                    ""
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
