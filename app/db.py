"""SQLite storage for kits (bags), items (tagged objects) and settings."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS kits (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    epc TEXT NOT NULL UNIQUE,
    kit_id INTEGER REFERENCES kits(id) ON DELETE SET NULL,
    notes TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "tx_power": 20.0,          # dBm. Lower = shorter range (fewer false "present").
    "region": "US",            # US / EU / KR / CN900 / CN800 - must match your country
    "presence_timeout": 5.0,   # seconds without a read before an item counts as missing
    "min_rssi": -75.0,         # dBm. Weaker than this = "weak" (maybe outside the bag)
    "smoothing": 5,            # number of recent reads averaged for the RSSI value
    "text_scale": 1.5,         # text and icon size on the screens (1.0 = original size)
}


class DB:
    def __init__(self, path: str):
        self.path = path
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=5)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # -- kits -----------------------------------------------------------
    def kits(self):
        with self.conn() as c:
            return c.execute(
                "SELECT k.*, COUNT(i.id) AS n FROM kits k LEFT JOIN items i ON i.kit_id = k.id "
                "GROUP BY k.id ORDER BY k.name COLLATE NOCASE"
            ).fetchall()

    def kit(self, kit_id):
        with self.conn() as c:
            return c.execute("SELECT * FROM kits WHERE id = ?", (kit_id,)).fetchone()

    def add_kit(self, name):
        with self.conn() as c:
            return c.execute("INSERT INTO kits (name, created) VALUES (?, ?)", (name, time.time())).lastrowid

    def rename_kit(self, kit_id, name):
        with self.conn() as c:
            c.execute("UPDATE kits SET name = ? WHERE id = ?", (name, kit_id))

    def delete_kit(self, kit_id):
        with self.conn() as c:
            c.execute("DELETE FROM kits WHERE id = ?", (kit_id,))

    # -- items ----------------------------------------------------------
    def items(self, kit_id=None):
        q = ("SELECT i.*, k.name AS kit_name FROM items i LEFT JOIN kits k ON k.id = i.kit_id")
        args = ()
        if kit_id is not None:
            q += " WHERE i.kit_id = ?"
            args = (kit_id,)
        with self.conn() as c:
            return c.execute(q + " ORDER BY i.name COLLATE NOCASE", args).fetchall()

    def item(self, item_id):
        with self.conn() as c:
            return c.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    def item_by_epc(self, epc):
        with self.conn() as c:
            return c.execute("SELECT * FROM items WHERE epc = ?", (epc,)).fetchone()

    def known_epcs(self):
        with self.conn() as c:
            return {r["epc"]: r["name"] for r in c.execute("SELECT epc, name FROM items")}

    def add_item(self, name, epc, kit_id, notes=""):
        with self.conn() as c:
            return c.execute(
                "INSERT INTO items (name, epc, kit_id, notes, created) VALUES (?, ?, ?, ?, ?)",
                (name, epc.upper(), kit_id, notes, time.time()),
            ).lastrowid

    def update_item(self, item_id, name, kit_id, notes):
        with self.conn() as c:
            c.execute("UPDATE items SET name = ?, kit_id = ?, notes = ? WHERE id = ?", (name, kit_id, notes, item_id))

    def delete_item(self, item_id):
        with self.conn() as c:
            c.execute("DELETE FROM items WHERE id = ?", (item_id,))

    # -- settings -------------------------------------------------------
    def settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        with self.conn() as c:
            for row in c.execute("SELECT key, value FROM settings"):
                if row["key"] in s:
                    default = DEFAULT_SETTINGS[row["key"]]
                    s[row["key"]] = type(default)(row["value"])
        return s

    def save_setting(self, key, value):
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
