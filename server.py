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

THEME_HEAD = """
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root{
      --bg: #07060a;          /* near-black */
      --panel: #0f0b16;       /* dark purple-black */
      --panel2: #120d1c;
      --text: #ffffff;
      --muted: rgba(255,255,255,.72);
      --muted2: rgba(255,255,255,.55);
      --border: rgba(255,255,255,.10);

      --purple: #7c3aed;      /* violet */
      --pink: #ff4fd8;        /* neon pink */
      --pink2:#ff2fbf;

      --ok: #22c55e;
      --bad: #ef4444;
      --warn:#fbbf24;

      --radius: 16px;
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --shadow2: 0 1px 0 rgba(255,255,255,.05) inset;

      --ring: 0 0 0 3px rgba(255,79,216,.25);
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: "Poppins", system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background:
        radial-gradient(900px 420px at 15% 0%, rgba(124,58,237,.22), transparent 55%),
        radial-gradient(900px 420px at 85% 0%, rgba(255,79,216,.18), transparent 55%),
        linear-gradient(180deg, #06050a, var(--bg));
      color: var(--text);
    }

    .wrap{
      max-width: 920px;
      margin: 0 auto;
      padding: 22px 14px 48px;
    }

    .brand{
      display:flex;
      align-items:center;
      gap:10px;
      margin: 8px 0 14px;
    }
    .logo{
      width: 38px; height: 38px;
      border-radius: 12px;
      background:
        linear-gradient(135deg, rgba(124,58,237,.95), rgba(255,79,216,.95));
      box-shadow: var(--shadow);
    }
    h1, h2{
      margin: 0;
      letter-spacing: -0.02em;
    }
    h1{ font-size: 20px; font-weight: 700; }
    h2{ font-size: 18px; font-weight: 700; }

    .sub{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }

    .grid{
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
      margin-top: 14px;
    }
    @media (min-width: 860px){
      .grid{ grid-template-columns: 1.25fr .75fr; gap: 16px; }
    }

    .card{
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow), var(--shadow2);
      padding: 16px;
    }

    label{
      display:block;
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      margin-top: 12px;
      margin-bottom: 6px;
      letter-spacing: .02em;
      text-transform: uppercase;
    }

    input, textarea, select{
      width: 100%;
      padding: 12px 12px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,.12);
      background: rgba(10,8,14,.75);
      color: var(--text);
      outline: none;
      font-size: 15px;
      box-shadow: 0 0 0 1px rgba(0,0,0,.2) inset;
    }
    textarea{ min-height: 120px; resize: vertical; }
    input::placeholder, textarea::placeholder{ color: rgba(255,255,255,.45); }

    input:focus, textarea:focus, select:focus{
      border-color: rgba(255,79,216,.55);
      box-shadow: var(--ring);
    }

    .row{
      display:flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }

    .btn{
      width: 100%;
      padding: 12px 14px;
      border: 0;
      border-radius: 14px;
      font-weight: 700;
      font-size: 15px;
      cursor: pointer;
      color: white;
      background: linear-gradient(135deg, rgba(124,58,237,1), rgba(255,79,216,1));
      box-shadow: 0 10px 24px rgba(124,58,237,.14), 0 10px 24px rgba(255,79,216,.10);
      transition: transform .06s ease, filter .12s ease;
      user-select: none;
      -webkit-tap-highlight-color: transparent;
    }
    .btn:active{ transform: translateY(1px); filter: brightness(.98); }

    .btn.secondary{
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.14);
      box-shadow: none;
      font-weight: 600;
      color: var(--text);
    }

    .btn.ghost{
      background: rgba(255,255,255,.04);
      border: 1px solid rgba(255,255,255,.12);
      box-shadow: none;
      font-weight: 700;
    }

    .btn.small{
      width: auto;
      padding: 10px 12px;
      border-radius: 12px;
      font-size: 14px;
    }

    .inline{
      display:flex;
      gap:10px;
      align-items: center;
      flex-wrap: wrap;
    }
    .inline select{ flex: 1; min-width: 220px; }
    .inline .btn.small{ flex: 0 0 auto; }

    .status{
      margin-top: 14px;
      padding: 12px;
      border-radius: 14px;
      background: rgba(0,0,0,.28);
      border: 1px solid rgba(255,255,255,.10);
    }

    .pill{
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.10);
    }

    code{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 12px;
      padding: 2px 6px;
      border-radius: 8px;
      background: rgba(0,0,0,.35);
      border: 1px solid rgba(255,255,255,.10);
      color: rgba(255,255,255,.9);
    }

    .small{
      font-size: 12px;
      color: var(--muted2);
      margin-top: 10px;
      line-height: 1.35;
    }

    .err{
      margin-top: 10px;
      color: #ffd1dc;
      background: rgba(239,68,68,.12);
      border: 1px solid rgba(239,68,68,.20);
      padding: 10px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 13px;
    }

    .eventGrid{
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 10px;
    }

    .eventBtn{
      padding: 12px 12px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.06);
      color: white;
      font-weight: 700;
      cursor: pointer;
      transition: transform .06s ease, filter .12s ease;
    }
    .eventBtn:active{ transform: translateY(1px); }

    .eventBtn.pink{
      background: linear-gradient(135deg, rgba(255,79,216,1), rgba(124,58,237,1));
      border: 0;
    }

    .hintRow{
      display:flex;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .hintRow .small{ margin-top: 0; }
  </style>
"""

