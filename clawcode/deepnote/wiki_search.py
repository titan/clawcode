from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class WikiSearchIndex:
    """SQLite FTS5 index with optional semantic backend placeholders."""

    def __init__(self, index_dir: Path, vector_store: str = "none") -> None:
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "deepnote_fts.db"
        self.vector_store = (vector_store or "none").lower().strip()
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self._conn = conn
            return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _init_db(self) -> None:
        conn = self._connect()
        with self._lock:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deepnote_docs (
                    path TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS deepnote_fts
                USING fts5(path UNINDEXED, title, content, tokenize='unicode61')
                """
            )
            conn.commit()

    def upsert_document(self, path: str, title: str, content: str, tags: list[str] | None = None) -> None:
        tags = tags or []
        ts = int(time.time())
        conn = self._connect()
        with self._lock:
            conn.execute(
                """
                INSERT INTO deepnote_docs(path, title, content, tags_json, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (path, title, content, json.dumps(tags, ensure_ascii=False), ts),
            )
            conn.execute("DELETE FROM deepnote_fts WHERE path = ?", (path,))
            conn.execute(
                "INSERT INTO deepnote_fts(path, title, content) VALUES(?, ?, ?)",
                (path, title, content),
            )
            conn.commit()

    def keyword_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        q = " ".join((query or "").split())
        if not q:
            return []
        conn = self._connect()
        with self._lock:
            rows = conn.execute(
                """
                SELECT d.path, d.title, d.tags_json, d.updated_at,
                       snippet(deepnote_fts, 2, '>>>', '<<<', '...', 20) AS snippet,
                       bm25(deepnote_fts) AS rank
                FROM deepnote_fts
                JOIN deepnote_docs d ON d.path = deepnote_fts.path
                WHERE deepnote_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (q, max(1, limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def semantic_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        # Optional vector search hook. Keep graceful fallback when libs are absent.
        if self.vector_store in {"chroma", "faiss"}:
            # Placeholder behavior: fallback to keyword until vector adapter is configured.
            return self.keyword_search(query, limit=limit)
        return self.keyword_search(query, limit=limit)

