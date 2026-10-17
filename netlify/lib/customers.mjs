// Shared by the Netlify functions: the customer store, the contact-detail rules
// (mirroring validate() in server.py) and the customer ID format.

import { getStore } from "@netlify/blobs";
import { randomUUID } from "node:crypto";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_RE = /^[+\d\s()-]+$/;

export const customerStore = () => getStore({ name: "customers", consistency: "strong" });

export const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");

// Keys sort by creation time, so listing returns customers in order.
export const newCustomerId = () => `${Date.now().toString(36).padStart(9, "0")}-${randomUUID().slice(0, 8)}`;

// Returns [clean, errors]; errors is empty when the details are valid.
export function validate(data) {
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
