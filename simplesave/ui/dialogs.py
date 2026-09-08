"""Dialogs: new tag (name + color), preferences, simple confirm."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from simplesave import theme as theme_module


# Carbon-derived palette. Distinct enough at a glance that two adjacent tags
# never look the same. Cycles when exhausted.
TAG_PALETTE: list[str] = [
    "#0f62fe",  # blue 60
    "#42be65",  # green 50
    "#fa4d56",  # red 50
    "#f1c21b",  # yellow 30
    "#a56eff",  # purple 50
    "#08bdba",  # teal 40
    "#ff7eb6",  # magenta 40
    "#ff832b",  # orange 40
    "#33b1ff",  # cyan 40
    "#d4bbff",  # purple 30
    "#007d79",  # teal 70
    "#9f1853",  # magenta 70
    "#6929c4",  # purple 70
    "#1192e8",  # cyan 60
    "#005d5d",  # teal 80
]


def palette_color(index: int) -> str:
    """Return the palette color at `index`, cycling if out of range."""
    if not TAG_PALETTE:
        return "#0f62fe"
    return TAG_PALETTE[index % len(TAG_PALETTE)]


class NewTagDialog(QDialog):
    """Prompt for tag name + color.

    The color defaults to the next slot in TAG_PALETTE (based on `palette_index`
    passed in from the caller, usually the current tag count) so each new tag
    starts with a different color. User can still override via the picker.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial_color: str | None = None,
        palette_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New tag")
        self.setMinimumWidth(360)
        start = initial_color or palette_color(palette_index)
        self._color = QColor(start)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Tag name"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. wordpress")
        layout.addWidget(self._name_edit)

        # Color row: swatch + Pick button
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        color_row.addWidget(QLabel("Color"))
        color_row.addStretch(1)
        self._color_swatch = QLabel()
        self._color_swatch.setFixedSize(28, 28)
        self._update_swatch()
        color_row.addWidget(self._color_swatch)
        pick_btn = QPushButton("Pick…")
        pick_btn.setProperty("variant", "secondary")
        pick_btn.clicked.connect(self._pick_color)
        color_row.addWidget(pick_btn)
        layout.addLayout(color_row)

        # Quick palette: tap a swatch to select that color without opening
        # the full color dialog.
        palette_row = QHBoxLayout()
        palette_row.setSpacing(4)
        for hex_color in TAG_PALETTE[:10]:
            sw = QPushButton()
            sw.setFixedSize(22, 22)
            sw.setStyleSheet(
                f"background: {hex_color}; border: 1px solid #6f6f6f;"
                " border-radius: 4px;"
            )
            sw.setCursor(Qt.PointingHandCursor)
            sw.clicked.connect(lambda _=False, c=hex_color: self._set_color(c))
            palette_row.addWidget(sw)
        palette_row.addStretch(1)
        layout.addLayout(palette_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setProperty("variant", "ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setProperty("variant", "primary")
        save.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _update_swatch(self) -> None:
        self._color_swatch.setStyleSheet(
            f"background: {self._color.name()}; border: 1px solid #6f6f6f;"
        )

    def _set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self._update_swatch()

    def _pick_color(self) -> None:
        dlg = QColorDialog(self._color, self)
        dlg.setOption(QColorDialog.DontUseNativeDialog, False)
        if dlg.exec() == QDialog.Accepted:
            self._color = dlg.currentColor()
            self._update_swatch()

    def get_result(self) -> tuple[str, str]:
        return self._name_edit.text().strip(), self._color.name()


class PreferencesDialog(QDialog):
    """Font size + per-theme text color, applied live.

    There's no OK/Cancel: every change writes straight into the shared
    `prefs` dict and fires `on_change` immediately so the window behind
    this dialog updates as you pick, same spirit as the theme toggle.
    "Done" just closes it.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        prefs: dict,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(400)
        self._prefs = prefs
        self._on_change = on_change

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        heading = QLabel("Appearance")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        font_row.addWidget(QLabel("Font size"))
        font_row.addStretch(1)
        self._font_spin = QSpinBox()
        self._font_spin.setRange(9, 28)
        self._font_spin.setSuffix(" px")
        self._font_spin.setValue(int(prefs.get("font_size", 13)))
        self._font_spin.valueChanged.connect(self._on_font_size_changed)
        font_row.addWidget(self._font_spin)
        layout.addLayout(font_row)

        layout.addWidget(self._build_color_row(
            "Text color — dark theme", "text_color_dark", theme_module.DARK["text_primary"],
        ))
        layout.addWidget(self._build_color_row(
            "Text color — light theme", "text_color_light", theme_module.LIGHT["text_primary"],
        ))

        hint = QLabel(
            "Text color is picked per theme so it always stays readable\n"
            "against that theme's background."
        )
        hint.setProperty("role", "secondary")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        done = QPushButton("Done")
        done.setProperty("variant", "primary")
        done.clicked.connect(self.accept)
        btn_row.addWidget(done)
        layout.addLayout(btn_row)

    def _build_color_row(self, label: str, pref_key: str, default_hex: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(QLabel(label))
        h.addStretch(1)

        swatch = QLabel()
        swatch.setFixedSize(24, 24)

        def current_hex() -> str:
            return self._prefs.get(pref_key) or default_hex

        def refresh_swatch() -> None:
            swatch.setStyleSheet(f"background: {current_hex()}; border: 1px solid #6f6f6f;")

        refresh_swatch()
        h.addWidget(swatch)

        pick = QPushButton("Pick…")
        pick.setProperty("variant", "secondary")

        def do_pick() -> None:
            dlg = QColorDialog(QColor(current_hex()), self)
            if dlg.exec() == QDialog.Accepted:
                self._prefs[pref_key] = dlg.currentColor().name()
                refresh_swatch()
                self._notify()

        pick.clicked.connect(do_pick)
        h.addWidget(pick)

        reset = QPushButton("Reset")
        reset.setProperty("variant", "ghost")

        def do_reset() -> None:
            self._prefs[pref_key] = ""
            refresh_swatch()
            self._notify()

        reset.clicked.connect(do_reset)
        h.addWidget(reset)

        return row

    def _on_font_size_changed(self, value: int) -> None:
        self._prefs["font_size"] = int(value)
        self._notify()

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()
