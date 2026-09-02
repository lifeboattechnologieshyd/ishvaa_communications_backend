import traceback
import uuid
from decimal import Decimal
from django.conf import settings
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from phonepe.sdk.pg.common.http_client_modules import phonepe_response
from razorpay.errors import SignatureVerificationError
from django.db.models import OuterRef, Subquery, Prefetch, Q

from db.models import OrganizationSubscription, Organization, OrganizationStatus, Transaction, TransactionType, \
    TransactionStatus, PaymentGateway
from db.models.subscription import SubscriptionPayment, PaymentStatus, SubscriptionStatus, SubscriptionPlan, \
    BillingCycle
from shared.clients.phonepe import phone_pe_initiate, create_upi_intent_mandate, create_upi_collect_mandate, \
    validate_subscription_webhook
from shared.clients.razorpay import create_razorpay_subscription, get_razorpay_client
from shared.utils import CustomResponse
import json
import traceback

import razorpay

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

class SubscriptionPaymentAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        user = request.user
        plan_id = request.data.get("plan_id")

        if not plan_id:
            return CustomResponse().errorResponse(
                data={},
                description="Plan is required.",
            )

        try:

            organization = user.organization

            if not organization:
                return CustomResponse().errorResponse(
                    data={},
                    description=(
                        "User is not linked to an organization."
                    ),
                )

            try:

                plan = SubscriptionPlan.objects.get(
                    id=plan_id,
                    is_active=True,
                )

            except SubscriptionPlan.DoesNotExist:

                return CustomResponse().errorResponse(
                    data={},
                    description="Subscription plan not found.",
                )

            # -----------------------------------------------------
            # Check active subscription
            # -----------------------------------------------------

            existing_subscription = (
                OrganizationSubscription.objects
                .select_related("plan")
                .filter(
                    organization=organization,
                    status=SubscriptionStatus.ACTIVE,
                )
                .order_by("-created_at")
                .first()
            )

            if existing_subscription:

                return CustomResponse().errorResponse(
                    data={
                        "subscription_id": str(
                            existing_subscription.id
                        ),
                        "plan_name": (
                            existing_subscription.plan.name
                        ),
                        "subscription_status": (
                            existing_subscription.status
                        ),
                    },
                    description=(
                        "Organization already has "
                        "an active subscription."
                    ),
                )

            # -----------------------------------------------------
            # Create Razorpay subscription
            # -----------------------------------------------------

            print(
                "========== CREATING RAZORPAY SUBSCRIPTION =========="
            )

            razorpay_response = (
                create_razorpay_subscription(
                    plan_id=plan.razorpay_plan_id,
                )
            )

            print(
                "========== RAZORPAY RESPONSE =========="
            )
            print(razorpay_response)

            razorpay_subscription_id = (
                razorpay_response["id"]
            )

            # -----------------------------------------------------
            # Create local records
            # -----------------------------------------------------

            with transaction.atomic():

                subscription = (
                    OrganizationSubscription.objects.create(
                        organization=organization,
                        plan=plan,
                        merchant_subscription_id=(
                            razorpay_subscription_id
                        ),
                        status=SubscriptionStatus.PENDING,
                    )
                )

                transaction_obj = (
                    Transaction.objects.create(
                        organization=organization,
                        subscription=subscription,
                        transaction_type=(
                            TransactionType.SUBSCRIPTION
                        ),
                        status=(
                            TransactionStatus.PENDING
                        ),
                        payment_gateway=(
                            PaymentGateway.RAZORPAY
                        ),
                        amount=plan.amount,
                        currency=plan.currency,
                        gateway_subscription_id=(
                            razorpay_subscription_id
                        ),
                        response=razorpay_response,
                    )
                )

                payment = (
                    SubscriptionPayment.objects.create(
                        subscription=subscription,
                        razorpay_subscription_id=(
                            razorpay_subscription_id
                        ),
                        amount=plan.amount,
                        status=PaymentStatus.INITIATED,
                        response=razorpay_response,
                    )
                )

            # -----------------------------------------------------
            # Response
            # -----------------------------------------------------

            return CustomResponse().successResponse(
                data={
                    "organization_id": str(
                        organization.id
                    ),
                    "subscription_id": str(
                        subscription.id
                    ),
                    "payment_id": str(
                        payment.id
                    ),
                    "plan_id": str(
                        plan.id
                    ),
                    "plan_name": plan.name,
                    "checkout_data": razorpay_response,
                    "transaction_id": str(
                        transaction_obj.id
                    ),
                },
                description=(
                    "Subscription payment initiated successfully."
                ),
            )

        except Exception as exc:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description=str(exc),
            )



class VerifySubscriptionPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        razorpay_payment_id = request.data.get(
            "payment_id"
        )

        razorpay_subscription_id = request.data.get(
            "subscription_id"
        )

        razorpay_signature = request.data.get(
            "signature"
        )

        # ---------------------------------------------------------
        # VALIDATION
        # ---------------------------------------------------------

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

            # -----------------------------------------------------
            # GET USER ORGANIZATION
            # -----------------------------------------------------

            user = request.user
            organization = user.organization

            if not organization:
                return CustomResponse().errorResponse(
                    data={},
                    description=(
                        "User is not linked to an organization."
                    )
                )

            # -----------------------------------------------------
            # VERIFY RAZORPAY SIGNATURE
            # -----------------------------------------------------

            client = get_razorpay_client()

            client.utility.verify_subscription_payment_signature(
                {
                    "razorpay_payment_id": (
                        razorpay_payment_id
                    ),
                    "razorpay_subscription_id": (
                        razorpay_subscription_id
                    ),
                    "razorpay_signature": (
                        razorpay_signature
                    ),
                }
            )

            # -----------------------------------------------------
            # GET SUBSCRIPTION
            # -----------------------------------------------------

            subscription = (
                OrganizationSubscription.objects
                .select_related("plan")
                .filter(
                    organization=organization,
                    merchant_subscription_id=(
                        razorpay_subscription_id
                    ),
                )
                .first()
            )

            if subscription is None:
                return CustomResponse().errorResponse(
                    data={},
                    description="Subscription not found."
                )

            # -----------------------------------------------------
            # GET SUBSCRIPTION PAYMENT
            # -----------------------------------------------------

            payment = (
                SubscriptionPayment.objects
                .filter(
                    subscription=subscription,
                    razorpay_subscription_id=(
                        razorpay_subscription_id
                    ),
                )
                .order_by("-created_at")
                .first()
            )

            if payment is None:
                return CustomResponse().errorResponse(
                    data={},
                    description="Subscription payment not found."
                )

            # -----------------------------------------------------
            # GET TRANSACTION
            # -----------------------------------------------------

            transaction_obj = (
                Transaction.objects
                .filter(
                    organization=organization,
                    subscription=subscription,
                    transaction_type=(
                        TransactionType.SUBSCRIPTION
                    ),
                    gateway_subscription_id=(
                        razorpay_subscription_id
                    ),
                )
                .order_by("-created_at")
                .first()
            )

            if transaction_obj is None:
                return CustomResponse().errorResponse(
                    data={},
                    description="Transaction not found."
                )

            # -----------------------------------------------------
            # IDEMPOTENCY CHECK
            # -----------------------------------------------------

            if (
                transaction_obj.status
                == TransactionStatus.SUCCESS
            ):

                return CustomResponse().successResponse(
                    data={
                        "organization_id": str(
                            organization.id
                        ),
                        "subscription_id": str(
                            subscription.id
                        ),
                        "subscription_payment_id": str(
                            payment.id
                        ),
                        "transaction_id": str(
                            transaction_obj.id
                        ),
                        "razorpay_payment_id": (
                            transaction_obj.gateway_payment_id
                        ),
                        "plan_name": (
                            subscription.plan.name
                        ),
                        "subscription_status": (
                            subscription.status
                        ),
                    },
                    description=(
                        "Subscription payment "
                        "already verified."
                    )
                )

            # -----------------------------------------------------
            # UPDATE PAYMENT + TRANSACTION + SUBSCRIPTION
            # -----------------------------------------------------

            now = timezone.now()

            with transaction.atomic():

                # -------------------------------------------------
                # SUBSCRIPTION PAYMENT
                # -------------------------------------------------

                payment.razorpay_payment_id = (
                    razorpay_payment_id
                )

                payment.status = PaymentStatus.SUCCESS

                payment.payment_date = now

                payment.save(
                    update_fields=[
                        "razorpay_payment_id",
                        "status",
                        "payment_date",
                    ]
                )

                # -------------------------------------------------
                # TRANSACTION
                # -------------------------------------------------

                transaction_obj.gateway_payment_id = (
                    razorpay_payment_id
                )

                transaction_obj.status = (
                    TransactionStatus.SUCCESS
                )

                transaction_obj.payment_date = now

                transaction_obj.save(
                    update_fields=[
                        "gateway_payment_id",
                        "status",
                        "payment_date",
                    ]
                )

                # -------------------------------------------------
                # SUBSCRIPTION
                # -------------------------------------------------

                subscription.status = (
                    SubscriptionStatus.ACTIVE
                )

                subscription.starts_at = now

                if (
                    subscription.plan.billing_cycle
                    == BillingCycle.MONTHLY
                ):

                    subscription.next_billing_at = (
                        now + relativedelta(months=1)
                    )

                    subscription.expires_at = (
                        now + relativedelta(months=1)
                    )

                else:

                    subscription.next_billing_at = (
                        now + relativedelta(years=1)
                    )

                    subscription.expires_at = (
                        now + relativedelta(years=1)
                    )

                subscription.save(
                    update_fields=[
                        "status",
                        "starts_at",
                        "next_billing_at",
                        "expires_at",
                    ]
                )

            # -----------------------------------------------------
            # RESPONSE
            # -----------------------------------------------------

            return CustomResponse().successResponse(
                data={
                    "organization_id": str(
                        organization.id
                    ),
                    "subscription_id": str(
                        subscription.id
                    ),
                    "subscription_payment_id": str(
                        payment.id
                    ),
                    "transaction_id": str(
                        transaction_obj.id
                    ),
                    "razorpay_payment_id": (
                        razorpay_payment_id
                    ),
                    "plan_name": (
                        subscription.plan.name
                    ),
                    "subscription_status": (
                        subscription.status
                    ),
                },
                description=(
                    "Subscription verified successfully."
                )
            )

        # ---------------------------------------------------------
        # INVALID RAZORPAY SIGNATURE
        # ---------------------------------------------------------

        except SignatureVerificationError:

            return CustomResponse().errorResponse(
                data={},
                description="Invalid Razorpay signature."
            )

        # ---------------------------------------------------------
        # OTHER ERRORS
        # ---------------------------------------------------------

        except Exception as exc:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description=str(exc)
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

        print("\n" + "=" * 80)
        print("RAZORPAY WEBHOOK RECEIVED")
        print("=" * 80)

        body = request.body.decode("utf-8")
        signature = request.headers.get("X-Razorpay-Signature")

        print("Webhook body received:", bool(body))
        print("Webhook signature received:", bool(signature))

        client = get_razorpay_client()

        # =========================================================
        # VERIFY WEBHOOK SIGNATURE
        # =========================================================

        print("\n[1] VERIFYING WEBHOOK SIGNATURE")

        if not signature:

            print("[ERROR] Webhook signature is missing.")

            return CustomResponse().errorResponse(
                data={},
                description="Webhook signature missing.",
            )

        try:

            client.utility.verify_webhook_signature(
                body,
                signature,
                settings.RAZORPAY_WEBHOOK_SECRET,
            )

            print("[SUCCESS] Webhook signature verified.")

        except Exception as exc:

            print("[ERROR] Webhook signature verification failed.")
            print("Error:", str(exc))

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description="Invalid webhook signature.",
            )

        # =========================================================
        # PARSE PAYLOAD
        # =========================================================

        print("\n[2] PARSING WEBHOOK PAYLOAD")

        try:

            payload = json.loads(body)

            print("[SUCCESS] Webhook JSON parsed.")

        except json.JSONDecodeError as exc:

            print("[ERROR] Invalid JSON payload.")
            print("Error:", str(exc))

            return CustomResponse().errorResponse(
                data={},
                description="Invalid webhook payload.",
            )

        event = payload.get("event")

        print("Webhook event:", event)

        if not isinstance(event, str):

            print("[ERROR] Invalid webhook event.")

            return CustomResponse().errorResponse(
                data={},
                description="Invalid webhook event.",
            )

        payload_data = payload.get("payload", {})

        subscription_entity = (
            payload_data
            .get("subscription", {})
            .get("entity", {})
        )

        payment_entity = (
            payload_data
            .get("payment", {})
            .get("entity", {})
        )

        razorpay_subscription_id = (
            subscription_entity.get("id")
        )

        razorpay_payment_id = (
            payment_entity.get("id")
        )

        print("\nWebhook IDs:")
        print(
            "Razorpay Subscription ID:",
            razorpay_subscription_id,
        )
        print(
            "Razorpay Payment ID:",
            razorpay_payment_id,
        )

        # =========================================================
        # FIND LOCAL SUBSCRIPTION
        # =========================================================

        print("\n[3] FINDING LOCAL SUBSCRIPTION")

        subscription = None

        if razorpay_subscription_id:

            print(
                "Searching subscription:",
                razorpay_subscription_id,
            )

            subscription = (
                OrganizationSubscription.objects
                .select_related(
                    "organization",
                    "plan",
                )
                .filter(
                    merchant_subscription_id=(
                        razorpay_subscription_id
                    )
                )
                .first()
            )

        if subscription:

            print("[SUCCESS] Local subscription found.")
            print("Local Subscription ID:", subscription.id)
            print("Organization ID:", subscription.organization_id)
            print("Plan ID:", subscription.plan_id)
            print("Current Status:", subscription.status)

        else:

            print(
                "[WARNING] Local subscription NOT found."
            )

        # =========================================================
        # SUBSCRIPTION EVENTS
        # =========================================================

        if event.startswith("subscription."):

            print("\n" + "-" * 80)
            print("SUBSCRIPTION EVENT")
            print("Event:", event)
            print("-" * 80)

            if not subscription:

                print(
                    "[WARNING] Subscription event received "
                    "but local subscription does not exist."
                )

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found.",
                )

            # -----------------------------------------------------
            # SUBSCRIPTION ACTIVATED
            # -----------------------------------------------------

            if event == "subscription.activated":

                print("\n[EVENT] subscription.activated")

                print(
                    "Previous subscription status:",
                    subscription.status,
                )

                update_fields = [
                    "status",
                ]

                subscription.status = (
                    SubscriptionStatus.ACTIVE
                )

                current_start = (
                    subscription_entity.get(
                        "current_start"
                    )
                )

                current_end = (
                    subscription_entity.get(
                        "current_end"
                    )
                )

                charge_at = (
                    subscription_entity.get(
                        "charge_at"
                    )
                )

                print("current_start:", current_start)
                print("current_end:", current_end)
                print("charge_at:", charge_at)

                if current_start:

                    subscription.starts_at = (
                        datetime.fromtimestamp(
                            current_start,
                            tz=timezone.get_current_timezone(),
                        )
                    )

                    update_fields.append(
                        "starts_at"
                    )

                    print(
                        "starts_at:",
                        subscription.starts_at,
                    )

                if current_end:

                    subscription.expires_at = (
                        datetime.fromtimestamp(
                            current_end,
                            tz=timezone.get_current_timezone(),
                        )
                    )

                    update_fields.append(
                        "expires_at"
                    )

                    print(
                        "expires_at:",
                        subscription.expires_at,
                    )

                if charge_at:

                    subscription.next_billing_at = (
                        datetime.fromtimestamp(
                            charge_at,
                            tz=timezone.get_current_timezone(),
                        )
                    )

                    update_fields.append(
                        "next_billing_at"
                    )

                    print(
                        "next_billing_at:",
                        subscription.next_billing_at,
                    )

                subscription.save(
                    update_fields=update_fields
                )

                print(
                    "[SUCCESS] Subscription activated."
                )

            # -----------------------------------------------------
            # SUBSCRIPTION AUTHENTICATED
            # -----------------------------------------------------

            elif event == "subscription.authenticated":

                print(
                    "[EVENT] subscription.authenticated"
                )

                print(
                    "[INFO] No database update required."
                )

            # -----------------------------------------------------
            # SUBSCRIPTION CHARGED
            # -----------------------------------------------------

            elif event == "subscription.charged":

                print("\n[EVENT] subscription.charged")

                print(
                    "Payment ID:",
                    razorpay_payment_id,
                )

                if not razorpay_payment_id:

                    print(
                        "[ERROR] Payment ID missing."
                    )

                    return CustomResponse().errorResponse(
                        data={},
                        description="Payment ID missing.",
                    )

                # -------------------------------------------------
                # IDEMPOTENCY CHECK
                # -------------------------------------------------

                print(
                    "\nChecking existing transaction..."
                )

                existing_transaction = (
                    Transaction.objects
                    .filter(
                        gateway_payment_id=(
                            razorpay_payment_id
                        )
                    )
                    .first()
                )

                if existing_transaction:

                    print(
                        "[INFO] Transaction already exists."
                    )

                    print(
                        "Transaction ID:",
                        existing_transaction.id,
                    )

                    print(
                        "Transaction Status:",
                        existing_transaction.status,
                    )

                    return CustomResponse().successResponse(
                        data={},
                        description="Payment already processed.",
                    )

                print(
                    "[SUCCESS] No existing transaction found."
                )

                # -------------------------------------------------
                # PAYMENT AMOUNT
                # -------------------------------------------------

                razorpay_amount = (
                    payment_entity.get("amount")
                )

                print(
                    "Razorpay amount:",
                    razorpay_amount,
                )

                if razorpay_amount is None:

                    print(
                        "[ERROR] Payment amount missing."
                    )

                    return CustomResponse().errorResponse(
                        data={},
                        description="Payment amount missing.",
                    )

                amount = (
                    Decimal(str(razorpay_amount))
                    / Decimal("100")
                )

                currency = (
                    payment_entity.get("currency")
                    or subscription.plan.currency
                )

                print(
                    "Transaction amount:",
                    amount,
                )

                print(
                    "Transaction currency:",
                    currency,
                )

                gateway_order_id = payment_entity.get("order_id")
                gateway_invoice_id = payment_entity.get("invoice_id")

                print("Gateway Order ID:", gateway_order_id)
                print("Gateway Payment ID:", razorpay_payment_id)
                print("Gateway Subscription ID:", razorpay_subscription_id)
                print("Gateway Invoice ID:", gateway_invoice_id)

                # -------------------------------------------------
                # CREATE TRANSACTION
                # -------------------------------------------------

                print(
                    "\nCreating new transaction..."
                )

                transaction_obj = (
                    Transaction.objects.create(
                        organization=(
                            subscription.organization
                        ),
                        subscription=subscription,
                        transaction_type=(
                            TransactionType.SUBSCRIPTION
                        ),
                        status=(
                            TransactionStatus.SUCCESS
                        ),
                        payment_gateway=(
                            PaymentGateway.RAZORPAY
                        ),
                        amount=amount,
                        currency=currency,
                        gateway_payment_id=(
                            razorpay_payment_id
                        ),
                        gateway_subscription_id=(
                            razorpay_subscription_id
                        ),
                        gateway_order_id=gateway_order_id,
                        gateway_invoice_id=gateway_invoice_id,

                        payment_date=timezone.now(),
                        response=payload,
                    )
                )

                print(
                    "[SUCCESS] Transaction created."
                )

                print(
                    "Local Transaction ID:",
                    transaction_obj.id,
                )

                print(
                    "Gateway Payment ID:",
                    transaction_obj.gateway_payment_id,
                )

                print(
                    "Transaction Status:",
                    transaction_obj.status,
                )

                # -------------------------------------------------
                # UPDATE NEXT BILLING DATE
                # -------------------------------------------------

                charge_at = (
                    subscription_entity.get(
                        "charge_at"
                    )
                )

                print(
                    "Next charge timestamp:",
                    charge_at,
                )

                if charge_at:

                    subscription.next_billing_at = (
                        datetime.fromtimestamp(
                            charge_at,
                            tz=timezone.get_current_timezone(),
                        )
                    )

                    subscription.save(
                        update_fields=[
                            "next_billing_at",
                        ]
                    )

                    print(
                        "[SUCCESS] Next billing date updated:",
                        subscription.next_billing_at,
                    )

            # -----------------------------------------------------
            # SUBSCRIPTION PENDING
            # -----------------------------------------------------

            elif event == "subscription.pending":

                print(
                    "\n[EVENT] subscription.pending"
                )

                print(
                    "Previous status:",
                    subscription.status,
                )

                subscription.status = (
                    SubscriptionStatus.PENDING
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                print(
                    "[SUCCESS] Subscription status → PENDING"
                )

            # -----------------------------------------------------
            # SUBSCRIPTION HALTED
            # -----------------------------------------------------

            elif event == "subscription.halted":

                print(
                    "\n[EVENT] subscription.halted"
                )

                print(
                    "Previous status:",
                    subscription.status,
                )

                subscription.status = (
                    SubscriptionStatus.HALTED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                print(
                    "[SUCCESS] Subscription status → HALTED"
                )

            # -----------------------------------------------------
            # SUBSCRIPTION PAUSED
            # -----------------------------------------------------

            elif event == "subscription.paused":

                print(
                    "\n[EVENT] subscription.paused"
                )

                subscription.status = (
                    SubscriptionStatus.PAUSED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                print(
                    "[SUCCESS] Subscription status → PAUSED"
                )

            # -----------------------------------------------------
            # SUBSCRIPTION RESUMED
            # -----------------------------------------------------

            elif event == "subscription.resumed":

                print(
                    "\n[EVENT] subscription.resumed"
                )

                subscription.status = (
                    SubscriptionStatus.ACTIVE
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                print(
                    "[SUCCESS] Subscription status → ACTIVE"
                )

            # -----------------------------------------------------
            # SUBSCRIPTION CANCELLED
            # -----------------------------------------------------

            elif event == "subscription.cancelled":

                print(
                    "\n[EVENT] subscription.cancelled"
                )

                subscription.status = (
                    SubscriptionStatus.CANCELLED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                print(
                    "[SUCCESS] Subscription status → CANCELLED"
                )

            # -----------------------------------------------------
            # SUBSCRIPTION COMPLETED
            # -----------------------------------------------------

            elif event == "subscription.completed":

                print(
                    "\n[EVENT] subscription.completed"
                )

                subscription.status = (
                    SubscriptionStatus.EXPIRED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

                print(
                    "[SUCCESS] Subscription status → EXPIRED"
                )

        # =========================================================
        # PAYMENT AUTHORIZED
        # =========================================================

        elif event == "payment.authorized":

            print("\n" + "-" * 80)
            print("PAYMENT AUTHORIZED")
            print("-" * 80)

            print(
                "Payment ID:",
                razorpay_payment_id,
            )

            print(
                "Subscription ID:",
                razorpay_subscription_id,
            )

            print(
                "Amount:",
                payment_entity.get("amount"),
            )

            print(
                "Currency:",
                payment_entity.get("currency"),
            )

            print(
                "[INFO] Payment is authorized."
            )

            print(
                "[INFO] NOT marking transaction SUCCESS."
            )

        # =========================================================
        # PAYMENT CAPTURED
        # =========================================================

        elif event == "payment.captured":

            print("\n" + "-" * 80)
            print("PAYMENT CAPTURED")
            print("-" * 80)

            print(
                "Payment ID:",
                razorpay_payment_id,
            )

            print(
                "Subscription ID:",
                razorpay_subscription_id,
            )

            if not razorpay_payment_id:

                print(
                    "[ERROR] Payment ID missing."
                )

                return CustomResponse().errorResponse(
                    data={},
                    description="Payment ID missing.",
                )

            if not subscription:

                print(
                    "[WARNING] Local subscription not found."
                )

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found.",
                )

            # -----------------------------------------------------
            # FIND TRANSACTION
            # -----------------------------------------------------

            print(
                "Searching transaction by payment ID..."
            )

            transaction_obj = (
                Transaction.objects
                .filter(
                    organization=subscription.organization,
                    gateway_payment_id=(
                        razorpay_payment_id
                    ),
                )
                .first()
            )

            if transaction_obj:

                print(
                    "[SUCCESS] Transaction found:",
                    transaction_obj.id,
                )

                print(
                    "Current transaction status:",
                    transaction_obj.status,
                )

                if transaction_obj.status != (
                    TransactionStatus.SUCCESS
                ):

                    print(
                        "Updating transaction to SUCCESS..."
                    )

                    transaction_obj.status = (
                        TransactionStatus.SUCCESS
                    )

                    transaction_obj.payment_date = (
                        timezone.now()
                    )

                    transaction_obj.response = payload

                    transaction_obj.save(
                        update_fields=[
                            "status",
                            "payment_date",
                            "response",
                        ]
                    )

                    print(
                        "[SUCCESS] Transaction updated."
                    )

                else:

                    print(
                        "[INFO] Transaction already SUCCESS."
                    )

            else:

                print(
                    "[WARNING] Transaction not found."
                )

                razorpay_amount = (
                    payment_entity.get("amount")
                )

                if razorpay_amount is None:

                    print(
                        "[ERROR] Payment amount missing."
                    )

                    return CustomResponse().errorResponse(
                        data={},
                        description="Payment amount missing.",
                    )

                amount = (
                    Decimal(str(razorpay_amount))
                    / Decimal("100")
                )

                currency = (
                    payment_entity.get(
                        "currency"
                    )
                    or subscription.plan.currency
                )

                print(
                    "Creating transaction from captured payment..."
                )

                transaction_obj = (
                    Transaction.objects.create(
                        organization=(
                            subscription.organization
                        ),
                        subscription=subscription,
                        transaction_type=(
                            TransactionType.SUBSCRIPTION
                        ),
                        status=(
                            TransactionStatus.SUCCESS
                        ),
                        payment_gateway=(
                            PaymentGateway.RAZORPAY
                        ),
                        amount=amount,
                        currency=currency,
                        gateway_payment_id=(
                            razorpay_payment_id
                        ),
                        gateway_subscription_id=(
                            razorpay_subscription_id
                        ),
                        payment_date=timezone.now(),
                        response=payload,
                    )
                )

                print(
                    "[SUCCESS] Transaction created:",
                    transaction_obj.id,
                )

        # =========================================================
        # PAYMENT FAILED
        # =========================================================

        elif event == "payment.failed":

            print("\n" + "-" * 80)
            print("PAYMENT FAILED")
            print("-" * 80)

            print(
                "Payment ID:",
                razorpay_payment_id,
            )

            print(
                "Subscription ID:",
                razorpay_subscription_id,
            )

            failure_reason = (
                payment_entity.get(
                    "error_description"
                )
            )

            print(
                "Failure reason:",
                failure_reason,
            )

            if not razorpay_payment_id:

                print(
                    "[ERROR] Payment ID missing."
                )

                return CustomResponse().errorResponse(
                    data={},
                    description="Payment ID missing.",
                )

            if not subscription:

                print(
                    "[WARNING] Local subscription not found."
                )

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found.",
                )

            # -----------------------------------------------------
            # FIND TRANSACTION
            # -----------------------------------------------------

            print(
                "Searching transaction by payment ID..."
            )

            transaction_obj = (
                Transaction.objects
                .filter(
                    organization=subscription.organization,
                    gateway_payment_id=(
                        razorpay_payment_id
                    ),
                )
                .first()
            )

            if transaction_obj:

                print(
                    "[SUCCESS] Transaction found:",
                    transaction_obj.id,
                )

                transaction_obj.status = (
                    TransactionStatus.FAILED
                )

                transaction_obj.failure_reason = (
                    failure_reason
                )

                transaction_obj.response = payload

                transaction_obj.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "response",
                    ]
                )

                print(
                    "[SUCCESS] Transaction updated → FAILED"
                )

            else:

                print(
                    "[WARNING] Transaction not found."
                )

                razorpay_amount = (
                    payment_entity.get(
                        "amount",
                        0,
                    )
                )

                amount = (
                    Decimal(str(razorpay_amount))
                    / Decimal("100")
                )

                currency = (
                    payment_entity.get(
                        "currency"
                    )
                    or subscription.plan.currency
                )

                print(
                    "Creating failed transaction..."
                )

                transaction_obj = (
                    Transaction.objects.create(
                        organization=(
                            subscription.organization
                        ),
                        subscription=subscription,
                        transaction_type=(
                            TransactionType.SUBSCRIPTION
                        ),
                        status=(
                            TransactionStatus.FAILED
                        ),
                        payment_gateway=(
                            PaymentGateway.RAZORPAY
                        ),
                        amount=amount,
                        currency=currency,
                        gateway_payment_id=(
                            razorpay_payment_id
                        ),
                        gateway_subscription_id=(
                            razorpay_subscription_id
                        ),
                        failure_reason=(
                            failure_reason
                        ),
                        response=payload,
                    )
                )

                print(
                    "[SUCCESS] Failed transaction created:",
                    transaction_obj.id,
                )

        # =========================================================
        # UNKNOWN EVENT
        # =========================================================

        else:

            print("\n" + "-" * 80)
            print("UNHANDLED RAZORPAY EVENT")
            print("-" * 80)

            print(
                "Event:",
                event,
            )

        # =========================================================
        # COMPLETE
        # =========================================================

        print("\n" + "=" * 80)
        print("RAZORPAY WEBHOOK PROCESSED SUCCESSFULLY")
        print("Event:", event)
        print("Subscription:", razorpay_subscription_id)
        print("Payment:", razorpay_payment_id)
        print("=" * 80 + "\n")

        return CustomResponse().successResponse(
            data={},
            description="Webhook processed successfully.",
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
