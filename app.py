import os
import stripe
from flask import Flask, request, jsonify
import libsql_client

app = Flask(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

# Turso connection credentials using auraflowdb
TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "wss://auraflowdb-auraflow2026.aws-us-west-2.turso.io")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

def get_db_client():
    return libsql_client.create_client_sync(
        url=TURSO_URL,
        auth_token=TURSO_AUTH_TOKEN
    )

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
        
        customer_email = None
        if isinstance(session_data, dict):
            customer_email = session_data.get("customer_email") or session_data.get("customer_details", {}).get("email")
        else:
            customer_email = getattr(session_data, "customer_email", None)
            
        print(f"Payment successful for email: {customer_email}")

        # Database action with auraflowdb
        try:
            client = get_db_client()
            client.execute(
                "INSERT INTO users (email, status) VALUES (?, ?)",
                (customer_email, "active")
            )
            client.close()
            print("Successfully recorded user in auraflowdb!")
        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({"error": str(e)}), 400

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
