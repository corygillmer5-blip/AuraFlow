import os
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)

# Load your Stripe secret key and webhook secret from environment variables
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

@app.route("/", methods=["GET"])
def home():
    return "Aura Flow Licensing Engine Active (Cloud Turso Mode)"

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError as e:
        return "Invalid signature", 400

    # Handle the checkout session completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        amount_total = session.get("amount_total") # amount in cents (e.g., 29900, 99900, 250000)
        
        max_activations = 1 # default fallback
        if amount_total == 29900:
            max_activations = 1   # Indie Tier ($299/yr)
        elif amount_total == 99900:
            max_activations = 5   # Professional Enterprise ($999/yr)
        elif amount_total == 250000:
            max_activations = 99  # Unlimited Enterprise ($2,500/yr)

        # TODO: Generate your secure license key here and save to Turso database

    return jsonify(success=True), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
