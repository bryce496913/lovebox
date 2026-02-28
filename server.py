import os
import sqlite3
import time
import secrets
from flask import Flask, request, jsonify, redirect, url_for, session, render_template_string

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
  </style>
</head>
<body>
  <h2>Send to a Love Box</h2>
  <p class="small">No history. Only the most recent pending message/event is stored (overwrites previous).</p>

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

      {% if status %}<div class="status">{{ status }}</div>{% endif %}
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

      // Insert at cursor position if possible
      const start = box.selectionStart ?? box.value.length;
      const end = box.selectionEnd ?? box.value.length;

      box.value = box.value.slice(0, start) + tag + box.value.slice(end);
      box.focus();

      // Move cursor after inserted tag
      const newPos = start + tag.length;
      box.setSelectionRange(newPos, newPos);

      // Reset dropdown
      select.value = "";
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
    return conn

def init_db():
    conn = db()
    schema_path = os.path.join(BASE_DIR, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    conn.execute(
        "INSERT OR REPLACE INTO devices (box_id, token, paired_to) VALUES (?, ?, ?)",
        (BOX1_ID, BOX1_TOKEN, BOX2_ID),
    )
    conn.execute(
        "INSERT OR REPLACE INTO devices (box_id, token, paired_to) VALUES (?, ?, ?)",
        (BOX2_ID, BOX2_TOKEN, BOX1_ID),
    )

    conn.execute("INSERT OR IGNORE INTO inbox (box_id) VALUES (?)", (BOX1_ID,))
    conn.execute("INSERT OR IGNORE INTO inbox (box_id) VALUES (?)", (BOX2_ID,))
    conn.commit()
    conn.close()

try:
    init_db()
except Exception as e:
    print("DB init failed:", repr(e))

# =========================
# Auth / Routing Rules
# =========================
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

def put_inbox(target_box_id: str, msg_type: str, msg_text: str = None, msg_event: str = None):
    conn = db()
    msg_id = secrets.token_hex(8)
    now = int(time.time())
    conn.execute(
        "UPDATE inbox SET msg_id=?, msg_type=?, msg_text=?, msg_event=?, created_at=? WHERE box_id=?",
        (msg_id, msg_type, msg_text, msg_event, now, target_box_id),
    )
    conn.commit()
    conn.close()
    return msg_id

# =========================
# Web UI (NO templates)
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
        return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status="Invalid target")

    if event:
        put_inbox(target, "event", msg_event=event)
        return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status=f"Sent event: {event} → {target}")

    if not text:
        return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status="Type a message first")

    put_inbox(target, "text", msg_text=text)
    return render_template_string(SEND_HTML, box1=BOX1_ID, box2=BOX2_ID, status=f"Sent message → {target}")

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

@app.get("/api/check")
def api_check():
    box_id = request.args.get("box_id", "")
    token = request.args.get("token", "")
    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    conn = db()
    row = conn.execute("SELECT * FROM inbox WHERE box_id=?", (box_id,)).fetchone()
    conn.close()

    if not row or not row["msg_id"]:
        return jsonify({"ok": True, "has": False})

    return jsonify({
        "ok": True,
        "has": True,
        "msg_id": row["msg_id"],
        "type": row["msg_type"],
        "text": row["msg_text"],
        "event": row["msg_event"],
        "created_at": row["created_at"],
    })

@app.post("/api/ack")
def api_ack():
    data = request.get_json(force=True, silent=True) or {}
    box_id = data.get("box_id", "")
    token = data.get("token", "")
    msg_id = data.get("msg_id", "")

    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    conn = db()
    row = conn.execute("SELECT msg_id FROM inbox WHERE box_id=?", (box_id,)).fetchone()
    if row and row["msg_id"] == msg_id:
        conn.execute(
            "UPDATE inbox SET msg_id=NULL, msg_type=NULL, msg_text=NULL, msg_event=NULL, created_at=NULL WHERE box_id=?",
            (box_id,),
        )
        conn.commit()
    conn.close()

    return jsonify({"ok": True})

@app.post("/api/send_event")
def api_send_event():
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
    put_inbox(target, "event", msg_event=event)
    return jsonify({"ok": True, "sent_to": target})

@app.get("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

