# simpleSave — Spec & Folder Structure

A 100% local desktop snippet manager. Mac-first, Windows-portable. Python + PySide6 + SQLite. Carbon-inspired UI with dark/light toggle, colored tag pills, folders, and md/txt/csv import + export.

---

## 1. Goals & non-goals

**Goals**
- Save text/code snippets fast, find them faster.
- 100% local. No accounts, no cloud, no telemetry.
- Tags (with custom colors), folders, search.
- Dark + light mode toggle (Carbon-inspired).
- Import/export: Markdown, plain text, CSV.
- Single executable per platform (Mac `.app`, Windows `.exe`).

**Non-goals (v1)**
- No sync, no AI features, no plugins.
- No multi-user, no auth.
- No syntax highlighting beyond a monospace font (add in v2 via Pygments).
- No App Store submission yet — local use first.

---

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Familiar, fast to iterate. |
| GUI | PySide6 (Qt 6) | Best fit for Carbon styling, native feel on Mac + Windows, mature. |
| DB | SQLite (via `sqlite3` stdlib) | Zero-config, single file, portable. |
| Migrations | Hand-rolled `schema_version` table | Avoid Alembic overhead for a personal app. |
| Clipboard | `pyperclip` | Cross-platform copy. |
| Color picker | `QColorDialog` + custom eyedropper | Carbon-styled wrapper. |
| Packaging | PyInstaller (Mac + Windows) | Single-file builds. |
| Tests | `pytest` + `pytest-qt` | Light coverage on DB + import/export. |

---

## 3. Folder structure

```
application-simpleSave/
├── SPEC.md                       ← this file
├── README.md                     ← user-facing (write last)
├── pyproject.toml                ← deps + project metadata
├── requirements.txt              ← pinned versions
├── .gitignore
│
├── simplesave/                   ← app package
│   ├── __init__.py
│   ├── __main__.py               ← `python -m simplesave`
│   ├── app.py                    ← QApplication bootstrap, theme load
│   ├── config.py                 ← paths, constants, user prefs file
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py         ← SQLite connection + WAL mode
│   │   ├── schema.sql            ← initial schema
│   │   ├── migrations/           ← future schema bumps
│   │   └── repository.py         ← CRUD: snippets, tags, folders
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── snippet.py            ← dataclass
│   │   ├── tag.py                ← dataclass (name + hex color)
│   │   └── folder.py             ← dataclass (nested via parent_id)
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py        ← QMainWindow, the screenshot layout
│   │   ├── sidebar.py            ← folders tree + tag list
│   │   ├── snippet_list.py       ← left "Text Save Area" list
│   │   ├── editor.py             ← right pane (title, body, tag pills)
│   │   ├── tag_pill.py           ← reusable colored pill widget
│   │   ├── tag_bar.py            ← top tag filter bar from screenshot
│   │   ├── toolbar.py            ← "All other controls and settings"
│   │   ├── color_picker.py       ← QColorDialog wrapper + eyedropper
│   │   ├── eyedropper.py         ← screen color sampler (Qt overlay)
│   │   └── dialogs/
│   │       ├── import_dialog.py
│   │       ├── export_dialog.py
│   │       ├── new_tag_dialog.py
│   │       └── settings_dialog.py
│   │
│   ├── theme/
│   │   ├── __init__.py
│   │   ├── tokens.py             ← Carbon color/spacing/type tokens
│   │   ├── dark.qss              ← Carbon Gray 100 stylesheet
│   │   ├── light.qss             ← Carbon White stylesheet
│   │   └── fonts/                ← IBM Plex Sans + Mono (OFL licensed)
│   │
│   ├── io/
│   │   ├── __init__.py
│   │   ├── markdown.py           ← import + export .md
│   │   ├── plaintext.py          ← import + export .txt
│   │   └── csv_io.py             ← import + export .csv
│   │
│   └── utils/
│       ├── __init__.py
│       ├── search.py             ← SQLite FTS5 helpers
│       └── hotkeys.py            ← global shortcuts
│
├── tests/
│   ├── test_repository.py
│   ├── test_markdown_io.py
│   ├── test_csv_io.py
│   └── test_search.py
│
├── scripts/
│   ├── build_mac.sh              ← PyInstaller → simpleSave.app
│   └── build_windows.bat         ← PyInstaller → simpleSave.exe
│
└── assets/
    ├── icon.icns                 ← Mac icon
    ├── icon.ico                  ← Windows icon
    └── icon.png                  ← source
```

