# simpleSave

*Developed with Claude assistance.*

A 100% local snippet manager. No accounts, no cloud, no telemetry.

Python + PySide6 + SQLite. Carbon-inspired dark/light theme. Tags with custom colors, folders, search, and round-trip import/export for Markdown, plain text, and CSV.

## Run it

```bash
./run.sh
```

That's it. The script creates a virtualenv, installs `PySide6` and `pyperclip`, and launches the app via `python -m simplesave`.

If you'd rather drive it manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m simplesave
```

## Where your data lives

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/simpleSave/simplesave.db` |
| Windows | `%APPDATA%\simpleSave\simplesave.db` |
| Linux | `~/.local/share/simpleSave/simplesave.db` |

Prefs (theme, last-used folder/tags, window geometry) live next to the DB in `prefs.json`. Both files are plain SQLite + plain JSON — back them up or sync them yourself if you want.

## Features in v1

- Snippets with title, body, folder, multi-tag, language.
- Syntax color-coding in the editor, driven by a per-snippet Language dropdown
  (Pygments under the hood — see "Syntax highlighting" below).
- Tag pills with custom colors (click pill → filter; click again → unfilter).
- Folder tree (nestable in schema; flat creation in v1 UI).
- Dark and light themes — toggle in toolbar or `Ctrl+T`.
- Preferences (toolbar → "Preferences"): font size, and a text color picker
  per theme — applied live, no restart needed.
- Autosave (~500 ms debounce).
- Search across title and body.
- Import: `.md` (with YAML-ish front matter), `.txt`, `.csv`.
- Export: same three formats — CSV and single-snippet exports let you name
  the file; every export reveals itself in Finder when it's done.
- "Template" button: saves a blank CSV in the exact shape bulk import
  expects, so you know what columns to fill in before importing many
  snippets at once.
- Copy snippet body to clipboard.

## Syntax highlighting

Set a snippet's **Language** in the editor's meta row and its body colors
itself accordingly (Python, JavaScript, Bash, SQL, and about a dozen others —
see the dropdown for the full list). Pick "Plain text" to turn it off for
that snippet. The color style follows the app theme (a dark-friendly palette
in dark mode, a light-friendly one in light mode) and updates immediately
when you toggle themes.

## Keyboard shortcuts

| Action | Shortcut |
|---|---|
| New snippet | `Ctrl+N` |
| Focus search | `Ctrl+F` |
| Force save | `Ctrl+S` |
| Toggle theme | `Ctrl+T` |
| Copy snippet | `Ctrl+Shift+C` |

(On macOS, `Ctrl` maps to `⌘` for these.)

## Import / export formats

**Markdown** — round-trips cleanly:

```markdown
---
title: My snippet
folder: Laravel/Helpers
tags: [php, wordpress]
language: php
---

Body goes here.
```

**Plain text** — body only. Filename becomes the title on import.

**CSV** — columns: `id, title, body, folder, tags, language, created_at, updated_at`. Tags joined with `|`.

## Build a Mac `.app` and `.dmg`

```bash
./scripts/build_mac.sh
```

Produces:

- `dist/simpleSave.app` — double-clickable bundle (self-contained: ships its own Python + Qt)
- `dist/simpleSave.dmg` — drag-to-Applications installer

### Prereqs

| What | Why | Install |
|---|---|---|
| macOS 11+ | Build host | — |
| Python 3.11+ | Build runtime | `brew install python@3.12` or python.org installer |
| Xcode Command Line Tools | `iconutil` for `.icns` | `xcode-select --install` |
| `create-dmg` (optional) | Prettier DMG layout | `brew install create-dmg` |

If `create-dmg` isn't installed, the script falls back to `hdiutil` and you still get a working (uglier) DMG.

### Install from the DMG

1. Open `dist/simpleSave.dmg`
2. Drag `simpleSave.app` into the **Applications** shortcut
3. First launch only: right-click the app in Applications → **Open** → **Open** to bypass the Gatekeeper "unidentified developer" warning. After that, double-click like any app.

### Why the warning?

By default the DMG is **ad-hoc signed**, not Developer ID signed. macOS shows the warning once because Apple wants a Developer Program account before it'll trust an app silently.

### Developer ID signing + notarization (removes the warning)

`build_mac.sh` supports a fully signed, notarized build — no code changes, just environment variables:

1. Enroll in the [Apple Developer Program](https://developer.apple.com/programs/) ($99/yr) if you haven't.
2. Create a **Developer ID Application** certificate: Keychain Access → Certificate Assistant → Request a Certificate From a Certificate Authority (save the CSR to disk) → upload it at [Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/certificates/list) → download the issued certificate and double-click it to install it in your login keychain.
3. Find the exact identity string:
   ```bash
   security find-identity -v -p codesigning
   ```
   Look for a line like `"Developer ID Application: Your Name (ABCDE12345)"`.
4. (Optional, for notarization) Generate an app-specific password at [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → App-Specific Passwords, then save it once so you don't retype it every release:
   ```bash
   xcrun notarytool store-credentials "simplesave-notary" \
     --apple-id you@example.com \
     --team-id ABCDE12345 \
     --password the-app-specific-password
   ```
5. Build signed and notarized:
   ```bash
   SIMPLESAVE_SIGN_IDENTITY="Developer ID Application: Your Name (ABCDE12345)" \
   SIMPLESAVE_KEYCHAIN_PROFILE="simplesave-notary" \
   ./scripts/build_mac.sh
   ```
   Leave `SIMPLESAVE_KEYCHAIN_PROFILE` unset to sign without submitting for notarization (still shows a milder Gatekeeper prompt, but the identity is verifiable). Leave both unset for the original ad-hoc build.

The script signs every nested library with the hardened runtime (required for notarization), signs the `.app`, builds the `.dmg`, submits it to Apple, waits for approval, and staples the ticket to both — so a finished run needs no further steps. `entitlements.plist` at the project root carries the two hardened-runtime exceptions PyInstaller apps typically need (dynamic library loading for the bundled Python/Qt runtime); nothing else is granted.

### Build size

Expect ~80–130 MB for the `.app` (mostly the bundled Qt runtime). DMG is ~50–70 MB compressed. This is normal for PySide6 apps.

## Not in v1

- FTS5 search — currently uses simple `LIKE`; plenty fast for thousands of snippets.
- Eyedropper screen color picker — `QColorDialog` gives you a perfectly good wheel + sampler on macOS already.
- Windows `.exe` packaging — same approach, different script. Add when you want it.
- Tests — coming in next phase.

## Project layout

See `SPEC.md` for the full design doc. The shipping code lives in:

```
simplesave/
├── app.py            QApplication bootstrap
├── config.py         paths + prefs
├── db.py             SQLite layer
├── models.py         dataclasses
├── theme.py          Carbon tokens + QSS
├── io_formats.py     md/txt/csv import + export
└── ui/
    ├── main_window.py
    ├── tag_pill.py
    └── dialogs.py

scripts/
└── build_mac.sh      PyInstaller -> .app -> .dmg

assets/
├── icon.png          source icon (1024x1024)
└── icon.icns         generated by build script
```

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and distribute.
