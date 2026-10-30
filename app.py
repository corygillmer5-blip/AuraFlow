import os
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)

stripe.api.key = os.environ.get("STRIPE_SECRET_KEY")
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
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        
        # Pull email directly using safe dictionary get if it's a dict, 
        # or fallback to attribute/data lookup
        customer_email = None
        if isinstance(session_data, dict):
            customer_email = session_data.get("customer_email") or session_data.get("customer_details", {}).get("email")
        else:
            customer_email = getattr(session_data, "customer_email", None)
            
        print(f"Payment successful for email: {customer_email}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
