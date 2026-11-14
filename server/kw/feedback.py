"""Contact / feedback messages from the site.

Every message is appended to data/feedback.jsonl. When SMTP is configured (see alerts.py) and CONTACT_EMAILS
holds a comma-separated list of addresses, each message is also mailed there.
"""
import datetime as dt
import json
import os
import re
import threading
import time
from collections import defaultdict, deque

from . import alerts
from .firms import DATA

KINDS = ("question", "suggestion", "bug", "data", "other")
PATH = DATA / "feedback.jsonl"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
LIMIT, WINDOW_S = 5, 3600  # per sender address, per hour

_lock = threading.Lock()
_recent: dict[str, deque] = defaultdict(deque)  # ponytail: in-memory per process, resets on restart


def recipients():
    return [a.strip() for a in os.environ.get("CONTACT_EMAILS", "").split(",") if EMAIL_RE.match(a.strip())]


def _clean(v, n):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(v or "")).strip()[:n]


def submit(body: dict, ip: str = "?"):
    """Validate and store one message. Returns {"stored", "emailed"}; ValueError on bad input."""
    if _clean(body.get("website"), 200):  # honeypot field, hidden from people
        return {"stored": True, "emailed": False}
    kind = body.get("kind") if body.get("kind") in KINDS else "other"
    message = _clean(body.get("message"), 5000)
    name = _clean(body.get("name"), 120)
    email = _clean(body.get("email"), 254)
    page = _clean(body.get("page"), 60)
    if len(message) < 10:
        raise ValueError("Please write at least a sentence (10 characters).")
    if email and not EMAIL_RE.match(email):
        raise ValueError("That email address does not look right. Leave it empty to stay anonymous.")
    now = time.time()
    with _lock:
        q = _recent[ip]
        while q and now - q[0] > WINDOW_S:
            q.popleft()
        if len(q) >= LIMIT:
            raise ValueError("Too many messages from here in the last hour. Please try again later.")
        q.append(now)
        rec = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "kind": kind, "name": name,
               "email": email, "page": page, "message": message}
        PATH.parent.mkdir(parents=True, exist_ok=True)
        with PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    emailed = False
    to = recipients()
    if to and alerts.smtp_ready():
        text = f"{kind} from {name or 'anonymous'} <{email or 'no email'}> on page {page or '-'}\n\n{message}"
        try:
            for addr in to:
                alerts.send_email(addr, f"Kiln Watch {kind}: {message[:60]}", text)
            emailed = True
        except Exception:  # the message is already stored; mail failure must not lose it or fail the request
            emailed = False
    return {"stored": True, "emailed": emailed}


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    PATH = Path(tempfile.mkdtemp()) / "fb.jsonl"
    for bad in ({"message": "short"}, {"message": "a long enough message", "email": "nope"}):
        try:
            submit(bad, "t")
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
    assert submit({"message": "hello there, a question", "kind": "question", "email": "a@b.org"}, "t")["stored"]
    assert submit({"message": "spam spam spam spam", "website": "x"}, "t") == {"stored": True, "emailed": False}
    for _ in range(LIMIT - 1):
        submit({"message": "another real message"}, "t")
    try:
        submit({"message": "one too many messages"}, "t")
        raise AssertionError("rate limit not applied")
    except ValueError:
        pass
    assert len(PATH.read_text(encoding="utf-8").splitlines()) == LIMIT  # honeypot never stored
    print("feedback ok")
