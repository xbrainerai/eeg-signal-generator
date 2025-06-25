# disk_queue.py
import sqlite3
import os
import logging
from datetime import datetime
class DiskQueue:
    def __init__(self, db_path='buffer.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    payload TEXT
                )
            """)
    def push(self, timestamp, payload):
        try:
            with self.conn:
                self.conn.execute("INSERT INTO queue (timestamp, payload) VALUES (?, ?)", (timestamp, payload))
        except Exception as e:
            logging.error(f"Failed to push to disk queue: {e}")
    def pop(self, limit=10):
        try:
            with self.conn:
                cursor = self.conn.execute("SELECT id, payload FROM queue ORDER BY id ASC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                if rows:
                    ids = [row[0] for row in rows]
                    self.conn.execute("DELETE FROM queue WHERE id IN (%s)" % ','.join('?' * len(ids)), ids)
                    return [row[1] for row in rows]
        except Exception as e:
            logging.error(f"Failed to pop from disk queue: {e}")
        return []
    def size(self):
        try:
            with self.conn:
                cursor = self.conn.execute("SELECT COUNT(*) FROM queue")
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            logging.error(f"Failed to get queue size: {e}")
            return 0
    def close(self):
        self.conn.close()