Data lives outside the repo:
- macOS: `~/Library/Application Support/simpleSave/simplesave.db`
- Windows: `%APPDATA%\simpleSave\simplesave.db`

---

## 4. Database schema

SQLite, single file, WAL mode. FTS5 virtual table for search.

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE folders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE snippets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    language    TEXT,                  -- optional: 'python', 'sql', etc.
    folder_id   INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    color       TEXT NOT NULL          -- '#rrggbb'
);

CREATE TABLE snippet_tags (
    snippet_id  INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (snippet_id, tag_id)
);

CREATE VIRTUAL TABLE snippets_fts USING fts5(
    title, body, content='snippets', content_rowid='id'
);

-- triggers keep FTS in sync with snippets
```

---

## 5. UI layout (matches your screenshot)

```
┌─────────────────────────────────────────────────────────────────────┐
│ [Tag1] [Tag2] [Tag3] [Tag4] [Tag5]        [search] [+] [☼/☾] [⚙]  │  ← TagBar + Toolbar
├──────────────────────┬──────────────────────────────────────────────┤
│ Text Save Area       │ Title: ____________________________          │
│                      │ Folder: [▾]  Tags: [pill+] [pill+] [+]       │
│ ┌──────────────────┐ │                                              │
│ │ Snippet 1        │ │ ┌──────────────────────────────────────────┐ │
│ │ Snippet 2        │ │ │                                          │ │
│ │ Snippet 3        │ │ │      Editor (monospace, IBM Plex Mono)   │ │
│ │ ...              │ │ │                                          │ │
│ └──────────────────┘ │ └──────────────────────────────────────────┘ │
│ [Folders ▾]          │ [Copy] [Export] [Delete]   updated_at        │
└──────────────────────┴──────────────────────────────────────────────┘
```

Key behaviors:
- Top tag bar filters the list. Click a pill → filter; click again → unfilter.
- Sidebar / left column shows snippet titles, sorted by updated_at desc.
- Editor autosaves on debounce (~500 ms) — no save button.
- Theme toggle in toolbar persists to prefs file.
- New tag opens `color_picker` dialog with **eyedropper** and **color wheel** (`QColorDialog` extended).

---

## 6. Carbon-inspired theming

Token file at `simplesave/theme/tokens.py`. Two QSS stylesheets generated from tokens.

**Color tokens (subset, Carbon v11)**

| Token | Dark (Gray 100) | Light (White) |
|---|---|---|
| `background` | `#161616` | `#ffffff` |
| `layer-01` | `#262626` | `#f4f4f4` |
| `layer-02` | `#393939` | `#ffffff` |
| `border-subtle` | `#393939` | `#e0e0e0` |
| `text-primary` | `#f4f4f4` | `#161616` |
| `text-secondary` | `#c6c6c6` | `#525252` |
| `text-placeholder` | `#6f6f6f` | `#a8a8a8` |
| `interactive` | `#0f62fe` | `#0f62fe` |
| `focus` | `#ffffff` | `#0f62fe` |
| `danger` | `#fa4d56` | `#da1e28` |
| `support-success` | `#42be65` | `#24a148` |

**Typography**: IBM Plex Sans (UI), IBM Plex Mono (editor). Both OFL licensed — bundle in `theme/fonts/`.

