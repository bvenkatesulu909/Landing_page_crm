"""Backend for the landing page.

Serves index.html and stores customer details submitted through the
contact form in a local SQLite database (customers.db).

Run:  python server.py
Open: http://localhost:8000

Endpoints:
  POST /api/customers   Save a customer (JSON: name, phone, email, address)
  GET  /api/customers   List saved customers. Requires the ADMIN_TOKEN
                        environment variable to be set on the server and the
                        same value sent in the "X-Admin-Token" header.
"""

import hmac
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "customers.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
MAX_BODY_BYTES = 10_000

# Only these files are served; everything else (including the database) is not.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/landing-page.html": ("landing-page.html", "text/html; charset=utf-8"),
}

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^[+\d\s()-]+$")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                phone      TEXT NOT NULL,
                email      TEXT NOT NULL,
                address    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def validate(data):
    """Return (clean_data, errors). Mirrors the checks in index.html."""
    if not isinstance(data, dict):
        return None, {"form": "Invalid request."}

    clean = {k: str(data.get(k, "")).strip() for k in ("name", "phone", "email", "address")}
    errors = {}

    if not 2 <= len(clean["name"]) <= 100:
        errors["name"] = "Please enter your name."

    digits = re.sub(r"\D", "", clean["phone"])
    if not PHONE_RE.match(clean["phone"]) or not 10 <= len(digits) <= 15:
        errors["phone"] = "Please enter a valid phone number (10–15 digits)."

    if len(clean["email"]) > 254 or not EMAIL_RE.match(clean["email"]):
        errors["email"] = "Please enter a valid email address."

    if not 5 <= len(clean["address"]) <= 500:
        errors["address"] = "Please enter your address."

    return clean, errors


class Handler(BaseHTTPRequestHandler):
    server_version = "LandingPage/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/customers":
            return self.list_customers()

        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            body = (BASE_DIR / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/customers":
            return self.send_json(404, {"error": "Not found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            return self.send_json(400, {"errors": {"form": "Invalid request."}})

        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json(400, {"errors": {"form": "Invalid request."}})

        clean, errors = validate(data)
        if errors:
            return self.send_json(400, {"errors": errors})

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO customers (name, phone, email, address, created_at) VALUES (?, ?, ?, ?, ?)",
                (clean["name"], clean["phone"], clean["email"], clean["address"], created_at),
            )
        customer = {"id": cur.lastrowid, **clean, "created_at": created_at}
        self.send_json(201, {"id": cur.lastrowid, "customer": customer, "message": "Customer details saved."})

    def list_customers(self):
        token = self.headers.get("X-Admin-Token", "")
        if not ADMIN_TOKEN or not hmac.compare_digest(token, ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
        self.send_json(200, {"customers": [dict(r) for r in rows]})


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving on http://{HOST}:{PORT}  (database: {DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
