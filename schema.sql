CREATE TABLE IF NOT EXISTS devices (
  box_id TEXT PRIMARY KEY,
  token TEXT NOT NULL,
  paired_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbox (
  box_id TEXT PRIMARY KEY,
  msg_id TEXT,
  msg_text TEXT,
  msg_type TEXT,          -- "text" or "event"
  msg_event TEXT,         -- e.g. "heartbeat", "rainbow"
  created_at INTEGER
);
