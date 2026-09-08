"""Paths, constants, and user preferences."""
from __future__ import annotations

import json
import sys
from pathlib import Path


APP_NAME = "simpleSave"


def app_data_dir() -> Path:
    """Per-OS app data directory. Created if missing."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        import os
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DB_PATH = app_data_dir() / "simplesave.db"
PREFS_PATH = app_data_dir() / "prefs.json"


DEFAULT_PREFS = {
    "theme": "dark",            # 'dark' | 'light'
    "font_size": 13,
    "editor_font": "Menlo",     # falls back gracefully if missing
    "autosave_ms": 500,
    "default_export_dir": str(Path.home() / "Documents" / "simpleSave-exports"),
    "window_geometry": "",
    "active_tag_ids": [],
    "active_folder_id": None,
}


def load_prefs() -> dict:
    if not PREFS_PATH.exists():
        return dict(DEFAULT_PREFS)
    try:
        with PREFS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_PREFS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_PREFS)


def save_prefs(prefs: dict) -> None:
    try:
        with PREFS_PATH.open("w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass
