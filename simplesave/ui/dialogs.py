"""Dialogs: new tag (name + color), import preview, simple confirm."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
