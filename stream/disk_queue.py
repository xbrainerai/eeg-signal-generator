from __future__ import annotations
import sqlite3
import logging
from pathlib import Path
from typing import List

class DiskQueue:
    def __init__(self, db_path: str | Path = "buffer.db") -> None:
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    # ---------------- private ---------------- #
    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        REAL,
                    payload   TEXT
                );
                """
            )

    # ----------------  API  ------------------ #
    def push(self, ts: float, payload: str) -> None:
        try:
            with self.conn:
                self.conn.execute("INSERT INTO queue (ts, payload) VALUES (?, ?)", (ts, payload))
        except Exception as exc:  # noqa: BLE001
            logging.error("DiskQueue push() failed: %s", exc, exc_info=True)

    def pop(self, limit: int = 10) -> List[str]:
        try:
            with self.conn:
                cur = self.conn.execute(
                    "SELECT id, payload FROM queue ORDER BY id ASC LIMIT ?", (limit,)
                )
                rows = cur.fetchall()
                if not rows:
                    return []
                ids = [row[0] for row in rows]
                self.conn.execute(
                    f"DELETE FROM queue WHERE id IN ({','.join('?' for _ in ids)})", ids
                )
                return [row[1] for row in rows]
        except Exception as exc:  # noqa: BLE001
            logging.error("DiskQueue pop() failed: %s", exc, exc_info=True)
            return []

    def size(self) -> int:
        with self.conn:
            cur = self.conn.execute("SELECT COUNT(*) FROM queue")
            return int(cur.fetchone()[0])

    def close(self) -> None:
        self.conn.close()
