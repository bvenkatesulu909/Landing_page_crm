"""Generate dummy customers with payment details, and import them into the site.

The customers are fake: names are random combinations, emails use the reserved
example.com domain, and every record is marked "is_demo": true so it can be
filtered out or removed without touching real form submissions.

Usage:
    python scripts/demo_customers.py generate [--count 1000] [--out demo_customers.json]
    python scripts/demo_customers.py import   [--count 1000] [--url https://your-site.netlify.app]
    python scripts/demo_customers.py delete   [--url https://your-site.netlify.app]

import/delete read the admin token from the CUSTOMERS_ADMIN_TOKEN environment variable.
"""

import argparse
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_URL = "https://loquacious-dragon-b3a19b.netlify.app"
BATCH_SIZE = 250
SEED = 20261016

FIRST_NAMES = [
    "Aarav", "Aditi", "Akash", "Ananya", "Arjun", "Bhavya", "Chaitanya", "Deepika", "Divya", "Gaurav",
    "Harika", "Ishaan", "Kavya", "Kiran", "Lakshmi", "Madhu", "Manoj", "Meera", "Naveen", "Neha",
    "Pavan", "Pooja", "Pranav", "Priya", "Rahul", "Ramesh", "Ravi", "Sai", "Sandeep", "Sanjana",
    "Shreya", "Sneha", "Srinivas", "Suresh", "Swathi", "Teja", "Uday", "Varun", "Vijay", "Yamini",
]
LAST_NAMES = [
    "Reddy", "Rao", "Naidu", "Sharma", "Kumar", "Patel", "Iyer", "Nair", "Gupta", "Verma",
    "Chowdary", "Varma", "Menon", "Pillai", "Joshi", "Singh", "Shetty", "Goud", "Yadav", "Das",
]
CITIES = [
    ("Hyderabad", "Telangana", "500"), ("Bengaluru", "Karnataka", "560"), ("Chennai", "Tamil Nadu", "600"),
    ("Vijayawada", "Andhra Pradesh", "520"), ("Visakhapatnam", "Andhra Pradesh", "530"),
    ("Tirupati", "Andhra Pradesh", "517"), ("Anantapur", "Andhra Pradesh", "515"),
    ("Mumbai", "Maharashtra", "400"), ("Pune", "Maharashtra", "411"), ("Kochi", "Kerala", "682"),
    ("Mysuru", "Karnataka", "570"), ("Warangal", "Telangana", "506"),
]
STREETS = ["MG Road", "Gandhi Nagar", "Nehru Street", "Station Road", "Lake View Colony",
           "Temple Street", "Market Road", "Park Avenue", "Ambedkar Nagar", "Main Road"]
PLANS = [("Basic", 4999), ("Standard", 9999), ("Premium", 19999), ("Enterprise", 49999)]
METHODS = ["UPI", "UPI", "UPI", "Card", "Net banking", "Cash"]  # UPI is the most common
STATUS_WEIGHTS = [
    ("Payment completed", 40),
    ("Dues pending", 25),
    ("Contacted", 20),
    ("Processing transaction", 15),
]


def iso(dt):
    return dt.replace(microsecond=0).isoformat()


def make_customer(n, rng, now):
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    city, state, pin = rng.choice(CITIES)
    plan, price = rng.choice(PLANS)
    status = rng.choices([s for s, _ in STATUS_WEIGHTS], [w for _, w in STATUS_WEIGHTS])[0]
    created = now - timedelta(days=rng.uniform(0, 90), minutes=rng.randint(0, 1440))

    paid, due, due_date, txn = 0, 0, None, None
    txn_date = created + timedelta(days=rng.uniform(0, max(0.1, (now - created).days)))
    txn_id = f"TXN{created:%y%m%d}{n:05d}"

    if status == "Payment completed":
        paid = price
        txn = {"id": txn_id, "date": iso(txn_date), "amount": price,
               "method": rng.choice(METHODS), "status": "Success"}
    elif status == "Dues pending":
        paid = rng.choice([0, round(price * 0.25), round(price * 0.5), round(price * 0.75)])
        due = price - paid
        # About a third are already overdue.
        due_date = (created + timedelta(days=rng.choice([15, 30, 45, 60]))).date().isoformat()
        if paid:
            txn = {"id": txn_id, "date": iso(txn_date), "amount": paid,
                   "method": rng.choice(METHODS), "status": "Success"}
        elif rng.random() < 0.3:
            txn = {"id": txn_id, "date": iso(txn_date), "amount": price,
                   "method": rng.choice(METHODS), "status": "Failed"}
    elif status == "Processing transaction":
        paid = rng.choice([0, 0, round(price * 0.5)])
        due = price - paid
        due_date = (now + timedelta(days=rng.randint(1, 20))).date().isoformat()
        txn = {"id": txn_id, "date": iso(now - timedelta(hours=rng.randint(1, 48))), "amount": due,
               "method": rng.choice(["UPI", "Card", "Net banking"]), "status": "Processing"}
    # "Contacted": a lead that has been quoted a plan but not billed yet.

    return {
        "id": f"demo-{n:04d}",
        "name": f"{first} {last}",
        "phone": f"{rng.choice('6789')}{rng.randint(0, 999_999_999):09d}",
        "email": f"{first}.{last}{n}@example.com".lower(),
        "address": f"{rng.randint(1, 250)}, {rng.choice(STREETS)}, {city}, {state} {pin}{rng.randint(1, 99):03d}",
        "status": status,
        "plan": plan,
        "total_amount": price,
        "amount_paid": paid,
        "amount_due": due,
        "due_date": due_date,
        "last_transaction": txn,
        "is_demo": True,
        "created_at": iso(created),
    }


def generate(count):
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc)
    return [make_customer(n, rng, now) for n in range(1, count + 1)]


def request(method, url, token, payload=None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", "X-Admin-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} failed: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")


def require_token():
    token = os.environ.get("CUSTOMERS_ADMIN_TOKEN", "")
    if not token:
        sys.exit("Set CUSTOMERS_ADMIN_TOKEN to the site's admin token first.")
    return token


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["generate", "import", "delete"])
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--out", default="demo_customers.json")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    if args.action == "generate":
        customers = generate(args.count)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(customers, f, indent=1)
        print(f"Wrote {len(customers)} demo customers to {args.out}")

    elif args.action == "import":
        token = require_token()
        customers = generate(args.count)
        for i in range(0, len(customers), BATCH_SIZE):
            chunk = customers[i:i + BATCH_SIZE]
            batch = f"demo-{i // BATCH_SIZE + 1:02d}"
            result = request("POST", f"{base}/api/customers/import", token, {"batch": batch, "customers": chunk})
            print(f"Imported {result['imported']} customers as batch {result['batch']}")

    elif args.action == "delete":
        result = request("DELETE", f"{base}/api/customers/demo", require_token())
        print(f"Deleted {result['deleted_batches']} demo batches")


if __name__ == "__main__":
    main()
