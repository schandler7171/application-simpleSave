"""Paths, constants, and user preferences."""
from __future__ import annotations

import json
import sys
from pathlib import Path


APP_NAME = "simpleSave"


def resource_path(*parts: str) -> Path:
    """Path to a bundled, read-only resource (e.g. the sample snippet CSVs),
    resolved correctly both when running from source and when frozen into
    a PyInstaller .app (where such files live under sys._MEIPASS instead of
    next to this file).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent  # project root
    return base.joinpath(*parts)


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
    # Per-theme text color overrides set from Preferences. Empty string
    # means "use that theme's default" (see simplesave.theme).
    "text_color_dark": "",
    "text_color_light": "",
    # Remembers the last filename used for a CSV bulk export so the save
    # dialog can default to it next time.
    "last_csv_export_name": "simplesave-export.csv",
    # Flips to True after the bundled sample snippets (Bash, HTML, JS, CSS,
    # Python) are auto-imported once on first launch. Left False forever
    # skips re-seeding, even if the user deletes them afterward.
    "seeded_sample_snippets": False,
    # Whether the editor's Folder/Language/Tags row is expanded. Collapsed
    # by default so a snippet reads as just a title + code.
    "details_expanded": False,
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