**Spacing scale**: `2, 4, 8, 12, 16, 24, 32, 40, 48` px (Carbon's mini-unit grid).

**Components to style**: buttons (primary/secondary/ghost/danger), text inputs, tag pills, list rows, tree items, dialog chrome, scrollbars.

---

## 7. Tag pills + color picker + eyedropper

- `TagPill` widget: rounded `QFrame` with `name` label and `×` remove button. Background = tag color, text color auto-computed from luminance for contrast.
- `ColorPickerDialog` wraps `QColorDialog` with two extras:
  1. **Color wheel** — Qt's native wheel via `QColorDialog.ShowAlphaChannel` flag is fine; if not big enough, embed a custom `QWidget` that paints an HSV wheel (~80 lines).
  2. **Eyedropper button** — opens a translucent fullscreen `QWidget`, grabs the screen via `QScreen.grabWindow()`, samples pixel under cursor, returns hex.

---

## 8. Import / export formats

**Markdown (round-trip)**

```markdown
---
title: My snippet
folder: Laravel/Helpers
tags: [php, wordpress]
created_at: 2026-05-29T12:00:00
---

Body goes here, free-form markdown.
```

Front matter is YAML-ish but parsed with a small hand-rolled parser to avoid a `pyyaml` dependency. One file per snippet on export; folder = subdirectory.

**Plain text**: body only. Filename = title. Metadata lost; warn on export.

**CSV**: one row per snippet with columns `id, title, body, folder, tags, created_at, updated_at`. Tags joined with `|`. UTF-8, RFC 4180 quoting.

Import flow: file/folder picker → preview table → conflict resolution (skip / overwrite / duplicate) → commit in a single transaction.

---

## 9. Settings (stored in `~/.../simpleSave/prefs.json`)

```json
{
  "theme": "dark",
  "font_size": 13,
  "editor_font": "IBM Plex Mono",
  "autosave_ms": 500,
  "default_export_dir": "~/Documents/simpleSave-exports",
  "window_geometry": "..."
}
```

---

## 10. Build phases

| Phase | Scope | Estimate |
|---|---|---|
| **0. Scaffold** | Folder layout, deps, empty modules, `__main__.py` runs an empty window. | 1 sitting |
| **1. DB + models** | Schema, repository CRUD, tests. | 1 sitting |
| **2. Core UI** | Main window, snippet list, editor, autosave. | 1–2 sittings |
| **3. Tags + folders** | Pills, sidebar, tag bar filter, color picker. | 1–2 sittings |
| **4. Theming** | Tokens, dark.qss, light.qss, toggle, IBM Plex fonts. | 1 sitting |
| **5. Import/export** | Markdown, txt, CSV with preview + conflict dialog. | 1–2 sittings |
| **6. Search** | FTS5 wiring + UI. | 1 sitting |
| **7. Eyedropper + polish** | Screen sampler, keyboard shortcuts, empty states. | 1 sitting |
| **8. Packaging** | PyInstaller scripts for Mac + Windows, app icons. | 1 sitting |

Total: ~2 focused weekends to a daily-driver MVP.

---

## 11. Mac → Windows porting notes

PySide6 is cross-platform by default. Watch-outs:
- Paths: use `pathlib` everywhere; never hardcode `/` or `\`.
- App data dir: use `QStandardPaths.AppDataLocation`, not hand-rolled.
- Fonts: bundle IBM Plex so look is identical on both OSes.
- PyInstaller: separate build per OS (no cross-compile). Use GitHub Actions matrix later if you want CI builds.
- Code-signing: deferred. Local-only means no signing required for personal use; users will get the "unidentified developer" warning on first launch and can right-click → Open.

---

## 12. Open questions for next session

1. Snippet versioning / undo history — yes or skip for v1?
2. Hotkey for global "new snippet from clipboard" — yes or skip?
3. Should folders be nested or flat for v1? (Schema supports nested; UI is simpler if flat.)
4. Add syntax highlighting in v1 via Pygments, or defer?

Answer these when we start phase 0 and I'll lock them into the build plan.
