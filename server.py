import os
import sqlite3
import time
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, abort

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

# =========================
# FORCE TEMPLATE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# Optional: allow debug route to show what's deployed
DEBUG_TEMPLATES = os.environ.get("DEBUG_TEMPLATES", "0") == "1"

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = APP_SECRET

print("---- LoveBox Boot ----")
print("BASE_DIR:", BASE_DIR)
print("TEMPLATE_DIR:", TEMPLATE_DIR)
try:
    print("templates/ contents:", os.listdir(TEMPLATE_DIR))
except Exception as e:
    print("templates/ not readable:", repr(e))

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

    # Upsert paired devices
    conn.execute(
        "INSERT OR REPLACE INTO devices (box_id, token, paired_to) VALUES (?, ?, ?)",
        (BOX1_ID, BOX1_TOKEN, BOX2_ID),
    )
    conn.execute(
        "INSERT OR REPLACE INTO devices (box_id, token, paired_to) VALUES (?, ?, ?)",
        (BOX2_ID, BOX2_TOKEN, BOX1_ID),
    )

    # Ensure inbox rows exist
    conn.execute("INSERT OR IGNORE INTO inbox (box_id) VALUES (?)", (BOX1_ID,))
    conn.execute("INSERT OR IGNORE INTO inbox (box_id) VALUES (?)", (BOX2_ID,))
    conn.commit()
    conn.close()

# Initialize DB at import time
try:
    init_db()
except Exception as e:
    print("DB init failed:", e)

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
# Debug route (optional)
# =========================
@app.get("/debug/templates")
def debug_templates():
    if not DEBUG_TEMPLATES:
        abort(404)
    out = {
        "BASE_DIR": BASE_DIR,
        "TEMPLATE_DIR": TEMPLATE_DIR,
        "templates_exists": os.path.isdir(TEMPLATE_DIR),
        "templates_list": [],
    }
    try:
        out["templates_list"] = os.listdir(TEMPLATE_DIR)
    except Exception as e:
        out["templates_error"] = repr(e)
    return jsonify(out)

@app.get("/health")
def health():
    return jsonify({"ok": True})

# =========================
# Web UI
# =========================
@app.get("/")
def root():
    if session.get("logged_in"):
        return redirect(url_for("send_page"))
    return redirect(url_for("login_page"))

@app.get("/login")
def login_page():
    return render_template("login.html")

@app.post("/login")
def login_post():
    pwd = request.form.get("password", "")
    if pwd == WEB_PASSWORD:
        session["logged_in"] = True
        return redirect(url_for("send_page"))
    return render_template("login.html", error="Wrong password")

@app.get("/send")
def send_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return render_template("send.html", box1=BOX1_ID, box2=BOX2_ID)

@app.post("/send")
def send_post():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    target = request.form.get("target", "")
    text = (request.form.get("text", "") or "").strip()
    event = (request.form.get("event", "") or "").strip()

    if target not in (BOX1_ID, BOX2_ID):
        return render_template("send.html", box1=BOX1_ID, box2=BOX2_ID, status="Invalid target")

    if event:
        put_inbox(target, "event", msg_event=event)
        return render_template("send.html", box1=BOX1_ID, box2=BOX2_ID, status=f"Sent event: {event} → {target}")

    if not text:
        return render_template("send.html", box1=BOX1_ID, box2=BOX2_ID, status="Type a message first")

    put_inbox(target, "text", msg_text=text)
    return render_template("send.html", box1=BOX1_ID, box2=BOX2_ID, status=f"Sent message → {target}")

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
