"""SQLite layer: connection, schema, and repository CRUD."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

from simplesave.config import DB_PATH
from simplesave.models import Folder, Snippet, Tag


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS folders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES folders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS snippets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    language    TEXT,
    folder_id   INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    color       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snippet_tags (
    snippet_id  INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (snippet_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_snippets_folder ON snippets(folder_id);
CREATE INDEX IF NOT EXISTS idx_snippets_updated ON snippets(updated_at DESC);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Database:
    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        # executescript implicitly commits any active transaction, so run it
        # outside our explicit BEGIN/COMMIT wrapper.
        self._conn.executescript(SCHEMA)
        cur = self._conn.execute("SELECT COUNT(*) FROM schema_version;")
        if cur.fetchone()[0] == 0:
            with self.tx() as cur2:
                cur2.execute("INSERT INTO schema_version(version) VALUES (1);")

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN;")
            yield cur
            cur.execute("COMMIT;")
        except Exception:
            cur.execute("ROLLBACK;")
            raise

    def close(self) -> None:
        self._conn.close()

    # ---------- folders ----------

    def list_folders(self) -> list[Folder]:
        rows = self._conn.execute(
            "SELECT id, name, parent_id FROM folders ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [Folder(id=r["id"], name=r["name"], parent_id=r["parent_id"]) for r in rows]

    def create_folder(self, name: str, parent_id: Optional[int] = None) -> Folder:
        with self.tx() as cur:
            cur.execute(
                "INSERT INTO folders(name, parent_id) VALUES (?, ?);",
                (name.strip(), parent_id),
            )
            fid = cur.lastrowid
        return Folder(id=fid, name=name.strip(), parent_id=parent_id)

    def rename_folder(self, folder_id: int, name: str) -> None:
        with self.tx() as cur:
            cur.execute("UPDATE folders SET name=? WHERE id=?;", (name.strip(), folder_id))

    def delete_folder(self, folder_id: int) -> None:
        with self.tx() as cur:
            cur.execute("DELETE FROM folders WHERE id=?;", (folder_id,))

    def get_or_create_folder_path(self, path: str) -> Optional[int]:
        """Resolve a slash-delimited path like 'A/B/C' to the deepest folder id, creating as needed."""
        path = (path or "").strip().strip("/")
        if not path:
            return None
        parent: Optional[int] = None
        for part in path.split("/"):
            if not part:
                continue
            row = self._conn.execute(
                "SELECT id FROM folders WHERE name=? AND (parent_id IS ? OR parent_id=?);",
                (part, parent, parent),
            ).fetchone()
            if row:
                parent = row["id"]
            else:
                parent = self.create_folder(part, parent).id
        return parent

    def folder_full_path(self, folder_id: Optional[int]) -> str:
        if folder_id is None:
            return ""
        parts: list[str] = []
        current: Optional[int] = folder_id
        seen: set[int] = set()
        while current is not None and current not in seen:
            seen.add(current)
            row = self._conn.execute(
                "SELECT name, parent_id FROM folders WHERE id=?;", (current,)
            ).fetchone()
            if not row:
                break
            parts.append(row["name"])
            current = row["parent_id"]
        return "/".join(reversed(parts))

    # ---------- tags ----------

    def list_tags(self) -> list[Tag]:
        rows = self._conn.execute(
            "SELECT id, name, color FROM tags ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [Tag(id=r["id"], name=r["name"], color=r["color"]) for r in rows]

    def get_tag_by_name(self, name: str) -> Optional[Tag]:
        row = self._conn.execute(
            "SELECT id, name, color FROM tags WHERE name=?;", (name,)
        ).fetchone()
        if not row:
            return None
        return Tag(id=row["id"], name=row["name"], color=row["color"])

    def create_tag(self, name: str, color: str) -> Tag:
        with self.tx() as cur:
            cur.execute("INSERT INTO tags(name, color) VALUES (?, ?);", (name.strip(), color))
            tid = cur.lastrowid
        return Tag(id=tid, name=name.strip(), color=color)

    def upsert_tag(self, name: str, color: str = "#0f62fe") -> Tag:
        existing = self.get_tag_by_name(name)
        if existing:
            return existing
        return self.create_tag(name, color)

    def update_tag(self, tag_id: int, name: str, color: str) -> None:
        with self.tx() as cur:
            cur.execute("UPDATE tags SET name=?, color=? WHERE id=?;", (name.strip(), color, tag_id))

    def delete_tag(self, tag_id: int) -> None:
        with self.tx() as cur:
            cur.execute("DELETE FROM tags WHERE id=?;", (tag_id,))

    # ---------- snippets ----------

    def _row_to_snippet(self, row: sqlite3.Row) -> Snippet:
        s = Snippet(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            language=row["language"],
            folder_id=row["folder_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        s.tags = self._tags_for(row["id"])
        return s

    def _tags_for(self, snippet_id: int) -> list[Tag]:
        rows = self._conn.execute(
            """SELECT t.id, t.name, t.color FROM tags t
               JOIN snippet_tags st ON st.tag_id = t.id
               WHERE st.snippet_id = ?
               ORDER BY t.name COLLATE NOCASE;""",
            (snippet_id,),
        ).fetchall()
        return [Tag(id=r["id"], name=r["name"], color=r["color"]) for r in rows]

    def list_snippets(
        self,
        folder_id: Optional[int] = None,
        tag_ids: Optional[Iterable[int]] = None,
        search: Optional[str] = None,
    ) -> list[Snippet]:
        params: list = []
        where: list[str] = []

        if folder_id is not None:
            where.append("s.folder_id = ?")
            params.append(folder_id)

        if search:
            where.append("(s.title LIKE ? OR s.body LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])

        tag_ids = list(tag_ids or [])
        if tag_ids:
            placeholders = ",".join("?" * len(tag_ids))
            where.append(
                f"s.id IN (SELECT snippet_id FROM snippet_tags WHERE tag_id IN ({placeholders}) "
                f"GROUP BY snippet_id HAVING COUNT(DISTINCT tag_id) = ?)"
            )
            params.extend(tag_ids)
            params.append(len(tag_ids))

        sql = "SELECT s.* FROM snippets s"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.updated_at DESC;"

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_snippet(r) for r in rows]

    def get_snippet(self, snippet_id: int) -> Optional[Snippet]:
        row = self._conn.execute("SELECT * FROM snippets WHERE id=?;", (snippet_id,)).fetchone()
        if not row:
            return None
        return self._row_to_snippet(row)

    def create_snippet(
        self,
        title: str,
        body: str = "",
        folder_id: Optional[int] = None,
        language: Optional[str] = None,
        tag_ids: Optional[Iterable[int]] = None,
    ) -> Snippet:
        now = _now_iso()
        with self.tx() as cur:
            cur.execute(
                """INSERT INTO snippets(title, body, language, folder_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                (title, body, language, folder_id, now, now),
            )
            sid = cur.lastrowid
            for tid in (tag_ids or []):
                cur.execute(
                    "INSERT OR IGNORE INTO snippet_tags(snippet_id, tag_id) VALUES (?, ?);",
                    (sid, tid),
                )
        return self.get_snippet(sid)  # type: ignore[return-value]

    def update_snippet(
        self,
        snippet_id: int,
        *,
        title: Optional[str] = None,
        body: Optional[str] = None,
        folder_id: Optional[int] = ...,  # type: ignore[assignment]
        language: Optional[str] = ...,   # type: ignore[assignment]
    ) -> None:
        sets: list[str] = []
        params: list = []
        if title is not None:
            sets.append("title=?")
            params.append(title)
        if body is not None:
            sets.append("body=?")
            params.append(body)
        if folder_id is not ...:
            sets.append("folder_id=?")
            params.append(folder_id)
        if language is not ...:
            sets.append("language=?")
            params.append(language)
        if not sets:
            return
        sets.append("updated_at=?")
        params.append(_now_iso())
        params.append(snippet_id)
        with self.tx() as cur:
            cur.execute(f"UPDATE snippets SET {', '.join(sets)} WHERE id=?;", params)

    def set_snippet_tags(self, snippet_id: int, tag_ids: Iterable[int]) -> None:
        with self.tx() as cur:
            cur.execute("DELETE FROM snippet_tags WHERE snippet_id=?;", (snippet_id,))
            for tid in tag_ids:
                cur.execute(
                    "INSERT OR IGNORE INTO snippet_tags(snippet_id, tag_id) VALUES (?, ?);",
                    (snippet_id, tid),
                )

    def delete_snippet(self, snippet_id: int) -> None:
        with self.tx() as cur:
            cur.execute("DELETE FROM snippets WHERE id=?;", (snippet_id,))
