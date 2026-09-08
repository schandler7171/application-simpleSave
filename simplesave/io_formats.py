"""Import + export: markdown (with front matter), plain text, CSV."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from simplesave.db import Database
from simplesave.models import Snippet


@dataclass
class ImportResult:
    created: int = 0
    skipped: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


# ---------- Markdown ----------

_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "snippet"


def _parse_front_matter(text: str) -> tuple[dict, str]:
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    head, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in head.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            meta[k] = [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]
        else:
            meta[k] = v.strip('"').strip("'")
    return meta, body.lstrip("\n")


def snippet_to_markdown(db: Database, s: Snippet) -> str:
    folder_path = db.folder_full_path(s.folder_id)
    tag_names = [t.name for t in s.tags]
    tags_str = "[" + ", ".join(tag_names) + "]"
    lines = [
        "---",
        f"title: {s.title}",
        f"folder: {folder_path}",
        f"tags: {tags_str}",
        f"created_at: {s.created_at}",
        f"updated_at: {s.updated_at}",
    ]
    if s.language:
        lines.append(f"language: {s.language}")
    lines.append("---")
    lines.append("")
    lines.append(s.body)
    return "\n".join(lines)


def export_markdown(db: Database, snippets: Iterable[Snippet], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for s in snippets:
        folder_path = db.folder_full_path(s.folder_id)
        target_dir = out_dir / folder_path if folder_path else out_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{_slug(s.title)}.md"
        path.write_text(snippet_to_markdown(db, s), encoding="utf-8")
        count += 1
    return count


def import_markdown(db: Database, paths: Iterable[Path]) -> ImportResult:
    result = ImportResult()
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8")
            meta, body = _parse_front_matter(text)
            title = meta.get("title") or Path(p).stem
            folder_path = meta.get("folder") or ""
            folder_id = db.get_or_create_folder_path(folder_path) if folder_path else None
            language = meta.get("language") or None
            tag_names = meta.get("tags") or []
            if isinstance(tag_names, str):
                tag_names = [t.strip() for t in tag_names.split(",") if t.strip()]
            s = db.create_snippet(
                title=title, body=body, folder_id=folder_id, language=language,
            )
            tag_ids: list[int] = []
            for name in tag_names:
                if not name:
                    continue
                tag = db.upsert_tag(name)
                if tag.id is not None:
                    tag_ids.append(tag.id)
            if s.id is not None:
                db.set_snippet_tags(s.id, tag_ids)
            result.created += 1
        except Exception as e:
            result.errors.append(f"{p}: {e}")
            result.skipped += 1
    return result


# ---------- Plain text ----------

def export_plaintext(db: Database, snippets: Iterable[Snippet], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for s in snippets:
        path = out_dir / f"{_slug(s.title)}.txt"
        path.write_text(s.body, encoding="utf-8")
        count += 1
    return count


def import_plaintext(db: Database, paths: Iterable[Path]) -> ImportResult:
    result = ImportResult()
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8")
            title = Path(p).stem
            db.create_snippet(title=title, body=text)
            result.created += 1
        except Exception as e:
            result.errors.append(f"{p}: {e}")
            result.skipped += 1
    return result


# ---------- CSV ----------

CSV_COLUMNS = ["id", "title", "body", "folder", "tags", "language", "created_at", "updated_at"]


def export_csv(db: Database, snippets: Iterable[Snippet], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for s in snippets:
            w.writerow({
                "id": s.id or "",
                "title": s.title,
                "body": s.body,
                "folder": db.folder_full_path(s.folder_id),
                "tags": "|".join(t.name for t in s.tags),
                "language": s.language or "",
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            })
            count += 1
    return count


def import_csv(db: Database, path: Path) -> ImportResult:
    result = ImportResult()
    try:
        with Path(path).open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    title = (row.get("title") or "").strip() or "Untitled"
                    body = row.get("body") or ""
                    language = (row.get("language") or "").strip() or None
                    folder_path = (row.get("folder") or "").strip()
                    folder_id = db.get_or_create_folder_path(folder_path) if folder_path else None
                    s = db.create_snippet(
                        title=title, body=body, folder_id=folder_id, language=language,
                    )
                    raw_tags = (row.get("tags") or "").strip()
                    if raw_tags:
                        tag_ids: list[int] = []
                        for name in raw_tags.split("|"):
                            name = name.strip()
                            if not name:
                                continue
                            tag = db.upsert_tag(name)
                            if tag.id is not None:
                                tag_ids.append(tag.id)
                        if s.id is not None:
                            db.set_snippet_tags(s.id, tag_ids)
                    result.created += 1
                except Exception as e:
                    result.errors.append(f"row: {e}")
                    result.skipped += 1
    except Exception as e:
        result.errors.append(f"{path}: {e}")
    return result