LOGIN_HTML = f"""<!doctype html>
<html>
<head>
{THEME_HEAD}
  <title>Love Box • Login</title>
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="logo" aria-hidden="true"></div>
      <div>
        <h1>Love Box</h1>
        <div class="sub">Enter the password to send messages & events.</div>
      </div>
    </div>

    <div class="card">
      <form method="post" action="/login">
        <label>Password</label>
        <input type="password" name="password" placeholder="Password" required />
        <button class="btn" type="submit">Login</button>
      </form>

      {{% if error %}}<div class="err">{{{{ error }}}}</div>{{% endif %}}

      <div class="small">Tip: bookmark <code>/send</code> after logging in.</div>
    </div>
  </div>
</body>
</html>
"""

SEND_HTML = f"""<!doctype html>
<html>
<head>
{THEME_HEAD}
  <title>Love Box • Send</title>
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="logo" aria-hidden="true"></div>
      <div>
        <h1>Send Love</h1>
        <div class="sub">Queue v2 (max {MAX_QUEUE}). Status: Sent → Delivered → Seen.</div>
      </div>
    </div>

    <div class="grid">
      <!-- LEFT: Message -->
      <div class="card">
        <h2>Message</h2>
        <div class="sub">Pick a box, write a message, drop an emoji tag, send.</div>

        <form method="post" action="/send" id="msgForm">
          <label>Target box</label>
          <select name="target" required>
            <option value="{{{{ box1 }}}}">{{{{ box1 }}}}</option>
            <option value="{{{{ box2 }}}}">{{{{ box2 }}}}</option>
          </select>

          <label>Message</label>
          <textarea id="messageBox" name="text" rows="4" placeholder="Type something sweet…"></textarea>

          <label>Emoji picker</label>
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

            <button class="btn ghost small" type="button" onclick="insertEmoji()">Insert</button>
          </div>

          <button class="btn" type="submit">Send Message</button>
        </form>

        {{% if msg_id %}}
          <div class="status">
            <div class="hintRow">
              <div class="small"><strong>Message ID:</strong> <code id="msgId">{{{{ msg_id }}}}</code></div>
              <div class="small"><strong>Status:</strong> <span class="pill" id="statusPill">{{{{ status_text }}}}</span></div>
            </div>
            <div class="small">This updates automatically.</div>
          </div>
        {{% elif status_text %}}
          <div class="status"><span class="pill">{{{{ status_text }}}}</span></div>
        {{% endif %}}
      </div>

      <!-- RIGHT: Events -->
      <div class="card">
        <h2>Quick Events</h2>
        <div class="sub">Send a quick animation trigger.</div>

        <form method="post" action="/send">
          <label>Target box</label>
          <select name="target" required>
            <option value="{{{{ box1 }}}}">{{{{ box1 }}}}</option>
            <option value="{{{{ box2 }}}}">{{{{ box2 }}}}</option>
          </select>

          <input type="hidden" name="text" value="" />

          <div class="eventGrid">
            <button class="eventBtn pink"  name="event" value="heartbeat" type="submit">❤️ Heartbeat</button>
            <button class="eventBtn"       name="event" value="rainbow"   type="submit">🌈 Rainbow</button>
            <button class="eventBtn"       name="event" value="breathe"   type="submit">😌 Breathe</button>
            <button class="eventBtn pink"  name="event" value="ping"      type="submit">✨ Ping</button>
          </div>

          <div class="small" style="margin-top:12px;">
            Tip: emojis render on the box as tags like <code>[HEART]</code>.
          </div>
        </form>
      </div>
    </div>
  </div>

  <script>
    function insertEmoji() {{
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
    }}

    async function pollStatus() {{
      const el = document.getElementById("msgId");
      const pill = document.getElementById("statusPill");
      if (!el || !pill) return;
      const msgId = el.textContent.trim();
      if (!msgId) return;

      try {{
        const r = await fetch("/status?msg_id=" + encodeURIComponent(msgId));
        if (!r.ok) return;
        const data = await r.json();
        if (data && data.ok) {{
          pill.textContent = data.status.toUpperCase();
        }}
      }} catch (e) {{}}
    }}

    if (document.getElementById("msgId")) {{
      setInterval(pollStatus, 2000);
    }}
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
        return jsonify({"ok": True})

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
