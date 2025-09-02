import os
import sqlite3
import string
import random
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, abort

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "urls.db"
BUG_REDIRECT = True

BUILD_INFO = APP_DIR / ".buildinfo.json"

def read_buildinfo():
    try:
        with open(BUILD_INFO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _fmt_mdt_from_utc_str(utc_str: str) -> str:
    # utc_str like "2025-09-02T16:45:12Z"
    dt_utc = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(ZoneInfo("America/Denver")).strftime("%Y-%m-%d %I:%M:%S %p %Z")

BUILD = read_buildinfo()
GIT_SHA = BUILD.get("git_sha", "unknown")

# Prefer pipeline-provided UTC → convert to MDT; fallback to "now" in MDT
if "deployed_at_utc" in BUILD:
    DEPLOYED_AT = _fmt_mdt_from_utc_str(BUILD["deployed_at_utc"])
else:
    DEPLOYED_AT = datetime.now(ZoneInfo("America/Denver")).strftime("%Y-%m-%d %I:%M:%S %p %Z")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "demo-secret")

# shown on the page so each deploy looks different
DEPLOYED_AT = os.environ.get("DEPLOYED_AT") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            code TEXT PRIMARY KEY,
            url  TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def ensure_scheme(u: str) -> str:
    # add https:// if user typed "example.com"
    if u.startswith(("http://", "https://")):
        return u
    return "https://" + u


def gen_code(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


@app.before_request
def _init():
    init_db()


@app.get("/")
def home():
    rows = db().execute(
        "SELECT code, url FROM urls ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    return render_template(
        "index.html",
        deployed_at=DEPLOYED_AT,
        rows=rows,
        short_url=None,
        short_code=None,
        short_href=None,
        git_sha=GIT_SHA,
    )

@app.post("/shorten")
def shorten():
    long_url = (request.form.get("url") or "").strip()
    if not long_url:
        return redirect("/")

    long_url = ensure_scheme(long_url)

    conn = db()
    while True:
        code = gen_code()
        try:
            conn.execute("INSERT INTO urls(code, url) VALUES (?, ?)", (code, long_url))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            continue

    short_url = urljoin(request.host_url, code)
    rows = conn.execute(
        "SELECT code, url FROM urls ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    #BUG
    short_href = "https://datadog.com" if BUG_REDIRECT else short_url

    return render_template(
        "index.html",
        rows=rows,
        short_url=short_url,
        short_code=code,
        short_href=short_href,
        git_sha=GIT_SHA,
    )

@app.get("/<code>")
def go(code):
    if BUG_REDIRECT:
        return redirect("https://datadog.com", code=302)  # undeniable bug
    row = db().execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
    if not row:
        abort(404)
    return redirect(row["url"], code=302)

@app.get("/healthz")
def healthz():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}