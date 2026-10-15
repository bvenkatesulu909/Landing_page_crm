// Netlify Function: the deployed version of the /api/customers endpoint in server.py.
// Stores customer details in Netlify Blobs (one blob per customer).
//
//   POST /api/customers   Save a customer (JSON: name, phone, email, address)
//   GET  /api/customers   List customers. Requires the ADMIN_TOKEN environment
//                         variable (set in Netlify) sent as the X-Admin-Token header.

import { getStore } from "@netlify/blobs";
import { randomUUID, timingSafeEqual } from "node:crypto";

const MAX_BODY_BYTES = 10_000;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_RE = /^[+\d\s()-]+$/;

const json = (status, payload) =>
    new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json; charset=utf-8" },
    });

// Mirrors validate() in server.py.
function validate(data) {
    if (!data || typeof data !== "object" || Array.isArray(data)) {
        return [null, { form: "Invalid request." }];
    }

    const clean = {};
    for (const key of ["name", "phone", "email", "address"]) {
        clean[key] = String(data[key] ?? "").trim();
    }
    const errors = {};

    if (clean.name.length < 2 || clean.name.length > 100) {
        errors.name = "Please enter your name.";
    }

    const digits = clean.phone.replace(/\D/g, "");
    if (!PHONE_RE.test(clean.phone) || digits.length < 10 || digits.length > 15) {
        errors.phone = "Please enter a valid phone number (10–15 digits).";
    }

    if (clean.email.length > 254 || !EMAIL_RE.test(clean.email)) {
        errors.email = "Please enter a valid email address.";
    }

    if (clean.address.length < 5 || clean.address.length > 500) {
        errors.address = "Please enter your address.";
    }

    return [clean, errors];
}

function isAdmin(req) {
    const expected = Buffer.from(process.env.ADMIN_TOKEN || "");
    const given = Buffer.from(req.headers.get("x-admin-token") || "");
    return expected.length > 0 && expected.length === given.length && timingSafeEqual(expected, given);
}

async function createCustomer(req, store) {
    const body = await req.text();
    if (!body || body.length > MAX_BODY_BYTES) {
        return json(400, { errors: { form: "Invalid request." } });
    }

    let data;
    try {
        data = JSON.parse(body);
    } catch {
        return json(400, { errors: { form: "Invalid request." } });
    }

    const [clean, errors] = validate(data);
    if (Object.keys(errors).length) {
        return json(400, { errors });
    }

    const createdAt = new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
    // Keys sort by creation time, so listing returns customers in order.
    const id = `${Date.now().toString(36).padStart(9, "0")}-${randomUUID().slice(0, 8)}`;
    const customer = { id, ...clean, created_at: createdAt };

    await store.setJSON(id, customer);
    return json(201, { id, customer, message: "Customer details saved." });
}

async function listCustomers(req, store) {
    if (!isAdmin(req)) {
        return json(401, { error: "Unauthorized" });
    }

    const { blobs } = await store.list();
    const customers = await Promise.all(blobs.map(({ key }) => store.get(key, { type: "json" })));
    customers.sort((a, b) => (a.id < b.id ? 1 : -1));
    return json(200, { customers: customers.filter(Boolean) });
}

export default async (req) => {
    const store = getStore({ name: "customers", consistency: "strong" });

    if (req.method === "POST") return createCustomer(req, store);
    if (req.method === "GET") return listCustomers(req, store);
    return json(405, { error: "Method not allowed" });
};

export const config = {
    path: "/api/customers",
};
