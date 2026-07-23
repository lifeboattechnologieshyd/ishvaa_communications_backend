import time

from django.conf import settings
from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo
from phonepe.sdk.pg.common.models.request.pg_payment_request import PgPaymentRequest
from phonepe.sdk.pg.common.models.request.refund_request import RefundRequest
from phonepe.sdk.pg.payments.v2.models.request.create_sdk_order_request import CreateSdkOrderRequest
from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest
from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
from phonepe.sdk.pg.subscription.v2.models.request.amount_type import AmountType
from phonepe.sdk.pg.subscription.v2.models.request.auth_workflow_type import AuthWorkflowType
from phonepe.sdk.pg.subscription.v2.models.request.frequency import Frequency

client_secret = settings.PHONE_PE_CLIENT_SECRETE
client_id = settings.PHONE_PE_CLIENT_ID
client_version = settings.PHONE_PE_CLIENT_VERSION
env = settings.PHONE_PE_ENV
should_publish_events = False

def get_phonepe_client():
    client = StandardCheckoutClient.get_instance(
        client_id=client_id,
        client_secret=client_secret,
        client_version=client_version,
        env=env,
        should_publish_events=should_publish_events,
    )
    return client

def phone_pe_initiate(order_id, amount):
    client = get_phonepe_client()

    meta_info = MetaInfo(udf1="subscription")

    sdk_order_request = CreateSdkOrderRequest.build_standard_checkout_request(
        merchant_order_id=str(order_id),
        amount=amount,
        meta_info=meta_info,
        disable_payment_retry=True,
    )

    return client.create_sdk_order(sdk_order_request=sdk_order_request)

from phonepe.sdk.pg.subscription.v2.subscription_client import SubscriptionClient


def get_subscription_client():
    return SubscriptionClient.get_instance(
        client_id=client_id,
        client_secret=client_secret,
        client_version=client_version,
        env=env,
    )
def create_upi_mandate(
    merchant_order_id,
    merchant_subscription_id,
    amount,
):
    client = get_subscription_client()

    setup_request = PgPaymentRequest.build_subscription_setup_upi_intent(
        merchant_order_id=merchant_order_id,
        merchant_subscription_id=merchant_subscription_id,
        amount=amount,
        device_os="ANDROID",
        merchant_callback_scheme="",
        target_app="PHONEPE",
        auth_workflow_type=AuthWorkflowType.TRANSACTION,
        subscription_expire_at=int(time.time() * 1000) + 86400000,
        amount_type=AmountType.FIXED,
        frequency=Frequency.ON_DEMAND,
        order_expire_at=int(time.time() * 1000) + 900000,
        max_amount=amount,
    )

    return client.setup(setup_request)
# upi intent for mobile app
def create_upi_intent_mandate(
    merchant_order_id,
    merchant_subscription_id,
    amount,
    device_os="ANDROID",
):
    client = get_subscription_client()

    setup_request = PgPaymentRequest.build_subscription_setup_upi_intent(
        merchant_order_id=merchant_order_id,
        merchant_subscription_id=merchant_subscription_id,
        amount=amount,
        device_os=device_os,
        merchant_callback_scheme="",
        target_app="PHONEPE",
        auth_workflow_type=AuthWorkflowType.TRANSACTION,
        subscription_expire_at=int(time.time() * 1000) + 1000000,
        amount_type=AmountType.FIXED,
        frequency=Frequency.ON_DEMAND,
        order_expire_at=int(time.time() * 1000) + 1000000,
        max_amount=amount,
    )

    return client.setup(setup_request)

# upi collect for web
def create_upi_collect_mandate(
    merchant_order_id,
    merchant_subscription_id,
    amount,
    vpa,
):
    print("merchant_order_id:", merchant_order_id)
    print("merchant_subscription_id:", merchant_subscription_id)
    client = get_subscription_client()

    setup_request = PgPaymentRequest.build_subscription_setup_upi_collect(
        merchant_order_id=merchant_order_id,
        merchant_subscription_id=merchant_subscription_id,
        amount=amount,
        auth_workflow_type=AuthWorkflowType.TRANSACTION,
        subscription_expire_at=int(time.time() * 1000) + 1000000,
        amount_type=AmountType.FIXED,
        frequency=Frequency.ON_DEMAND,
        order_expire_at=int(time.time() * 1000) + 1000000,
        max_amount=amount,
        vpa=vpa,
    )

    return client.setup(setup_request)


def validate_phonepe_webhook(auth_header, raw_body):
    client = get_subscription_client()

    callback_response = client.validate_callback(
        username=settings.PHONEPE_WEBHOOK_USERNAME,
        password=settings.PHONEPE_WEBHOOK_PASSWORD,
        callback_header_data=auth_header,
        callback_response_data=raw_body,
    )

    print("Callback Validation Response :", callback_response)

    return callback_response

def create_phonepe_subscription(subscription_id, amount):
    client = get_phonepe_client()

    # Build subscription request here
    create_subscription_response = client.create_subscription(
        merchant_subscription_id=str(subscription_id),
        amount=amount,
    )

    return create_subscription_response

def get_phonepe_subscription_status(subscription_id):
    client = get_phonepe_client()

    subscription_status = client.get_subscription_status(
        merchant_subscription_id=str(subscription_id)
    )

    return subscription_status

def cancel_phonepe_subscription(subscription_id):
    client = get_phonepe_client()

    cancel_response = client.cancel_subscription(
        merchant_subscription_id=str(subscription_id)
    )

    return cancel_response

def get_phonepe_payment_status(transaction_id):
    client = get_phonepe_client()

    payment_status = client.get_order_status(
        merchant_order_id=str(transaction_id)
    )

    return payment_status