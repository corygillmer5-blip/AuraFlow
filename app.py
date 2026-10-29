import os
import json
import sqlite3
import hashlib
import hmac
import datetime
from flask import Flask, request, jsonify, render_template_string, send_file
import io
import csv

app = Flask(__name__)

# Load configuration file
CONFIG_FILE = "smtp_config.json"
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

config = load_config()

# Turso Cloud Database Configuration
TURSO_URL = config.get("turso_database_url")
TURSO_TOKEN = config.get("turso_auth_token")

# Initialize database connection (Turso cloud or local SQLite fallback)
def get_db():
    if TURSO_URL and TURSO_TOKEN:
        try:
            import libsql_client
            return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
        except Exception as e:
            print(f"Turso connection error, falling back to local SQLite: {e}")
    
    # Fallback to local SQLite if Turso isn't configured
    conn = sqlite3.connect("licenses.db")
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database tables
def init_db():
    db = get_db()
    if TURSO_URL and TURSO_TOKEN:
        db.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT UNIQUE,
                email TEXT,
                seats INTEGER,
                hardware_id TEXT,
                expires_at TEXT,
                status TEXT
            )
        """)
    else:
        with db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT UNIQUE,
                    email TEXT,
                    seats INTEGER,
                    hardware_id TEXT,
                    expires_at TEXT,
                    status TEXT
                )
            """)

init_db()

@app.route("/")
def index():
    return "Aura Flow Licensing Engine Active (Cloud Turso Mode)"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
