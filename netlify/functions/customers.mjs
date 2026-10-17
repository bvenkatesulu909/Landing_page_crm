// Netlify Function: the deployed version of the /api/customers endpoint in server.py.
// Stores customer details in Netlify Blobs.
//
//   POST   /api/customers          Save a customer from the website form (JSON: name, phone,
//                                  email, address). One blob per customer.
//   GET    /api/customers          List all customers (form + demo), newest first.
//   POST   /api/customers/import   Store a batch of demo customers with payment details
//                                  (JSON: { batch, customers: [...] }). One blob per batch.
//   DELETE /api/customers/demo     Remove every demo batch. Form customers are never touched.
//
// Everything except the first route requires the ADMIN_TOKEN environment variable
// (set in Netlify) sent as the X-Admin-Token header.

import { isAdmin } from "../lib/admin.mjs";
import { customerStore, newCustomerId, nowIso, validate } from "../lib/customers.mjs";

const MAX_BODY_BYTES = 10_000;
const MAX_IMPORT_BYTES = 2_000_000;
const MAX_IMPORT_CUSTOMERS = 500;
const BATCH_PREFIX = "batch/";
const BATCH_RE = /^[a-z0-9-]{1,40}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}/;

const STATUSES = new Set(["Contacted", "Processing transaction", "Payment completed", "Dues pending"]);
const METHODS = new Set(["UPI", "Card", "Net banking", "Cash"]);
const TXN_STATES = new Set(["Success", "Processing", "Failed"]);

const json = (status, payload) =>
    new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json; charset=utf-8" },
    });

const money = (value) => Number.isFinite(value) && value >= 0 && value <= 10_000_000;

// Validates one imported demo customer: contact fields plus payment details.
function validateDemo(data) {
    const [clean, errors] = validate(data);
    if (!clean) return [null, errors];

    const id = String(data.id ?? "");
    if (!/^demo-[a-z0-9-]{1,40}$/.test(id)) errors.id = "id must look like demo-0001";
    if (!STATUSES.has(data.status)) errors.status = "unknown status";
    if (!String(data.plan ?? "").trim() || String(data.plan).length > 50) errors.plan = "plan is required";
    if (!DATE_RE.test(String(data.created_at ?? ""))) errors.created_at = "created_at must be an ISO date";

    const total = Number(data.total_amount);
    const paid = Number(data.amount_paid);
    const due = Number(data.amount_due);
    if (![total, paid, due].every(money) || paid + due > total) errors.amounts = "invalid amounts";

    if (data.due_date != null && !DATE_RE.test(String(data.due_date))) errors.due_date = "invalid due_date";

    let txn = null;
    if (data.last_transaction != null) {
        const t = data.last_transaction;
        txn = {
            id: String(t.id ?? "").slice(0, 40),
            date: String(t.date ?? ""),
            amount: Number(t.amount),
            method: t.method,
            status: t.status,
        };
        if (!txn.id || !DATE_RE.test(txn.date) || !money(txn.amount) ||
            !METHODS.has(txn.method) || !TXN_STATES.has(txn.status)) {
            errors.last_transaction = "invalid last_transaction";
        }
    }

    return [{
        id,
        ...clean,
        status: data.status,
        plan: String(data.plan ?? "").trim(),
        total_amount: total,
        amount_paid: paid,
        amount_due: due,
        due_date: data.due_date ?? null,
        last_transaction: txn,
        is_demo: true,
        created_at: String(data.created_at ?? ""),
    }, errors];
}


async function readJson(req, limit) {
    const body = await req.text();
    if (!body || body.length > limit) return null;
    try {
        return JSON.parse(body);
    } catch {
        return null;
    }
}

async function createCustomer(req, store) {
    const data = await readJson(req, MAX_BODY_BYTES);
    if (data === null) {
        return json(400, { errors: { form: "Invalid request." } });
    }

    const [clean, errors] = validate(data);
    if (Object.keys(errors).length) {
        return json(400, { errors });
    }

    const id = newCustomerId();
    const customer = { id, ...clean, created_at: nowIso() };

    await store.setJSON(id, customer);
    return json(201, { id, customer, message: "Customer details saved." });
}

async function listCustomers(store) {
    const { blobs } = await store.list();
    const values = await Promise.all(blobs.map(({ key }) => store.get(key, { type: "json" })));

    const customers = [];
    blobs.forEach(({ key }, i) => {
        const value = values[i];
        if (!value) return;
        if (key.startsWith(BATCH_PREFIX)) customers.push(...value);
        else customers.push(value);
    });

    customers.sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0));
    return json(200, { customers });
}

async function importDemo(req, store) {
    const data = await readJson(req, MAX_IMPORT_BYTES);
    if (!data || !BATCH_RE.test(String(data.batch ?? "")) || !Array.isArray(data.customers) ||
        data.customers.length === 0 || data.customers.length > MAX_IMPORT_CUSTOMERS) {
        return json(400, { error: `Send { batch, customers } with 1-${MAX_IMPORT_CUSTOMERS} customers.` });
    }

    const clean = [];
    for (const [i, item] of data.customers.entries()) {
        const [customer, errors] = validateDemo(item);
        if (!customer || Object.keys(errors).length) {
            return json(400, { error: `Customer ${i} is invalid.`, errors });
        }
        clean.push(customer);
    }

    // Re-importing the same batch name replaces it, so the import is safe to repeat.
    await store.setJSON(BATCH_PREFIX + data.batch, clean);
    return json(201, { batch: data.batch, imported: clean.length });
}

async function deleteDemo(store) {
    const { blobs } = await store.list({ prefix: BATCH_PREFIX });
    await Promise.all(blobs.map(({ key }) => store.delete(key)));
    return json(200, { deleted_batches: blobs.length });
}

export default async (req) => {
    const store = customerStore();
    const path = new URL(req.url).pathname.replace(/\/+$/, "");

    if (path === "/api/customers" && req.method === "POST") return createCustomer(req, store);

    if (!isAdmin(req)) return json(401, { error: "Unauthorized" });

    if (path === "/api/customers" && req.method === "GET") return listCustomers(store);
    if (path === "/api/customers/import" && req.method === "POST") return importDemo(req, store);
    if (path === "/api/customers/demo" && req.method === "DELETE") return deleteDemo(store);
    return json(404, { error: "Not found" });
};

export const config = {
    path: ["/api/customers", "/api/customers/import", "/api/customers/demo"],
};
