#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path
import importlib.util
import sys

# --- paths ---
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "urls.db"

def wipe_db():
    if not DB_PATH.exists():
        print(f"[wipe] {DB_PATH} not found — nothing to do.")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM urls;")
        conn.commit()
        print("[wipe] cleared urls table")
    finally:
        conn.close()

def load_flask_app():
    app_py = APP_DIR / "app.py"
    spec = importlib.util.spec_from_file_location("ddemo_app", app_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {app_py}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ddemo_app"] = mod
    spec.loader.exec_module(mod)
    if not hasattr(mod, "app"):
        raise AttributeError(f"Module {app_py} does not have attribute 'app'")
    return mod.app

def run_server():
    flask_app = load_flask_app()
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") in {"1", "true", "True"}
    print(f"[serve] starting Flask on http://127.0.0.1:{port} (debug={debug})")
    flask_app.run(host="127.0.0.1", port=port, debug=debug)

if __name__ == "__main__":
    wipe_db()
    run_server()