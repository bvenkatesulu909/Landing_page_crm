"""MCP server for the landing page's customer database.

Gives MCP clients (Claude Code, Claude Desktop, ...) tools to read and add the
customer details collected by the landing page contact form. It uses the same
SQLite database and validation rules as server.py, so anything submitted on
the website is visible here and vice versa.

Run (stdio transport, started by the MCP client):
    .venv/Scripts/python.exe mcp_server.py      # Windows
    .venv/bin/python mcp_server.py              # macOS / Linux
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

from server import DB_PATH, init_db, validate

MAX_LIMIT = 100

mcp = FastMCP("landing-page-customers")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def clamp_limit(limit):
    return max(1, min(int(limit), MAX_LIMIT))


@mcp.tool()
def list_customers(limit: int = 20, offset: int = 0) -> dict:
    """List customers who submitted the landing page form, newest first.

    Args:
        limit: Number of customers to return (1-100).
        offset: Number of customers to skip, for paging.
    """
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM customers ORDER BY id DESC LIMIT ? OFFSET ?",
            (clamp_limit(limit), max(0, int(offset))),
        ).fetchall()
    return {"total": total, "customers": [dict(r) for r in rows]}


@mcp.tool()
def search_customers(query: str, limit: int = 20) -> dict:
    """Search customers by name, phone, email or address (case-insensitive, partial match).

    Args:
        query: Text to look for, e.g. "gmail.com", "Bengaluru" or part of a name.
        limit: Maximum number of results (1-100).
    """
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")

    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM customers
            WHERE name LIKE :p ESCAPE '\\' OR phone LIKE :p ESCAPE '\\'
               OR email LIKE :p ESCAPE '\\' OR address LIKE :p ESCAPE '\\'
            ORDER BY id DESC LIMIT :limit
            """,
            {"p": pattern, "limit": clamp_limit(limit)},
        ).fetchall()
    return {"count": len(rows), "customers": [dict(r) for r in rows]}


@mcp.tool()
def get_customer(customer_id: int) -> dict:
    """Get one customer by their ID.

    Args:
        customer_id: The customer's numeric ID.
    """
    with connect() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        raise ValueError(f"No customer with id {customer_id}")
    return dict(row)


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

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, email, address, created_at) VALUES (?, ?, ?, ?, ?)",
            (clean["name"], clean["phone"], clean["email"], clean["address"], created_at),
        )
    return {"id": cur.lastrowid, **clean, "created_at": created_at}


@mcp.tool()
def customer_stats() -> dict:
    """Summary of form submissions: total, last 24 hours, last 7 days and the latest submission time."""
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat(timespec="seconds")
    week_ago = (now - timedelta(days=7)).isoformat(timespec="seconds")
    with connect() as conn:
        total, last_24h, last_7d, latest = conn.execute(
            """
            SELECT COUNT(*),
                   COALESCE(SUM(created_at >= ?), 0),
                   COALESCE(SUM(created_at >= ?), 0),
                   MAX(created_at)
            FROM customers
            """,
            (day_ago, week_ago),
        ).fetchone()
    return {"total": total, "last_24_hours": last_24h, "last_7_days": last_7d, "latest_submission": latest}


if __name__ == "__main__":
    init_db()
    mcp.run()
