-- Devices (same as before)
CREATE TABLE IF NOT EXISTS devices (
  box_id TEXT PRIMARY KEY,
  token TEXT NOT NULL,
  paired_to TEXT NOT NULL
);

-- Message queue with status lifecycle:
-- sent -> delivered -> seen
CREATE TABLE IF NOT EXISTS messages (
  msg_id TEXT PRIMARY KEY,
  to_box TEXT NOT NULL,
  from_source TEXT NOT NULL,   -- "web" or "device"
  msg_type TEXT NOT NULL,      -- "text" or "event"
  msg_text TEXT,
  msg_event TEXT,
  status TEXT NOT NULL,        -- "sent" | "delivered" | "seen"
  created_at INTEGER NOT NULL,
  delivered_at INTEGER,
  seen_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_messages_to_status_created
  ON messages(to_box, status, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_to_created
  ON messages(to_box, created_at);
