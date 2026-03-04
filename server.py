import os
import sqlite3
import time
import secrets
from flask import Flask, request, jsonify, redirect, url_for, session, render_template_string, abort

# =========================
# CONFIG (from Environment)
# =========================
APP_SECRET   = os.environ.get("APP_SECRET",   "dev-secret-change-me")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "dev-password-change-me")

BOX1_ID    = os.environ.get("BOX1_ID",    "bryce_box")
BOX1_TOKEN = os.environ.get("BOX1_TOKEN", "dev_token_box1")
BOX2_ID    = os.environ.get("BOX2_ID",    "amanda_box")
BOX2_TOKEN = os.environ.get("BOX2_TOKEN", "dev_token_box2")

DB_PATH = os.environ.get("DB_PATH", "lovebox.db")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MAX_QUEUE = 5  # per box


# =========================
# INLINE HTML (NO TEMPLATES)
# =========================
LOGIN_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Love Box Login</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 520px; margin: 40px auto; padding: 0 16px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 18px; }
    input { width: 100%; padding: 12px; font-size: 16px; margin-top: 8px; }
    button { margin-top: 12px; padding: 12px 14px; font-size: 16px; border-radius: 10px; border: 0; background: #111; color: #fff; width: 100%; }
    .err { color: #b00020; margin-top: 10px; }
    .small { font-size: 13px; color:#666; margin-top: 10px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Love Box</h2>
    <p>Enter password to send messages.</p>
    <form method="post" action="/login">
      <input type="password" name="password" placeholder="Password" required />
      <button type="submit">Login</button>
    </form>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <div class="small">Tip: bookmark <code>/send</code> after logging in.</div>
  </div>
</body>
</html>
"""

SEND_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Send Love Box Message</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; }
    .row { display:flex; gap:16px; flex-wrap:wrap; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 18px; flex: 1; min-width: 300px; }
    textarea, select, input { width: 100%; padding: 12px; font-size: 16px; margin-top: 8px; }
    button { margin-top: 12px; padding: 12px 14px; font-size: 16px; border-radius: 10px; border: 0; background: #111; color: #fff; width: 100%; cursor:pointer; }
    .small { font-size: 13px; color:#666; }
    .status { margin-top: 14px; padding: 10px; background:#f6f6f6; border-radius: 10px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }
    .evt { background:#0b5; }
    .evt2 { background:#07a; }
    .inline { display:flex; gap:10px; align-items:center; }
    .inline select { flex: 1; }
    .inline button { width:auto; margin-top: 8px; }
    .pill { display:inline-block; padding: 4px 10px; border-radius: 999px; background:#111; color:#fff; font-size: 12px; }
  </style>
</head>
<body>
  <h2>Send to a Love Box</h2>
  <p class="small">Queue v2: up to 5 pending per box. Status: Sent → Delivered → Seen.</p>

  <div class="row">
    <div class="card">
      <form method="post" action="/send" id="msgForm">
        <label>Target box</label>
        <select name="target" required>
          <option value="{{ box1 }}">{{ box1 }}</option>
          <option value="{{ box2 }}">{{ box2 }}</option>
        </select>

        <label style="margin-top:12px; display:block;">Message</label>
        <textarea id="messageBox" name="text" rows="4" placeholder="Type something sweet…"></textarea>

        <label style="margin-top:12px; display:block;">Emoji picker</label>
        <div class="inline">
          <select id="emojiSelect">
            <option value="">Select an emoji…</option>
            <option value="[BEER]">🍺 BEER</option>
            <option value="[BREAD]">🍞 BREAD</option>
            <option value="[CRY]">😭 CRY</option>
            <option value="[GLIZZY]">🌭 GLIZZY</option>
            <option value="[HEART]">❤️ HEART</option>
            <option value="[JOY]">🥹 JOY</option>
            <option value="[KISS]">😘 KISS</option>
            <option value="[LOVE]">🥰 LOVE</option>
            <option value="[MAIL]">📫 MAIL</option>
            <option value="[PANDA]">🐼 PANDA</option>
            <option value="[SMILE]">😀 SMILE</option>
            <option value="[SUSHI]">🍣 SUSHI</option>
            <option value="[UPSIDEDOWN]">🙃 UPSIDEDOWN</option>
            <option value="[WORM]">🪱 WORM</option>
          </select>

          <button type="button" onclick="insertEmoji()">Insert</button>
        </div>

        <button type="submit">Send Message</button>
      </form>

      {% if msg_id %}
        <div class="status">
          <div><strong>Message ID:</strong> <code id="msgId">{{ msg_id }}</code></div>
          <div style="margin-top:8px;">
            <strong>Status:</strong>
            <span class="pill" id="statusPill">{{ status_text }}</span>
          </div>
          <div class="small" style="margin-top:8px;">This will update automatically.</div>
        </div>
      {% elif status_text %}
        <div class="status">{{ status_text }}</div>
      {% endif %}
    </div>

    <div class="card">
      <form method="post" action="/send">
        <label>Target box</label>
        <select name="target" required>
          <option value="{{ box1 }}">{{ box1 }}</option>
          <option value="{{ box2 }}">{{ box2 }}</option>
        </select>

        <input type="hidden" name="text" value="" />
        <label style="margin-top:12px; display:block;">Quick Events</label>

        <div class="grid">
          <button class="evt"  name="event" value="heartbeat" type="submit">❤️ Heartbeat</button>
          <button class="evt2" name="event" value="rainbow"   type="submit">🌈 Rainbow</button>
          <button class="evt2" name="event" value="breathe"   type="submit">😌 Breathe</button>
          <button class="evt"  name="event" value="ping"      type="submit">✨ Ping</button>
        </div>
      </form>
    </div>
  </div>

  <script>
    function insertEmoji() {
      const select = document.getElementById("emojiSelect");
      const tag = select.value;
      if (!tag) return;

      const box = document.getElementById("messageBox");
      const start = box.selectionStart ?? box.value.length;
      const end = box.selectionEnd ?? box.value.length;

      box.value = box.value.slice(0, start) + tag + box.value.slice(end);
      box.focus();

      const newPos = start + tag.length;
      box.setSelectionRange(newPos, newPos);
      select.value = "";
    }

    async function pollStatus() {
      const el = document.getElementById("msgId");
      const pill = document.getElementById("statusPill");
      if (!el || !pill) return;
      const msgId = el.textContent.trim();
      if (!msgId) return;

      try {
        const r = await fetch("/status?msg_id=" + encodeURIComponent(msgId));
        if (!r.ok) return;
        const data = await r.json();
        if (data && data.ok) {
          pill.textContent = data.status.toUpperCase();
        }
      } catch (e) {}
    }

    // poll every 2s if msg_id is present
    if (document.getElementById("msgId")) {
      setInterval(pollStatus, 2000);
    }
  </script>
</body>
</html>
"""


# =========================
# APP
# =========================
app = Flask(__name__)
app.secret_key = APP_SECRET


# =========================
# DB Helpers
# =========================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # small reliability improvement for SQLite
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = db()
    schema_path = os.path.join(BASE_DIR, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    # Upsert paired devices
    conn.execute(
        "INSERT OR REPLACE INTO devices (box_id, token, paired_to) VALUES (?, ?, ?)",
        (BOX1_ID, BOX1_TOKEN, BOX2_ID),
    )
    conn.execute(
        "INSERT OR REPLACE INTO devices (box_id, token, paired_to) VALUES (?, ?, ?)",
        (BOX2_ID, BOX2_TOKEN, BOX1_ID),
    )
    conn.commit()
    conn.close()


def auth_box(box_id: str, token: str):
    conn = db()
    row = conn.execute(
        "SELECT box_id, token, paired_to FROM devices WHERE box_id = ?",
        (box_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None
    if row["token"] != token:
        return None
    return {"box_id": row["box_id"], "paired_to": row["paired_to"]}


def prune_queue(to_box: str):
    """
    Keep total messages for to_box <= MAX_QUEUE.
    Delete oldest SEEN first, then oldest overall if needed.
    """
    conn = db()
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE to_box=?",
        (to_box,),
    ).fetchone()["c"]

    if total <= MAX_QUEUE:
        conn.close()
        return

    # delete oldest seen first
    while total > MAX_QUEUE:
        seen_row = conn.execute(
            "SELECT msg_id FROM messages WHERE to_box=? AND status='seen' ORDER BY created_at ASC LIMIT 1",
            (to_box,),
        ).fetchone()
        if seen_row:
            conn.execute("DELETE FROM messages WHERE msg_id=?", (seen_row["msg_id"],))
            conn.commit()
        else:
            break

        total = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE to_box=?",
            (to_box,),
        ).fetchone()["c"]

    # still too many? delete oldest overall
    while total > MAX_QUEUE:
        row = conn.execute(
            "SELECT msg_id FROM messages WHERE to_box=? ORDER BY created_at ASC LIMIT 1",
            (to_box,),
        ).fetchone()
        if not row:
            break
        conn.execute("DELETE FROM messages WHERE msg_id=?", (row["msg_id"],))
        conn.commit()
        total -= 1

    conn.close()


def create_message(to_box: str, from_source: str, msg_type: str, msg_text: str = None, msg_event: str = None):
    msg_id = secrets.token_hex(8)
    now = int(time.time())

    conn = db()
    conn.execute(
        """
        INSERT INTO messages (msg_id, to_box, from_source, msg_type, msg_text, msg_event, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'sent', ?)
        """,
        (msg_id, to_box, from_source, msg_type, msg_text, msg_event, now),
    )
    conn.commit()
    conn.close()

    prune_queue(to_box)
    return msg_id


# init DB at import
try:
    init_db()
except Exception as e:
    print("DB init failed:", repr(e))


# =========================
# Web UI (session protected)
# =========================
@app.get("/")
def root():
    if session.get("logged_in"):
        return redirect(url_for("send_page"))
    return redirect(url_for("login_page"))

@app.get("/login")
def login_page():
    return render_template_string(LOGIN_HTML)

@app.post("/login")
def login_post():
    pwd = request.form.get("password", "")
    if pwd == WEB_PASSWORD:
        session["logged_in"] = True
        return redirect(url_for("send_page"))
    return render_template_string(LOGIN_HTML, error="Wrong password")

@app.get("/send")
def send_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID)

@app.post("/send")
def send_post():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    target = request.form.get("target", "")
    text = (request.form.get("text", "") or "").strip()
    event = (request.form.get("event", "") or "").strip()

    if target not in (BOX1_ID, BOX2_ID):
        return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status_text="Invalid target")

    if event:
        if event not in ("heartbeat", "rainbow", "breathe", "ping"):
            return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status_text="Invalid event")
        msg_id = create_message(target, "web", "event", msg_event=event)
        return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, msg_id=msg_id, status_text="SENT")

    if not text:
        return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status_text="Type a message first")

    msg_id = create_message(target, "web", "text", msg_text=text)
    return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, msg_id=msg_id, status_text="SENT")

