

import razorpay
from django.conf import settings
import hmac
import hashlib

def get_razorpay_client():
    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


def create_plan(
    name,
    amount,
    period,
    interval,
):
    client = get_razorpay_client()

    plan = client.plan.create({
        "period": period,
        "interval": interval,
        "item": {
            "name": name,
            "amount": int(amount * 100),
            "currency": "INR",
        }
    })

    return plan


def create_subscription(
    plan_id,
    total_count=120,
):
    client = get_razorpay_client()

    subscription = client.subscription.create({
        "plan_id": plan_id,
        "total_count": total_count,
        "customer_notify": 1,
    })

    return subscription


def get_subscription(
    subscription_id,
):
    client = get_razorpay_client()

    return client.subscription.fetch(
        subscription_id
    )

def cancel_subscription(
    subscription_id,
    cancel_at_cycle_end=False,
):
    client = get_razorpay_client()

    return client.subscription.cancel(
        subscription_id,
        {
            "cancel_at_cycle_end": cancel_at_cycle_end
        }
    )

def pause_subscription(
    subscription_id,
):
    client = get_razorpay_client()

    return client.subscription.pause(
        subscription_id
    )


def resume_subscription(
    subscription_id,
):
    client = get_razorpay_client()

    return client.subscription.resume(
        subscription_id
    )

def fetch_invoice(
    invoice_id,
):
    client = get_razorpay_client()

    return client.invoice.fetch(
        invoice_id
    )


def fetch_payment(
    payment_id,
):
    client = get_razorpay_client()

    return client.payment.fetch(
        payment_id
    )




def verify_webhook_signature(
    request_body,
    signature,
):
    client = get_razorpay_client()

    client.utility.verify_webhook_signature(
        request_body,
        signature,
        settings.RAZORPAY_WEBHOOK_SECRET,
    )

    return True


def verify_payment_signature(
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
):
    client = get_razorpay_client()

    client.utility.verify_payment_signature({
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
    })

    return True


def create_order(
    amount,
    receipt,
):
    client = get_razorpay_client()

    return client.order.create({
        "amount": int(amount * 100),
        "currency": "INR",
        "receipt": receipt,
    })