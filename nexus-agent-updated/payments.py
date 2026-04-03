import stripe
import os

def init_stripe():
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PLANS = {
    "pro": {
        "name": "Pro",
        "price": "$9.99/month",
        "price_id_env": "STRIPE_PRO_PRICE_ID",
        "features": ["200 agent runs/day", "All tools included", "Priority processing", "File storage 1GB", "Email support"],
        "color": "#00f5ff",
        "daily_limit": 200
    },
    "enterprise": {
        "name": "Enterprise",
        "price": "$29.99/month",
        "price_id_env": "STRIPE_ENTERPRISE_PRICE_ID",
        "features": ["Unlimited agent runs", "All tools + custom tools", "Fastest processing", "File storage 10GB", "24/7 Priority support", "API access"],
        "color": "#ff6b35",
        "daily_limit": 9999
    }
}

def create_checkout_session(plan_name: str, user_email: str, user_id: int, base_url: str):
    """Create a Stripe Checkout Session for subscription"""
    init_stripe()

    if plan_name not in PLANS:
        raise ValueError(f"Invalid plan: {plan_name}")

    plan = PLANS[plan_name]
    price_id = os.getenv(plan["price_id_env"])

    if not price_id or price_id.startswith("price_your"):
        raise ValueError(
            "Stripe price ID not configured. "
            "Go to stripe.com → Products → Create a product → Copy the Price ID → Add to .env"
        )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        customer_email=user_email,
        metadata={"user_id": str(user_id), "plan": plan_name},
        success_url=f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
        allow_promotion_codes=True,
    )
    return session

def handle_webhook(payload: bytes, sig_header: str):
    """Handle Stripe webhook events"""
    init_stripe()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise ValueError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid signature")

    return event

def cancel_subscription(subscription_id: str):
    """Cancel a user's subscription"""
    init_stripe()
    stripe.Subscription.delete(subscription_id)
