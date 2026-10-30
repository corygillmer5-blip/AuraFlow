import os
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configure Stripe API key from environment variables
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

@app.route("/")
def home():
    return "Aura Flow Backend is Running!"

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return jsonify({"error": "Invalid signature"}), 400

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # Safely convert Stripe session object to a dictionary to extract details
        session_dict = session.to_dict()
        customer_email = session_dict.get("customer_email") or session_dict.get("customer_details", {}).get("email")
        
        print(f"Payment successful for email: {customer_email}")
        
        # Add your fulfillment or database logging logic here

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
