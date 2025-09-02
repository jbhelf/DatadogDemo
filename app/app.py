import os
import sqlite3
import string
import random
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, abort

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "urls.db"

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
    # show form + last few links
    rows = db().execute(
        "SELECT code, url FROM urls ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    return render_template("index.html", deployed_at=DEPLOYED_AT, rows=rows, short_url=None, short_code=None)


@app.post("/shorten")
def shorten():
    long_url = (request.form.get("url") or "").strip()
    if not long_url:
        return redirect("/")  # nothing entered

    long_url = ensure_scheme(long_url)

    # generate a unique short code
    conn = db()
    while True:
        code = gen_code()
        try:
            conn.execute("INSERT INTO urls(code, url) VALUES (?, ?)", (code, long_url))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            continue  # collision; try another code

    short_url = urljoin(request.host_url, code)  # absolute URL to show the user
    rows = conn.execute(
        "SELECT code, url FROM urls ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    return render_template("index.html", deployed_at=DEPLOYED_AT, rows=rows, short_url=short_url, short_code=code)


@app.get("/<code>")
def go(code):
    row = db().execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
    if not row:
        abort(404)
    return redirect(row["url"], code=302)


@app.get("/healthz")
def healthz():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}