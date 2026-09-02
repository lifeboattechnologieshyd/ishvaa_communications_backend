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
                description="Plan is required."
            )

        subscription = None
        payment = None
        transaction_obj = None

        try:

            # Get organization from authenticated user
            organization = user.organization

            if not organization:
                return CustomResponse().errorResponse(
                    data={},
                    description="User is not linked to an organization."
                )

            try:
                plan = SubscriptionPlan.objects.get(
                    id=plan_id,
                    is_active=True,
                )

            except SubscriptionPlan.DoesNotExist:
                return CustomResponse().errorResponse(
                    data={},
                    description="Subscription plan not found."
                )

            # Check existing active subscription
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
                    )
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

                subscription = OrganizationSubscription.objects.create(
                    organization=organization,
                    plan=plan,
                    merchant_subscription_id=razorpay_subscription_id,
                    status=SubscriptionStatus.PENDING,
                )

                transaction_obj = Transaction.objects.create(
                    organization=organization,
                    subscription=subscription,
                    transaction_type=TransactionType.SUBSCRIPTION,
                    status=TransactionStatus.PENDING,
                    payment_gateway=PaymentGateway.RAZORPAY,
                    amount=plan.amount,
                    currency=plan.currency,
                    gateway_subscription_id=razorpay_subscription_id,
                    response=razorpay_response,
                )

                payment = SubscriptionPayment.objects.create(
                    subscription=subscription,
                    razorpay_subscription_id=razorpay_subscription_id,
                    amount=plan.amount,
                    status=PaymentStatus.INITIATED,
                    response=razorpay_response,
                )

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
                    "transaction_id": str(transaction_obj.id),
                },
                description=(
                    "Subscription payment initiated successfully."
                )
            )


        except Exception as exc:

            traceback.print_exc()

            if payment:
                payment.status = PaymentStatus.FAILED

                payment.failure_reason = str(exc)

                payment.save(

                    update_fields=[

                        "status",

                        "failure_reason",

                    ]

                )

            if transaction_obj:
                transaction_obj.status = TransactionStatus.FAILED

                transaction_obj.failure_reason = str(exc)

                transaction_obj.save(

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

        body = request.body.decode("utf-8")
        signature = request.headers.get("X-Razorpay-Signature")

        client = get_razorpay_client()

        # =========================================================
        # VERIFY WEBHOOK SIGNATURE
        # =========================================================

        if not signature:

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

        except Exception:

            traceback.print_exc()

            return CustomResponse().errorResponse(
                data={},
                description="Invalid webhook signature.",
            )

        # =========================================================
        # PARSE PAYLOAD
        # =========================================================

        try:

            payload = json.loads(body)

        except json.JSONDecodeError:

            return CustomResponse().errorResponse(
                data={},
                description="Invalid webhook payload.",
            )

        event = payload.get("event")

        if not isinstance(event, str):

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

        # =========================================================
        # FIND LOCAL SUBSCRIPTION
        # =========================================================

        subscription = None

        if razorpay_subscription_id:

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

        # =========================================================
        # SUBSCRIPTION EVENTS
        # =========================================================

        if event.startswith("subscription."):

            if not subscription:

                # Return success so Razorpay does not keep
                # retrying a webhook for an unknown subscription.

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found.",
                )

            # -----------------------------------------------------
            # SUBSCRIPTION ACTIVATED
            # -----------------------------------------------------

            if event == "subscription.activated":

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

                subscription.save(
                    update_fields=update_fields
                )

            # -----------------------------------------------------
            # SUBSCRIPTION AUTHENTICATED
            # -----------------------------------------------------

            elif event == "subscription.authenticated":

                # No database change required.
                pass

            # -----------------------------------------------------
            # SUBSCRIPTION CHARGED
            # -----------------------------------------------------

            elif event == "subscription.charged":

                if not razorpay_payment_id:

                    return CustomResponse().errorResponse(
                        data={},
                        description="Payment ID missing.",
                    )

                # -------------------------------------------------
                # Idempotency
                # -------------------------------------------------

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

                    return CustomResponse().successResponse(
                        data={},
                        description="Payment already processed.",
                    )

                # -------------------------------------------------
                # Razorpay amount is in paise.
                # -------------------------------------------------

                razorpay_amount = (
                    payment_entity.get("amount")
                )

                if razorpay_amount is None:

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

                # -------------------------------------------------
                # Create NEW transaction for every charge.
                # -------------------------------------------------

                Transaction.objects.create(
                    organization=subscription.organization,
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

                # -------------------------------------------------
                # Update next billing date if available.
                # -------------------------------------------------

                charge_at = (
                    subscription_entity.get(
                        "charge_at"
                    )
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

            # -----------------------------------------------------
            # SUBSCRIPTION PENDING
            # -----------------------------------------------------

            elif event == "subscription.pending":

                subscription.status = (
                    SubscriptionStatus.PENDING
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            # -----------------------------------------------------
            # SUBSCRIPTION HALTED
            # -----------------------------------------------------

            elif event == "subscription.halted":

                subscription.status = (
                    SubscriptionStatus.HALTED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            # -----------------------------------------------------
            # SUBSCRIPTION PAUSED
            # -----------------------------------------------------

            elif event == "subscription.paused":

                subscription.status = (
                    SubscriptionStatus.PAUSED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            # -----------------------------------------------------
            # SUBSCRIPTION RESUMED
            # -----------------------------------------------------

            elif event == "subscription.resumed":

                subscription.status = (
                    SubscriptionStatus.ACTIVE
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            # -----------------------------------------------------
            # SUBSCRIPTION CANCELLED
            # -----------------------------------------------------

            elif event == "subscription.cancelled":

                subscription.status = (
                    SubscriptionStatus.CANCELLED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

            # -----------------------------------------------------
            # SUBSCRIPTION COMPLETED
            # -----------------------------------------------------

            elif event == "subscription.completed":

                subscription.status = (
                    SubscriptionStatus.EXPIRED
                )

                subscription.save(
                    update_fields=[
                        "status",
                    ]
                )

        # =========================================================
        # PAYMENT AUTHORIZED
        # =========================================================

        elif event == "payment.authorized":

            # Payment is authorized but not necessarily captured.
            #
            # Do NOT mark Transaction SUCCESS here.
            #
            # payment.captured / subscription.charged will handle
            # the successful payment.

            pass

        # =========================================================
        # PAYMENT CAPTURED
        # =========================================================

        elif event == "payment.captured":

            if not razorpay_payment_id:

                return CustomResponse().errorResponse(
                    data={},
                    description="Payment ID missing.",
                )

            if not subscription:

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found.",
                )

            # -----------------------------------------------------
            # Find transaction using exact payment ID.
            # -----------------------------------------------------

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

            # -----------------------------------------------------
            # If transaction already exists, update it.
            # -----------------------------------------------------

            if transaction_obj:

                if transaction_obj.status != (
                    TransactionStatus.SUCCESS
                ):

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

            else:

                # -------------------------------------------------
                # This can happen if payment.captured arrives
                # before our local transaction was created.
                #
                # Create the transaction instead of losing
                # the payment record.
                # -------------------------------------------------

                razorpay_amount = (
                    payment_entity.get("amount")
                )

                if razorpay_amount is None:

                    return CustomResponse().errorResponse(
                        data={},
                        description="Payment amount missing.",
                    )

                amount = (
                    Decimal(str(razorpay_amount))
                    / Decimal("100")
                )

                Transaction.objects.create(
                    organization=subscription.organization,
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
                    currency=(
                        payment_entity.get(
                            "currency"
                        )
                        or subscription.plan.currency
                    ),
                    gateway_payment_id=(
                        razorpay_payment_id
                    ),
                    gateway_subscription_id=(
                        razorpay_subscription_id
                    ),
                    payment_date=timezone.now(),
                    response=payload,
                )

        # =========================================================
        # PAYMENT FAILED
        # =========================================================

        elif event == "payment.failed":

            if not razorpay_payment_id:

                return CustomResponse().errorResponse(
                    data={},
                    description="Payment ID missing.",
                )

            if not subscription:

                return CustomResponse().successResponse(
                    data={},
                    description="Subscription not found.",
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

                transaction_obj.status = (
                    TransactionStatus.FAILED
                )

                transaction_obj.failure_reason = (
                    payment_entity.get(
                        "error_description"
                    )
                )

                transaction_obj.response = payload

                transaction_obj.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "response",
                    ]
                )

            else:

                # A failed payment can also arrive before
                # a local transaction exists.

                razorpay_amount = (
                    payment_entity.get("amount", 0)
                )

                amount = (
                    Decimal(str(razorpay_amount))
                    / Decimal("100")
                )

                Transaction.objects.create(
                    organization=subscription.organization,
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
                    currency=(
                        payment_entity.get(
                            "currency"
                        )
                        or subscription.plan.currency
                    ),
                    gateway_payment_id=(
                        razorpay_payment_id
                    ),
                    gateway_subscription_id=(
                        razorpay_subscription_id
                    ),
                    failure_reason=(
                        payment_entity.get(
                            "error_description"
                        )
                    ),
                    response=payload,
                )

        # =========================================================
        # UNKNOWN EVENT
        # =========================================================

        else:

            print(
                "Unhandled Razorpay webhook event:",
                event,
            )

        # =========================================================
        # SUCCESS
        # =========================================================

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
