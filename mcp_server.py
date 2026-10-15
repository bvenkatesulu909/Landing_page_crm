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

@mcp.tool()
def list_customers(limit: int = 20, offset: int = 0) -> dict:
    """List customers who submitted the landing page form, newest first.

    Args:
        limit: Number of customers to return (1-100).
        offset: Number of customers to skip, for paging.
    """
    customers = load_customers()
    start = max(0, int(offset))
    return {"total": len(customers), "customers": customers[start:start + clamp_limit(limit)]}


@mcp.tool()
def search_customers(query: str, limit: int = 20) -> dict:
    """Search customers by name, phone, email or address (case-insensitive, partial match).

    Args:
        query: Text to look for, e.g. "gmail.com", "Bengaluru" or part of a name.
        limit: Maximum number of results (1-100).
    """
    needle = query.strip().lower()
    if not needle:
        raise ValueError("query must not be empty")

    matches = [
        c for c in load_customers()
        if any(needle in str(c.get(field, "")).lower() for field in ("name", "phone", "email", "address"))
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
    """Summary of form submissions: total, last 24 hours, last 7 days and the latest submission time."""
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat(timespec="seconds")
    week_ago = (now - timedelta(days=7)).isoformat(timespec="seconds")
    times = [c["created_at"] for c in load_customers()]
    return {
        "source": API_URL or "local database",
        "total": len(times),
        "last_24_hours": sum(t >= day_ago for t in times),
        "last_7_days": sum(t >= week_ago for t in times),
        "latest_submission": max(times, default=None),
    }


if __name__ == "__main__":
    if not API_URL:
        init_db()
    mcp.run()
