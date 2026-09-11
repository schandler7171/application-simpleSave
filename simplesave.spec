# PyInstaller spec for simpleSave.
# Build with:  pyinstaller simplesave.spec --noconfirm --clean
#
# Output:      dist/simpleSave.app
#
# Run from build_mac.sh — don't run this directly unless you know what you want.
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

ROOT = Path(SPECPATH)
ICON_ICNS = ROOT / "assets" / "icon.icns"

# Pygments discovers lexers/styles at runtime via pkgutil, which PyInstaller's
# static import scan can't see. Pull in the ones we actually offer in the
# editor's language dropdown (simplesave/ui/highlighter.py) explicitly so a
# built .app doesn't silently lose syntax highlighting.
hidden_pygments = collect_submodules("pygments.lexers") + collect_submodules("pygments.styles")

a = Analysis(
    ["simplesave/__main__.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "sample-snippets"), "sample-snippets")],
    hiddenimports=[
        # PySide6 picks these up automatically in 6.6+, but list them
        # defensively in case PyInstaller's hook misses something.
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        *hidden_pygments,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Don't ship Qt modules we don't use — keeps the bundle smaller.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="simpleSave",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                 # windowed
    disable_windowed_traceback=False,
    target_arch="universal2",      # builds a single binary that runs on Intel and Apple Silicon
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="simpleSave",
)

app = BUNDLE(
    coll,
    name="simpleSave.app",
    icon=str(ICON_ICNS) if ICON_ICNS.exists() else None,
    bundle_identifier="com.scottchandler.simplesave",
    info_plist={
        "CFBundleName": "simpleSave",
        "CFBundleDisplayName": "simpleSave",
        "CFBundleShortVersionString": "0.1.4",
        "CFBundleVersion": "0.1.4",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSHumanReadableCopyright": "Copyright (c) 2026 Scott Chandler.",
        "LSApplicationCategoryType": "public.app-category.productivity",
        # Avoid spurious mic / camera / files permission prompts: we use none.
    },
)
