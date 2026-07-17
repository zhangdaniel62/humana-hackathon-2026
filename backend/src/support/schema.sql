PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS support_rooms (
    id TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_rep_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    source_session_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('waiting', 'active', 'completed')),
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    claimed_at INTEGER,
    completed_at INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS support_rooms_one_open_per_customer_idx
ON support_rooms(customer_id)
WHERE status IN ('waiting', 'active');

CREATE INDEX IF NOT EXISTS support_rooms_queue_idx
ON support_rooms(status, created_at);

CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL REFERENCES support_rooms(id) ON DELETE CASCADE,
    sender_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_message_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE(room_id, sender_user_id, client_message_id)
);

CREATE INDEX IF NOT EXISTS support_messages_room_idx
ON support_messages(room_id, id);
