"""MCP server for the landing page's customer data.

Gives MCP clients (Claude Code, Claude Desktop, ...) tools to read and add the
customer details collected by the landing page contact form.

It works against one of two backends:
  * Local (default): the SQLite database written by server.py.
  * Live site: set CUSTOMERS_API_URL (e.g. https://your-site.netlify.app) and
    ADMIN_TOKEN, and it uses the deployed /api/customers endpoint instead.

Run (stdio transport, started by the MCP client):
    .venv/Scripts/python.exe mcp_server.py      # Windows
    .venv/bin/python mcp_server.py              # macOS / Linux
"""

import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

from server import DB_PATH, init_db, validate

API_URL = os.environ.get("CUSTOMERS_API_URL", "").rstrip("/")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
MAX_LIMIT = 100

mcp = FastMCP("landing-page-customers")


# ---------- Storage: live site API or local SQLite ----------

def api_request(method, payload=None):
    req = urllib.request.Request(
        f"{API_URL}/api/customers",
        method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError("The live site rejected the admin token. Check ADMIN_TOKEN.") from None
        raise ValueError(f"Live site returned HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    except urllib.error.URLError as e:
        raise ValueError(f"Could not reach {API_URL}: {e.reason}") from None


def load_customers():
    """All customers, newest first."""
    if API_URL:
        return api_request("GET")["customers"]

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def save_customer(clean):
    if API_URL:
        return api_request("POST", clean)["customer"]

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, email, address, created_at) VALUES (?, ?, ?, ?, ?)",
            (clean["name"], clean["phone"], clean["email"], clean["address"], created_at),
        )
    return {"id": cur.lastrowid, **clean, "created_at": created_at}


def clamp_limit(limit):
    return max(1, min(int(limit), MAX_LIMIT))


# ---------- Tools ----------

NEW_LEAD = "New lead"
STATUSES = ("Payment completed", "Dues pending", "Processing transaction", "Contacted", NEW_LEAD)


def status_of(customer):
    """Website form sign-ups have no payment details yet; they count as new leads."""
    return customer.get("status") or NEW_LEAD


@mcp.tool()
def list_customers(limit: int = 20, offset: int = 0, status: str = "", source: str = "") -> dict:
    """List customers, newest first, optionally filtered by payment status and source.

    Args:
        limit: Number of customers to return (1-100).
        offset: Number of customers to skip, for paging.
        status: Only this status: "Payment completed", "Dues pending",
            "Processing transaction", "Contacted" or "New lead". Empty for all.
        source: "real" (website form), "demo" (generated test data) or empty for both.
    """
    if status and status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    if source not in ("", "real", "demo"):
        raise ValueError('source must be "real", "demo" or empty')

    customers = [
        c for c in load_customers()
        if (not status or status_of(c) == status)
        and (not source or bool(c.get("is_demo")) == (source == "demo"))
    ]
    start = max(0, int(offset))
    return {"total": len(customers), "customers": customers[start:start + clamp_limit(limit)]}


@mcp.tool()
def search_customers(query: str, limit: int = 20) -> dict:
    """Search customers by name, phone, email, address or transaction ID (case-insensitive, partial match).

    Args:
        query: Text to look for, e.g. "gmail.com", "Bengaluru", part of a name or "TXN2608".
        limit: Maximum number of results (1-100).
    """
    needle = query.strip().lower()
    if not needle:
        raise ValueError("query must not be empty")

    matches = [
        c for c in load_customers()
        if any(needle in str(value).lower() for value in (
            c.get("name", ""), c.get("phone", ""), c.get("email", ""), c.get("address", ""),
            (c.get("last_transaction") or {}).get("id", ""),
        ))
    ]
    matches = matches[:clamp_limit(limit)]
    return {"count": len(matches), "customers": matches}


@mcp.tool()
def get_customer(customer_id: str) -> dict:
    """Get one customer by their ID (as shown in list or search results).

    Args:
        customer_id: The customer's ID.
    """
    for customer in load_customers():
        if str(customer["id"]) == str(customer_id).strip():
            return customer
    raise ValueError(f"No customer with id {customer_id}")


@mcp.tool()
def add_customer(name: str, phone: str, email: str, address: str) -> dict:
    """Add a customer, applying the same validation as the landing page form.

    Args:
        name: Full name (2-100 characters).
        phone: Phone number with 10-15 digits; +, spaces, brackets and dashes allowed.
        email: Email address.
        address: Postal address (5-500 characters).
    """
    clean, errors = validate({"name": name, "phone": phone, "email": email, "address": address})
    if errors:
        raise ValueError("Invalid customer details: " + "; ".join(f"{k}: {v}" for k, v in errors.items()))
    return save_customer(clean)


@mcp.tool()
def customer_stats() -> dict:
    """Summary of customers and payments: totals, sign-ups over time, counts per status,
    money collected and outstanding (in INR), overdue dues and transactions in progress."""
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat(timespec="seconds")
    week_ago = (now - timedelta(days=7)).isoformat(timespec="seconds")
    today = now.date().isoformat()
    customers = load_customers()
    times = [c["created_at"] for c in customers]
    processing = [c for c in customers if status_of(c) == "Processing transaction"]
    return {
        "source": API_URL or "local database",
        "total": len(customers),
        "real": sum(not c.get("is_demo") for c in customers),
        "demo": sum(bool(c.get("is_demo")) for c in customers),
        "last_24_hours": sum(t >= day_ago for t in times),
        "last_7_days": sum(t >= week_ago for t in times),
        "latest_submission": max(times, default=None),
        "by_status": {s: sum(status_of(c) == s for c in customers) for s in STATUSES},
        "collected_inr": sum(c.get("amount_paid") or 0 for c in customers),
        "outstanding_inr": sum(c.get("amount_due") or 0 for c in customers),
        "overdue_customers": sum(
            (c.get("amount_due") or 0) > 0 and (c.get("due_date") or "9999") < today for c in customers
        ),
        "processing_inr": sum((c.get("last_transaction") or {}).get("amount") or 0 for c in processing),
    }


if __name__ == "__main__":
    if not API_URL:
        init_db()
    mcp.run()
