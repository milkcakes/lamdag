"""WSGI entry point for cloud deployments (Render / Railway / gunicorn).

The desktop entry point (app.py's __main__ block) opens a browser, picks a
port, and sets up LAN access. That logic must not run under gunicorn; this
module just exposes the Flask `app` and ensures the database is ready.
"""

import os

# On cloud the project files are in /app and the database ships with the
# repo, so the writable data dir defaults to the project dir. Make sure it
# exists before the app imports.
from database.init_db import get_connection, init_database, seed_data
from app import app  # noqa: E402  (must come after init_db import)


def _ensure_database():
    init_database()
    conn = get_connection()
    try:
        fresh = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0
    finally:
        conn.close()
    if fresh:
        seed_data()


_ensure_database()
