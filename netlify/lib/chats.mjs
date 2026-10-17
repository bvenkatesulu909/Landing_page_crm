// Shared by the chat function and the daily cleanup: the chat store and how long
// conversations are kept. A conversation is kept for RETENTION_DAYS from the time it
// started, then removed. Change the period with CHAT_RETENTION_DAYS, and update the
// matching privacy note in index.html.

import { getStore } from "@netlify/blobs";

export const RETENTION_DAYS = Math.min(365, Math.max(1, Number(process.env.CHAT_RETENTION_DAYS) || 90));

export const chatsStore = () => getStore({ name: "chats", consistency: "strong" });

// True when a saved conversation has passed its retention period, or has no usable start time.
export function isExpired(chat, now = Date.now()) {
    const started = Date.parse(chat?.created_at);
    return Number.isNaN(started) || now - started > RETENTION_DAYS * 86_400_000;
}
