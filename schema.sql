PRAGMA foreign_keys=OFF;

CREATE TABLE IF NOT EXISTS devices (
  box_id    TEXT PRIMARY KEY,
  token     TEXT NOT NULL,
  paired_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  msg_id        TEXT PRIMARY KEY,
  to_box        TEXT NOT NULL,
  from_source   TEXT NOT NULL,
  msg_type      TEXT NOT NULL,
  msg_text      TEXT,
  msg_event     TEXT,
  status        TEXT NOT NULL,
  created_at    INTEGER NOT NULL,
  delivered_at  INTEGER,
  seen_at       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_messages_to_status_time
ON messages (to_box, status, created_at);
