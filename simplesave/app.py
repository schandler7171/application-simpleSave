"""QApplication bootstrap."""
from __future__ import annotations

import sys

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication

from simplesave import config, theme
from simplesave.db import Database
from simplesave.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)

    prefs = config.load_prefs()
    app.setStyleSheet(theme.build_stylesheet(prefs["theme"]))

    db = Database(config.DB_PATH)
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
