from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.environ.get("STATE_DB_PATH", "state.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS notified (
  listing_id TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_notified TEXT NOT NULL
);
"""

class StateStore:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def already_notified(self, listing_id: str, fingerprint: str) -> bool:
        cur = self.conn.execute(
            "SELECT fingerprint FROM notified WHERE listing_id = ?", (listing_id,)
        )
        row = cur.fetchone()
        if not row:
            return False
        return row[0] == fingerprint

    def upsert_notification(self, listing_id: str, fingerprint: str) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        cur = self.conn.execute("SELECT listing_id FROM notified WHERE listing_id = ?", (listing_id,))
        if cur.fetchone():
            self.conn.execute(
                "UPDATE notified SET fingerprint=?, last_notified=? WHERE listing_id=?",
                (fingerprint, now, listing_id),
            )
        else:
            self.conn.execute(
                "INSERT INTO notified(listing_id, fingerprint, first_seen, last_notified) VALUES (?,?,?,?)",
                (listing_id, fingerprint, now, now),
            )
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
