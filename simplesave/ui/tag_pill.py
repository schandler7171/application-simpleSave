"""Colored tag pill widget."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from simplesave.models import Tag


def _text_color_for(bg_hex: str) -> str:
    """Return '#ffffff' or '#161616' depending on luminance of bg."""
    try:
        c = QColor(bg_hex)
        # WCAG-ish relative luminance
        r, g, b = c.red() / 255, c.green() / 255, c.blue() / 255
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "#161616" if lum > 0.55 else "#ffffff"
    except Exception:
        return "#ffffff"


class TagPill(QWidget):
    """A colored pill displaying a tag.

    Signals:
      clicked(int): emitted with tag_id when the pill body is clicked.
      removed(int): emitted with tag_id when the × button is clicked
                    (only present when removable=True).
    """

    clicked = Signal(int)
    removed = Signal(int)

    def __init__(
        self,
        tag: Tag,
        *,
        removable: bool = False,
        active: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tag = tag
        self._removable = removable
        self._active = active
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        text_color = _text_color_for(self._tag.color)
        border = "2px solid #ffffff" if self._active else "2px solid transparent"

        self._label = QLabel(f"  {self._tag.name}  ")
        self._label.setStyleSheet(
            f"""
            QLabel {{
                background: {self._tag.color};
                color: {text_color};
                border-radius: 9px;
                padding: 1px 8px;
                font-family: "Space Mono", "Menlo", "Consolas", monospace;
                font-size: 12px;
                font-weight: 500;
                border: {border};
            }}
            """
        )
        self._label.setCursor(Qt.PointingHandCursor)
        self._label.mousePressEvent = self._on_click  # type: ignore[assignment]
        layout.addWidget(self._label)

        if self._removable:
            btn = QPushButton("×")
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {self._tag.color};
                    color: {text_color};
                    border: none;
                    border-top-right-radius: 9px;
                    border-bottom-right-radius: 9px;
                    font-family: "Space Mono", "Menlo", "Consolas", monospace;
                    font-weight: bold;
                    margin-left: -4px;
                }}
                QPushButton:hover {{
                    background: #fa4d56;
                    color: #ffffff;
                }}
                """
            )
            btn.clicked.connect(lambda: self.removed.emit(self._tag.id or 0))
            layout.addWidget(btn)

    def _on_click(self, _event) -> None:
        if self._tag.id is not None:
            self.clicked.emit(self._tag.id)

    @property
    def tag(self) -> Tag:
        return self._tag
