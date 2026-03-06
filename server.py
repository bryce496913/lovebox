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
COMMON_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0b0712;
    --panel:#120a1f;
    --panel2:#170c28;
    --border:#2b1843;
    --text:#ffffff;
    --muted:#bca9d6;
    --purple:#7c3aed;
    --pink:#ec4899;
    --ok:#22c55e;
    --warn:#f59e0b;
  }
  *{ box-sizing:border-box; }
  body{
    margin:0;
    font-family:'Poppins',system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
    background:radial-gradient(900px 600px at 20% 10%, #1a0e2e 0%, var(--bg) 55%, #07040d 100%);
    color:var(--text);
    padding:18px;
  }
  .wrap{ max-width:760px; margin:0 auto; }
  .title{ font-size:24px; font-weight:700; letter-spacing:.4px; margin:6px 0 4px; }
  .sub{ color:var(--muted); font-size:13px; margin:0 0 14px; }
  .grid{ display:grid; gap:14px; }
  @media(min-width:760px){ .grid{ grid-template-columns: 1fr 1fr; } }
  .card{
    background:linear-gradient(180deg, var(--panel) 0%, var(--panel2) 100%);
    border:1px solid var(--border);
    border-radius:16px;
    padding:16px;
    box-shadow: 0 10px 30px rgba(0,0,0,.35);
  }
  label{ display:block; font-size:12px; color:var(--muted); margin-top:10px; }
  input, textarea, select{
    width:100%;
    margin-top:8px;
    padding:12px 12px;
    border-radius:12px;
    border:1px solid var(--border);
    background:#0a0613;
    color:var(--text);
    outline:none;
    font-size:14px;
  }
  textarea{ min-height:108px; resize:vertical; }
  .btn{
    width:100%;
    margin-top:12px;
    padding:12px 14px;
    border-radius:12px;
    border:0;
    font-weight:700;
    color:white;
    cursor:pointer;
    background:linear-gradient(90deg, var(--purple), var(--pink));
    box-shadow: 0 10px 24px rgba(236,72,153,.18);
  }
  .btn:active{ transform: translateY(1px); }
  .row{ display:flex; gap:10px; align-items:center; }
  .row > * { flex: 1; }
  .btnSmall{
    flex:0 0 auto;
    padding:12px 12px;
    border-radius:12px;
    border:1px solid var(--border);
    background:#0a0613;
    color:var(--text);
    font-weight:700;
    cursor:pointer;
  }
  .pill{
    display:inline-block;
    padding:6px 10px;
    border-radius:999px;
    border:1px solid var(--border);
    background:#0a0613;
    font-size:12px;
    color:var(--muted);
  }
  .status{
    margin-top:12px;
    padding:12px;
    border-radius:14px;
    border:1px solid var(--border);
    background:#0a0613;
  }
  .k{ color:var(--muted); font-size:12px; }
  .v{ font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size:12px; }
  .err{ color:#ff4d6d; font-size:13px; margin-top:10px; }
  .divider{ height:1px; background:rgba(124,58,237,.35); margin:14px 0; }
  .events{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
  .evt{
    padding:12px 12px;
    border-radius:14px;
    border:1px solid var(--border);
    background:#0a0613;
    color:white;
    font-weight:700;
    cursor:pointer;
  }
  .evt.p{ border-color:rgba(124,58,237,.6); }
  .evt.k{ border-color:rgba(236,72,153,.6); }
  code{ color:#fff; }
</style>
"""

LOGIN_HTML = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Love Box Login</title>
  {COMMON_CSS}
</head>
<body>
  <div class="wrap">
    <div class="title">Love Box</div>
    <p class="sub">Enter password to send messages.</p>

    <div class="card">
      <form method="post" action="/login">
        <label>Password</label>
        <input type="password" name="password" placeholder="Password" required />
        <button class="btn" type="submit">Login</button>
      </form>
      {{% if error %}}<div class="err">{{{{ error }}}}</div>{{% endif %}}
      <div class="divider"></div>
      <div class="sub">Tip: bookmark <code>/send</code> after logging in.</div>
    </div>
  </div>
</body>
</html>
"""

SEND_HTML = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Send Love Box Message</title>
  {COMMON_CSS}
</head>
<body>
  <div class="wrap">
    <div class="title">Send to a Love Box</div>
    <p class="sub">Queue v2: up to 5 pending per box. Status: Sent → Delivered → Seen.</p>

    <div class="grid">
      <div class="card">
        <form method="post" action="/send">
          <label>Target box</label>
          <select name="target" required>
            <option value="{{{{ box1 }}}}">{{{{ box1 }}}}</option>
            <option value="{{{{ box2 }}}}">{{{{ box2 }}}}</option>
          </select>

          <label>Message</label>
          <textarea id="messageBox" name="text" placeholder="Type something sweet…"></textarea>

          <label>Emoji picker</label>
          <div class="row">
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
              <option value="[PARTY]">🎉 PARTY</option>
              <option value="[SMILE]">😀 SMILE</option>
              <option value="[SUSHI]">🍣 SUSHI</option>
              <option value="[UPSIDEDOWN]">🙃 UPSIDEDOWN</option>
              <option value="[WORM]">🪱 WORM</option>
              <option value="[MOON]">🌙 MOON</option>
              <option value="[SUN]">☀️ SUN</option>
              <option value="[RAINBOW]">🌈 RAINBOW</option>
            </select>
            <button class="btnSmall" type="button" onclick="insertEmoji()">Insert</button>
          </div>

          <button class="btn" type="submit">Send Message</button>
        </form>

        {{% if msg_id %}}
          <div class="status">
            <div><span class="k">Message ID:</span> <span class="v" id="msgId">{{{{ msg_id }}}}</span></div>
            <div style="margin-top:10px;">
              <span class="k">Status:</span>
              <span class="pill" id="statusPill">{{{{ status_text }}}}</span>
            </div>
            <div class="sub" style="margin-top:10px;">This updates automatically.</div>
          </div>
        {{% elif status_text %}}
          <div class="status"><span class="pill">{{{{ status_text }}}}</span></div>
        {{% endif %}}
      </div>

      <div class="card">
        <form method="post" action="/send">
          <label>Target box</label>
          <select name="target" required>
            <option value="{{{{ box1 }}}}">{{{{ box1 }}}}</option>
            <option value="{{{{ box2 }}}}">{{{{ box2 }}}}</option>
          </select>

          <input type="hidden" name="text" value="" />
          <label>Quick Events</label>

          <div class="events">
            <button class="evt p" name="event" value="heartbeat" type="submit">❤️ Heartbeat</button>
            <button class="evt k" name="event" value="rainbow"   type="submit">🌈 Rainbow</button>
            <button class="evt k" name="event" value="breathe"   type="submit">😌 Breathe</button>
            <button class="evt p" name="event" value="ping"      type="submit">✨ Ping</button>
          </div>
        </form>
      </div>
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
        if (data && data.ok) pill.textContent = (data.status || "").toUpperCase();
      } catch (e) {}
    }

    if (document.getElementById("msgId")) setInterval(pollStatus, 2000);
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
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
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
    conn.commit()
    conn.close()

def auth_box(box_id: str, token: str):
    conn = db()
    row = conn.execute("SELECT box_id, token, paired_to FROM devices WHERE box_id=?", (box_id,)).fetchone()
    conn.close()
    if (not row) or (row["token"] != token):
        return None
    return {"box_id": row["box_id"], "paired_to": row["paired_to"]}

def prune_queue(to_box: str):
    conn = db()
    total = conn.execute("SELECT COUNT(*) AS c FROM messages WHERE to_box=?", (to_box,)).fetchone()["c"]
    if total <= MAX_QUEUE:
        conn.close()
        return

    # delete oldest seen first
    while total > MAX_QUEUE:
        r = conn.execute(
            "SELECT msg_id FROM messages WHERE to_box=? AND status='seen' ORDER BY created_at ASC LIMIT 1",
            (to_box,),
        ).fetchone()
        if not r:
            break
        conn.execute("DELETE FROM messages WHERE msg_id=?", (r["msg_id"],))
        conn.commit()
        total = conn.execute("SELECT COUNT(*) AS c FROM messages WHERE to_box=?", (to_box,)).fetchone()["c"]

    # still too many -> delete oldest overall
    while total > MAX_QUEUE:
        r = conn.execute(
            "SELECT msg_id FROM messages WHERE to_box=? ORDER BY created_at ASC LIMIT 1",
            (to_box,),
        ).fetchone()
        if not r:
            break
        conn.execute("DELETE FROM messages WHERE msg_id=?", (r["msg_id"],))
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

try:
    init_db()
except Exception as e:
    print("DB init failed:", repr(e))

# =========================
# Web UI
# =========================
@app.get("/")
def root():
    return redirect(url_for("send_page")) if session.get("logged_in") else redirect(url_for("login_page"))

@app.get("/login")
def login_page():
    return render_template_string(LOGIN_HTML)

@app.post("/login")
def login_post():
    if (request.form.get("password") or "") == WEB_PASSWORD:
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
    text = (request.form.get("text") or "").strip()
    event = (request.form.get("event") or "").strip()

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
# API
# =========================
@app.post("/api/register")
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    info = auth_box(data.get("box_id", ""), data.get("token", ""))
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401
    return jsonify({"ok": True, "paired_to": info["paired_to"]})

@app.get("/api/pending_count")
def api_pending_count():
    box_id = request.args.get("box_id", "")
    token = request.args.get("token", "")
    if not auth_box(box_id, token):
        return jsonify({"ok": False, "error": "auth_failed"}), 401
    conn = db()
    c = conn.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE to_box=? AND status IN ('sent','delivered')",
        (box_id,),
    ).fetchone()["c"]
    conn.close()
    return jsonify({"ok": True, "count": c})

@app.get("/api/check")
def api_check():
    box_id = request.args.get("box_id", "")
    token = request.args.get("token", "")
    if not auth_box(box_id, token):
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
        conn.execute("UPDATE messages SET status='delivered', delivered_at=? WHERE msg_id=?",
                     (now, row["msg_id"]))
        conn.commit()

    row2 = conn.execute("SELECT * FROM messages WHERE msg_id=?", (row["msg_id"],)).fetchone()
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
    data = request.get_json(force=True, silent=True) or {}
    box_id = data.get("box_id", "")
    token = data.get("token", "")
    msg_id = data.get("msg_id", "")

    if not auth_box(box_id, token):
        return jsonify({"ok": False, "error": "auth_failed"}), 401

    conn = db()
    row = conn.execute("SELECT msg_id, to_box FROM messages WHERE msg_id=?", (msg_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": True})

    if row["to_box"] != box_id:
        conn.close()
        return jsonify({"ok": False, "error": "wrong_box"}), 403

    now = int(time.time())
    conn.execute("UPDATE messages SET status='seen', seen_at=? WHERE msg_id=?", (now, msg_id))
    conn.commit()
    conn.close()

    prune_queue(box_id)
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

    msg_id = create_message(info["paired_to"], "device", "event", msg_event=event)
    return jsonify({"ok": True, "sent_to": info["paired_to"], "msg_id": msg_id})

@app.get("/health")
def health():
    return jsonify({"ok": True})
