"""QApplication bootstrap."""
from __future__ import annotations

import sys

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication

from simplesave import config, theme
from simplesave.db import Database
from simplesave.seed_data import seed_sample_snippets_if_needed
from simplesave.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    # Force the Fusion style, which Qt draws entirely itself. Native
    # platform styles (macOS's Aqua-based style in particular) only
    # partially honor QPushButton stylesheet rules -- background-color,
    # border-radius and padding get silently ignored or fought with a
    # native bezel drawn underneath, which is why button styling here
    # kept looking "off" no matter what QSS was tried. Fusion fixes that
    # at the source instead of chasing individual button symptoms.
    app.setStyle("Fusion")

    prefs = config.load_prefs()
    active_theme = prefs["theme"]
    app.setStyleSheet(theme.build_stylesheet(
        active_theme,
        font_size=int(prefs.get("font_size", theme.DEFAULT_FONT_SIZE)),
        text_color=prefs.get(f"text_color_{active_theme}") or None,
    ))

    db = Database(config.DB_PATH)
    seed_sample_snippets_if_needed(db, prefs)
    window = MainWindow(db, prefs)

    geom_hex = prefs.get("window_geometry") or ""
    if geom_hex:
        try:
            window.restoreGeometry(QByteArray.fromHex(geom_hex.encode("ascii")))
        except Exception:
            pass

    window.show()
    code = app.exec()
    db.close()
    sys.exit(code)
