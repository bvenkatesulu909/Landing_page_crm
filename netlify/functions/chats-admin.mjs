// Netlify Function: read-only admin access to chat conversations.
//
//   GET /api/chats        Recent conversations, newest first (summaries only, no transcripts)
//   GET /api/chats/{id}   One conversation with its full transcript
//
// Both need the admin token (X-Admin-Token). Conversations past their retention period are
// not shown.

import { isAdmin } from "../lib/admin.mjs";
import { chatsStore, isExpired } from "../lib/chats.mjs";

const LIST_LIMIT = 200;
const ID_RE = /^[0-9a-f-]{8,40}$/i;

const json = (status, payload) =>
    new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });

function summarize(chat) {
    const transcript = Array.isArray(chat.transcript) ? chat.transcript : [];
    const firstUser = transcript.find((t) => t.from === "user");
    const last = transcript.at(-1);
    return {
        id: chat.id,
        started_at: chat.created_at,
        last_activity: last?.at || chat.updated_at || chat.created_at,
        turns: chat.user_turns || 0,
        preview: String(firstUser?.text || "").slice(0, 120),
        lead_id: chat.lead_id || null,
        callback_requested: chat.callback_requested === true,
        callback: chat.callback || null,
    };
}

export default async (req) => {
    if (!isAdmin(req)) return json(401, { error: "Unauthorized" });
    if (req.method !== "GET") return json(405, { error: "Method not allowed" });

    const store = chatsStore();
    const path = new URL(req.url).pathname.replace(/\/+$/, "");

    if (path === "/api/chats") {
        const { blobs } = await store.list();
        const chats = (await Promise.all(blobs.map(({ key }) => store.get(key, { type: "json" }))))
            .filter((chat) => chat && !isExpired(chat));
        chats.sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0));
        return json(200, {
            chats: chats.slice(0, LIST_LIMIT).map(summarize),
            total: chats.length,
            limit: LIST_LIMIT,
        });
    }

    const match = path.match(/^\/api\/chats\/([^/]+)$/);
    if (match && ID_RE.test(match[1])) {
        const chat = await store.get(match[1], { type: "json" });
        if (!chat || isExpired(chat)) return json(404, { error: "not_found" });
        return json(200, { chat: { ...summarize(chat), transcript: chat.transcript || [] } });
    }

    return json(404, { error: "not_found" });
};

export const config = {
    path: ["/api/chats", "/api/chats/*"],
};
