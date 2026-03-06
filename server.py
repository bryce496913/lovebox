import urequests as requests
import usocket as socket

BASE_URL = "https://lovebox-i52c.onrender.com"
_TIMEOUT_S = 12  # Render cold starts can exceed a few seconds

def set_timeout(seconds: int):
    global _TIMEOUT_S
    try:
        _TIMEOUT_S = int(seconds)
    except:
        _TIMEOUT_S = 12

def _prep():
    try:
        socket.setdefaulttimeout(_TIMEOUT_S)
    except:
        pass

def _url(path: str) -> str:
    return BASE_URL + path

def _safe_close(r):
    try:
        if r:
            r.close()
    except:
        pass

def _safe_json(r):
    try:
        return r.json()
    except:
        try:
            txt = r.text
            return {"ok": False, "error": "bad_json", "status": getattr(r, "status_code", None),
                    "body": (txt[:120] if txt else "")}
        except:
            return {"ok": False, "error": "bad_json_no_body", "status": getattr(r, "status_code", None)}

def health():
    _prep()
    r = None
    try:
        r = requests.get(_url("/health"))
        return _safe_json(r)
    except Exception as e:
        return {"ok": False, "error": "health_exception", "detail": str(e)}
    finally:
        _safe_close(r)

def register(box_id, token):
    _prep()
    r = None
    try:
        r = requests.post(_url("/api/register"), json={"box_id": box_id, "token": token})
        return _safe_json(r)
    except Exception as e:
        return {"ok": False, "error": "register_exception", "detail": str(e)}
    finally:
        _safe_close(r)

def check(box_id, token):
    _prep()
    r = None
    try:
        r = requests.get(_url("/api/check") + "?box_id=" + box_id + "&token=" + token)
        return _safe_json(r)
    except Exception as e:
        return {"ok": False, "error": "check_exception", "detail": str(e)}
    finally:
        _safe_close(r)

def ack(box_id, token, msg_id):
    _prep()
    r = None
    try:
        r = requests.post(_url("/api/ack"), json={"box_id": box_id, "token": token, "msg_id": msg_id})
        return _safe_json(r)
    except Exception as e:
        return {"ok": False, "error": "ack_exception", "detail": str(e)}
    finally:
        _safe_close(r)

def send_event(box_id, token, event_name):
    _prep()
    r = None
    try:
        r = requests.post(_url("/api/send_event"),
                          json={"box_id": box_id, "token": token, "event": event_name})
        return _safe_json(r)
    except Exception as e:
        return {"ok": False, "error": "send_event_exception", "detail": str(e)}
    finally:
        _safe_close(r)

def pending_count(box_id, token):
    _prep()
    r = None
    try:
        r = requests.get(_url("/api/pending_count") + "?box_id=" + box_id + "&token=" + token)
        return _safe_json(r)
    except Exception as e:
        return {"ok": False, "error": "pending_count_exception", "detail": str(e)}
    finally:
        _safe_close(r)