@app.get("/status")
def web_status():
    """Web-only status lookup (requires session)."""
    if not session.get("logged_in"):
        abort(401)

    msg_id = request.args.get("msg_id", "")
    if not msg_id:
        return jsonify({"ok": False, "error": "missing_msg_id"}), 400

    conn = db()
    row = conn.execute(
        "SELECT status, created_at, delivered_at, seen_at FROM messages WHERE msg_id=?",
        (msg_id,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({
        "ok": True,
        "status": row["status"],
        "created_at": row["created_at"],
        "delivered_at": row["delivered_at"],
        "seen_at": row["seen_at"],
    })


# =========================
# API for Love Boxes
# =========================
@app.post("/api/register")
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    box_id = data.get("box_id", "")
    token = data.get("token", "")
    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401
    return jsonify({"ok": True, "paired_to": info["paired_to"]})

@app.get("/api/pending_count")
def api_pending_count():
    """How many messages are waiting (sent/delivered but not seen)."""
    box_id = request.args.get("box_id", "")
    token = request.args.get("token", "")
    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    conn = db()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE to_box=? AND status IN ('sent','delivered')",
        (box_id,),
    ).fetchone()
    conn.close()
    return jsonify({"ok": True, "count": row["c"]})

@app.get("/api/check")
def api_check():
    """
    Returns the oldest pending message for box (status sent or delivered).
    - If status was sent, mark as delivered.
    - If already delivered, return again until seen (ACK).
    """
    box_id = request.args.get("box_id", "")
    token = request.args.get("token", "")
    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    conn = db()
    row = conn.execute(
        """
        SELECT * FROM messages
        WHERE to_box=? AND status IN ('sent','delivered')
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (box_id,),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": True, "has": False})

    now = int(time.time())
    if row["status"] == "sent":
        conn.execute(
            "UPDATE messages SET status='delivered', delivered_at=? WHERE msg_id=?",
            (now, row["msg_id"]),
        )
        conn.commit()

    # re-fetch current status
    row2 = conn.execute(
        "SELECT * FROM messages WHERE msg_id=?",
        (row["msg_id"],),
    ).fetchone()
    conn.close()

    return jsonify({
        "ok": True,
        "has": True,
        "msg_id": row2["msg_id"],
        "type": row2["msg_type"],
        "text": row2["msg_text"],
        "event": row2["msg_event"],
        "status": row2["status"],
        "created_at": row2["created_at"],
        "delivered_at": row2["delivered_at"],
        "seen_at": row2["seen_at"],
    })

@app.post("/api/ack")
def api_ack():
    """Mark a message as seen (final state)."""
    data = request.get_json(force=True, silent=True) or {}
    box_id = data.get("box_id", "")
    token = data.get("token", "")
    msg_id = data.get("msg_id", "")

    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    conn = db()
    row = conn.execute(
        "SELECT msg_id, to_box, status FROM messages WHERE msg_id=?",
        (msg_id,),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": True})  # idempotent

    if row["to_box"] != box_id:
        conn.close()
        return jsonify({"ok": False, "error": "wrong_box"}), 403

    now = int(time.time())
    conn.execute(
        "UPDATE messages SET status='seen', seen_at=? WHERE msg_id=?",
        (now, msg_id),
    )
    conn.commit()
    conn.close()

    prune_queue(box_id)
    return jsonify({"ok": True})

@app.post("/api/send_event")
def api_send_event():
    """
    Device sends an event to its paired box.
    POST JSON: { box_id, token, event }
    """
    data = request.get_json(force=True, silent=True) or {}
    box_id = data.get("box_id", "")
    token = data.get("token", "")
    event = (data.get("event", "") or "").strip()

    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    allowed = ("heartbeat", "rainbow", "breathe", "ping")
    if event not in allowed:
        return jsonify({"ok": False, "error": "bad_event", "allowed": list(allowed)}), 400

    target = info["paired_to"]
    msg_id = create_message(target, "device", "event", msg_event=event)
    return jsonify({"ok": True, "sent_to": target, "msg_id": msg_id})

@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
