from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as date_parser

from config.settings import DB_PATH


def _init_reminder_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            trigger_at TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    conn.commit()


class ReminderService:
    def __init__(self, on_trigger: Callable[[int, str], None] | None = None):
        self._on_trigger = on_trigger
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _init_reminder_db(conn)
        return conn

    def add(self, title: str, trigger_at: str) -> int:
        dt = date_parser.parse(trigger_at)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        iso = dt.isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (title, trigger_at) VALUES (?, ?)",
                (title, iso),
            )
            conn.commit()
            rid = cur.lastrowid
        self._schedule(rid, title, dt)
        return rid

    def _schedule(self, rid: int, title: str, dt: datetime) -> None:
        job_id = f"reminder_{rid}"

        def fire():
            self._mark_done(rid)
            if self._on_trigger:
                self._on_trigger(rid, title)

        self._scheduler.add_job(fire, "date", run_date=dt, id=job_id, replace_existing=True)

    def _mark_done(self, rid: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))
            conn.commit()

    def list_pending(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, trigger_at FROM reminders WHERE done = 0 ORDER BY trigger_at"
            ).fetchall()
            return [dict(r) for r in rows]

    def cancel(self, rid: int) -> bool:
        job_id = f"reminder_{rid}"
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ? AND done = 0", (rid,))
            conn.commit()
            return cur.rowcount > 0

    def load_pending_jobs(self) -> None:
        """Schedule future reminders; mark overdue ones done without notifying."""
        now = datetime.now()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, trigger_at FROM reminders WHERE done = 0"
            ).fetchall()
        for row in rows:
            dt = date_parser.parse(row["trigger_at"])
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            if dt > now:
                self._schedule(row["id"], row["title"], dt)
            else:
                self._mark_done(row["id"])

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
