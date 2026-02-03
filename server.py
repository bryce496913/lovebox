import os
import sqlite3
import time
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session


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
    with open("schema.sql", "r", encoding="utf-8") as f:
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


# Initialize DB at import time (so gunicorn also initializes it)
try:
    init_db()
except Exception as e:
    # Render logs will show this if schema file missing, etc.
    print("DB init failed:", e)


# =========================
# Auth / Routing Rules
# =========================
def auth_box(box_id: str, token: str):
    """Validate a device by box_id + token, return dict {box_id, paired_to} or None."""
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
    """
    Store exactly ONE pending item per box (overwrites any previous pending item).
    msg_type: "text" or "event"
    """
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
    """
    Love Box registers itself (auth check) and gets paired_to back.
    POST JSON: { box_id, token }
    """
    data = request.get_json(force=True, silent=True) or {}
    box_id = data.get("box_id", "")
    token = data.get("token", "")
    info = auth_box(box_id, token)
    if not info:
        return jsonify({"ok": False, "error": "auth_failed"}), 401
    return jsonify({"ok": True, "paired_to": info["paired_to"]})


@app.get("/api/check")
def api_check():
    """
    Love Box polls for a pending message/event.
    GET params: box_id, token
    """
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
        "type": row["msg_type"],      # "text" | "event"
        "text": row["msg_text"],
        "event": row["msg_event"],
        "created_at": row["created_at"],
    })


@app.post("/api/ack")
def api_ack():
    """
    Love Box acknowledges it processed msg_id.
    POST JSON: { box_id, token, msg_id }
    """
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
    """
    Love Box sends a button-trigger event to its paired box.
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
    put_inbox(target, "event", msg_event=event)
    return jsonify({"ok": True, "sent_to": target})


# For local dev only
if __name__ == "__main__":
    # init_db() already attempted at import; safe to call again locally
    try:
        init_db()
    except Exception as e:
        print("DB init failed:", e)
    app.run(host="0.0.0.0", port=5000, debug=True)
