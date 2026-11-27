"""SQLite persistence for the CoreLoop demo app. SYNTHETIC scenario; the file holds only user decisions.

The synthetic world is regenerated deterministically from (seed, n_cores). What persists is the
operator's side: the simulated clock, the scenario, every decision (ship now / submit / defer /
dismiss) and an append-only audit trail. Rebuilding the world from these rows reproduces the state.
"""
import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("CORELOOP_DB") or Path(__file__).resolve().parent / "coreloop_demo.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    core_id INTEGER NOT NULL,
    kind TEXT NOT NULL,              -- alert kind the decision answers
    action TEXT NOT NULL,            -- approve | defer | dismiss
    day INTEGER NOT NULL,            -- simulated day the decision was taken
    defer_until INTEGER,
    note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    core_id INTEGER,
    event TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path=DEFAULT_DB):
        self.path = str(path)
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        for k, v in (("seed", 11), ("n_cores", 600), ("today", 130)):
            if self.get(k) is None:
                self.set(k, v)

    # ---- meta ----
    def get(self, key, default=None):
        r = self.con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set(self, key, value):
        self.con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (key, json.dumps(value)))
        self.con.commit()

    # ---- decisions ----
    def add_decision(self, core_id, kind, action, day, defer_until=None, note=""):
        self.con.execute("INSERT INTO decisions(core_id,kind,action,day,defer_until,note) VALUES(?,?,?,?,?,?)",
                         (core_id, kind, action, day, defer_until, note))
        self.con.commit()

    def decisions(self):
        return [dict(r) for r in self.con.execute("SELECT * FROM decisions ORDER BY id")]

    # ---- audit trail ----
    def log(self, day, event, detail, core_id=None):
        self.con.execute("INSERT INTO audit_trail(day,core_id,event,detail) VALUES(?,?,?,?)",
                         (day, core_id, event, detail))
        self.con.commit()

    def trail(self, limit=500):
        return [dict(r) for r in self.con.execute("SELECT * FROM audit_trail ORDER BY id DESC LIMIT ?", (limit,))]

    def reset(self, seed=None, n_cores=None, today=None):
        self.con.executescript("DELETE FROM decisions; DELETE FROM audit_trail; DELETE FROM meta;")
        for k, v in (("seed", 11 if seed is None else seed), ("n_cores", 600 if n_cores is None else n_cores),
                     ("today", 130 if today is None else today)):
            self.set(k, v)
        self.log(self.get("today"), "scenario_reset", f"seed={self.get('seed')} n_cores={self.get('n_cores')}")
