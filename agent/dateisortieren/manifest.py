"""Digitales Manifest / Logbuch aller Dateiaktionen (SQLite).

Jede Aktion wird VOR der Ausführung protokolliert. Dadurch kann jede Verschiebung,
Umbenennung, Löschung (Quarantäne) und Komprimierung rückgängig gemacht werden.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from .models import Action

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    batch_id TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    src TEXT NOT NULL,
    dst TEXT,
    backup_path TEXT,
    reason TEXT,
    confidence REAL,
    category TEXT,
    tags TEXT,
    details TEXT,
    error TEXT,
    created_at TEXT,
    applied_at TEXT,
    undone_at TEXT,
    synced INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_batch ON actions(batch_id);
CREATE INDEX IF NOT EXISTS idx_actions_src ON actions(src);

CREATE TABLE IF NOT EXISTS file_index (
    path TEXT PRIMARY KEY,
    size INTEGER,
    mtime REAL,
    sha256 TEXT,
    phash TEXT,
    simhash TEXT
);
CREATE INDEX IF NOT EXISTS idx_file_sha ON file_index(sha256);
CREATE INDEX IF NOT EXISTS idx_file_size ON file_index(size);

CREATE TABLE IF NOT EXISTS optimized (
    path TEXT PRIMARY KEY,
    size INTEGER,
    mtime REAL
);
"""

_COLUMNS = [
    "id", "batch_id", "kind", "status", "src", "dst", "backup_path", "reason", "confidence",
    "category", "tags", "details", "error", "created_at", "applied_at", "undone_at",
]


class Manifest:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---------------------------------------------------------------- actions
    def save(self, action: Action, synced: bool = False) -> None:
        values = [
            action.id, action.batch_id, action.kind, action.status, action.src, action.dst,
            action.backup_path, action.reason, action.confidence, action.category,
            json.dumps(action.tags), json.dumps(action.details, default=str), action.error,
            action.created_at, action.applied_at, action.undone_at,
        ]
        with self._lock:
            self._conn.execute(
                f"INSERT OR REPLACE INTO actions ({', '.join(_COLUMNS)}, synced) "
                f"VALUES ({', '.join('?' * len(_COLUMNS))}, ?)",
                [*values, int(synced)],
            )
            self._conn.commit()

    def save_many(self, actions: Iterable[Action]) -> None:
        for action in actions:
            self.save(action)

    def get(self, action_id: str) -> Action | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return _row_to_action(row) if row else None

    def query(self, status: str | list[str] | None = None, batch_id: str | None = None,
              limit: int = 500, newest_first: bool = True) -> list[Action]:
        sql, params = "SELECT * FROM actions WHERE 1=1", []
        if status:
            statuses = [status] if isinstance(status, str) else status
            sql += f" AND status IN ({', '.join('?' * len(statuses))})"
            params += statuses
        if batch_id:
            sql += " AND batch_id = ?"
            params.append(batch_id)
        sql += f" ORDER BY COALESCE(applied_at, created_at) {'DESC' if newest_first else 'ASC'} LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_action(r) for r in rows]

    def open_proposal_for(self, src: str, kind: str) -> Action | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM actions WHERE src = ? AND kind = ? AND status IN ('proposed', 'approved') LIMIT 1",
                (src, kind),
            ).fetchone()
        return _row_to_action(row) if row else None

    def unsynced(self, limit: int = 200) -> list[Action]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM actions WHERE synced = 0 ORDER BY created_at LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_action(r) for r in rows]

    def mark_synced(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._lock:
            self._conn.executemany("UPDATE actions SET synced = 1 WHERE id = ?", [(i,) for i in ids])
            self._conn.commit()

    def last_batch_id(self) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT batch_id FROM actions WHERE status = 'applied' ORDER BY applied_at DESC LIMIT 1"
            ).fetchone()
        return row["batch_id"] if row else None

    def stats(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM actions GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    # ------------------------------------------------------------- file index
    def index_get(self, path: str) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute("SELECT * FROM file_index WHERE path = ?", (path,)).fetchone()

    def index_put(self, path: str, size: int, mtime: float, sha256: str | None,
                  phash: str | None, simhash: str | None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO file_index (path, size, mtime, sha256, phash, simhash) VALUES (?, ?, ?, ?, ?, ?)",
                (path, size, mtime, sha256, phash, simhash),
            )
            self._conn.commit()

    def index_remove(self, path: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM file_index WHERE path = ?", (path,))
            self._conn.commit()

    def index_rename(self, old: str, new: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE OR REPLACE file_index SET path = ? WHERE path = ?", (new, old))
            self._conn.commit()

    def index_by_sha(self, sha256: str) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute("SELECT * FROM file_index WHERE sha256 = ?", (sha256,)).fetchall()

    def index_with(self, column: str) -> list[sqlite3.Row]:
        assert column in {"phash", "simhash"}
        with self._lock:
            return self._conn.execute(f"SELECT * FROM file_index WHERE {column} IS NOT NULL").fetchall()

    # -------------------------------------------------------------- optimized
    def is_optimized(self, path: str, size: int, mtime: float) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT * FROM optimized WHERE path = ?", (path,)).fetchone()
        return bool(row and row["size"] == size and abs(row["mtime"] - mtime) < 1)

    def mark_optimized(self, path: str, size: int, mtime: float) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO optimized VALUES (?, ?, ?)", (path, size, mtime))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _row_to_action(row: sqlite3.Row) -> Action:
    data: dict[str, Any] = dict(row)
    data.pop("synced", None)
    data["tags"] = json.loads(data.get("tags") or "[]")
    data["details"] = json.loads(data.get("details") or "{}")
    return Action(**data)
