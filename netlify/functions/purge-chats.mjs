// Netlify scheduled function: once a day, removes chat conversations past their retention period.
// Customer records are never touched; only the chats store is cleaned.

import { chatsStore, isExpired, RETENTION_DAYS } from "../lib/chats.mjs";

export default async () => {
    const store = chatsStore();
    const { blobs } = await store.list();

    let deleted = 0;
    for (const { key } of blobs) {
        const chat = await store.get(key, { type: "json" });
        if (isExpired(chat)) {
            await store.delete(key);
            deleted += 1;
        }
    }

    console.log(`purge-chats: removed ${deleted} of ${blobs.length} conversations older than ${RETENTION_DAYS} days`);
    return new Response(null, { status: 204 });
};

export const config = {
    schedule: "@daily",
};
