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

def get_db_client():
    if not TURSO_URL or not TURSO_TOKEN:
        return None
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

def init_db():
    """Automatically ensures the licenses table exists in Turso on startup."""
    client = get_db_client()
    if client:
        try:
            client.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT UNIQUE NOT NULL,
                    email TEXT,
                    max_activations INTEGER NOT NULL,
                    locked_ip TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception as e:
            print(f"DB Init Error: {e}")
        finally:
            client.close()

# Initialize database table upon app startup
init_db()

@app.route("/", methods=["GET"])
def home():
    return "Aura Flow Licensing Engine Active (Auto-DB & IP-Lock Enabled)"

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return "Invalid payload or signature", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        amount_total = session.get("amount_total")
        
        max_activations = 1 
        if amount_total == 29900:
            max_activations = 1   # Indie Tier ($299/yr)
        elif amount_total == 99900:
            max_activations = 5   # Professional Enterprise ($999/yr)
        elif amount_total == 250000:
            max_activations = 99  # Unlimited Enterprise ($2,500/yr)

        new_key = generate_license_key()
        
        client = get_db_client()
        if client:
            try:
                query = """
                    INSERT INTO licenses (license_key, email, max_activations, status) 
                    VALUES (?, ?, ?, 'active')
                """
                client.execute(query, [new_key, customer_email, max_activations])
            finally:
                client.close()

    return jsonify(success=True), 200

@app.route("/activate", methods=["POST"])
def activate_license():
    data = request.get_json() or {}
    license_key = data.get("license_key")
    
    if not license_key:
        return jsonify({"error": "Missing license_key"}), 400

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    client = get_db_client()
    if not client:
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        result = client.execute("SELECT license_key, locked_ip, status, max_activations FROM licenses WHERE license_key = ?", [license_key])
        rows = result.rows
        
        if not rows:
            return jsonify({"error": "Invalid license key"}), 404
            
        row = rows[0]
        db_key, locked_ip, status, max_activations = row[0], row[1], row[2], row[3]

        if status != "active":
            return jsonify({"error": "License is inactive or revoked"}), 403

        if locked_ip is None:
            client.execute("UPDATE licenses SET locked_ip = ? WHERE license_key = ?", [client_ip, license_key])
            return jsonify({
                "status": "success",
                "message": "License successfully activated and bound to your IP address.",
                "max_activations": max_activations
            }), 200
        
        elif locked_ip == client_ip:
            return jsonify({
                "status": "success",
                "message": "License verified successfully.",
                "max_activations": max_activations
            }), 200
        else:
            return jsonify({
                "error": "Security violation: License is locked to a different IP address."
            }), 403

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        client.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
