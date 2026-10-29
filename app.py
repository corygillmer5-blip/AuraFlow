import os
import secrets
import stripe
import libsql_client
from flask import Flask, request, jsonify

app = Flask(__name__)

# Load environment variables
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

def generate_license_key():
    """Generates a secure, readable license key format: AF-XXXX-XXXX-XXXX"""
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    part3 = secrets.token_hex(2).upper()
    return f"AF-{part1}-{part2}-{part3}"

def save_license_to_turso(license_key, email, max_activations):
    """Saves the generated license key to the Turso database."""
    if not TURSO_URL or not TURSO_TOKEN:
        print("Turso credentials missing. License not saved to DB.")
        return False
        
    try:
        client = libsql_client.create_client_sync(
            url=TURSO_URL, 
            auth_token=TURSO_TOKEN
        )
        
        # Ensure your table is named 'licenses' with columns: key, email, max_activations, status
        query = """
            INSERT INTO licenses (license_key, email, max_activations, status) 
            VALUES (?, ?, ?, 'active')
        """
        client.execute(query, [license_key, email, max_activations])
        client.close()
        return True
    except Exception as e:
        print(f"Error saving to Turso: {e}")
        return False

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
        amount_total = session.get("amount_total") # amount in cents
        
        # Map amount to your exact yearly tiers & activation limits
        max_activations = 1 # default fallback
        if amount_total == 29900:
            max_activations = 1   # Indie Tier ($299/yr)
        elif amount_total == 99900:
            max_activations = 5   # Professional Enterprise ($999/yr)
        elif amount_total == 250000:
            max_activations = 99  # Unlimited Enterprise ($2,500/yr)

        # 1. Generate unique license key
        new_key = generate_license_key()
        
        # 2. Save to Turso database
        save_license_to_turso(new_key, customer_email, max_activations)
        
        # (Optional TODO: Trigger email to customer with their new_key)

    return jsonify(success=True), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
