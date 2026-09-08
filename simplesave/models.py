"""Dataclasses for snippets, tags, folders."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Folder:
    id: Optional[int]
    name: str
    parent_id: Optional[int] = None


@dataclass
class Tag:
    id: Optional[int]
    name: str
    color: str  # '#rrggbb'


@dataclass
class Snippet:
    id: Optional[int]
    title: str
    body: str = ""
    language: Optional[str] = None
    folder_id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    tags: list[Tag] = field(default_factory=list)
