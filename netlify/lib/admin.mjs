// Admin access check shared by the admin endpoints. The admin token is the ADMIN_TOKEN
// environment variable, sent by the admin page as the X-Admin-Token header.

import { timingSafeEqual } from "node:crypto";

export function isAdmin(req) {
    const expected = Buffer.from(process.env.ADMIN_TOKEN || "");
    const given = Buffer.from(req.headers.get("x-admin-token") || "");
    return expected.length > 0 && expected.length === given.length && timingSafeEqual(expected, given);
}
