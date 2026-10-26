import sqlite3
import threading
from contextlib import contextmanager

from config.settings import DB_PATH


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            trigger_at TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    conn.commit()


@contextmanager
def get_conn():
    """Short-lived connection (safe from any thread). Used by ReminderService."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _init_db(conn)
        yield conn
    finally:
        conn.close()


class MemoryStore:
    """SQLite store; chat runs in QThread so connection allows cross-thread access."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        _init_db(self._conn)

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]

    def get_profile(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM profile WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_profile(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO profile (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    def get_user_name(self) -> str:
        return self.get_profile("user_name", "")

    def get_pet_name(self) -> str:
        return self.get_profile("pet_name", "")

    def set_user_name(self, name: str) -> None:
        self.set_profile("user_name", name.strip())

    def set_pet_name(self, name: str) -> None:
        self.set_profile("pet_name", name.strip())

    def add_memory(self, content: str) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO memories (content) VALUES (?)", (content,))
            self._conn.commit()

    def recent_memories(self, limit: int = 5) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT content FROM memories ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [r["content"] for r in reversed(rows)]

    def add_chat(self, role: str, content: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO chat_history (role, content) VALUES (?, ?)",
                (role, content),
            )
            self._conn.commit()

    def recent_chats(self, limit: int = 10) -> list[dict[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def trim_chats(self, keep: int = 50) -> None:
        with self._lock:
            self._conn.execute(
                """
                DELETE FROM chat_history WHERE id NOT IN (
                    SELECT id FROM chat_history ORDER BY id DESC LIMIT ?
                )
                """,
                (keep,),
            )
            self._conn.commit()

    def clear_chats(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM chat_history")
            self._conn.commit()
