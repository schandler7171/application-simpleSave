"""Carbon-inspired theme tokens and QSS stylesheets."""
from __future__ import annotations


DARK = {
    "background":        "#161616",
    "layer_01":          "#262626",
    "layer_02":          "#393939",
    "layer_03":          "#525252",
    "border_subtle":     "#393939",
    "border_strong":     "#6f6f6f",
    "text_primary":      "#f4f4f4",
    "text_secondary":    "#c6c6c6",
    "text_placeholder":  "#6f6f6f",
    "text_on_color":     "#ffffff",
    "interactive":       "#0f62fe",
    "interactive_hover": "#0353e9",
    "focus":             "#ffffff",
    "danger":            "#fa4d56",
    "success":           "#42be65",
}

LIGHT = {
    "background":        "#ffffff",
    "layer_01":          "#f4f4f4",
    "layer_02":          "#ffffff",
    "layer_03":          "#e0e0e0",
    "border_subtle":     "#e0e0e0",
    "border_strong":     "#8d8d8d",
    "text_primary":      "#161616",
    "text_secondary":    "#525252",
    "text_placeholder":  "#a8a8a8",
    "text_on_color":     "#ffffff",
    "interactive":       "#0f62fe",
    "interactive_hover": "#0353e9",
    "focus":             "#0f62fe",
    "danger":            "#da1e28",
    "success":           "#24a148",
}


SPACING = {"02": 4, "03": 8, "04": 12, "05": 16, "06": 24, "07": 32}


_QSS_TEMPLATE = """
* {{
    font-family: "Work Sans", "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: {text_primary};
}}

QMainWindow, QWidget {{
    background-color: {background};
    color: {text_primary};
}}

#TopBar {{
    background-color: {layer_01};
    border-bottom: 1px solid {border_subtle};
}}

#Sidebar {{
    background-color: {layer_01};
    border-right: 1px solid {border_subtle};
}}

#EditorPane {{
    background-color: {background};
}}

QLabel {{
    color: {text_primary};
    background: transparent;
}}

QLabel[role="secondary"] {{
    color: {text_secondary};
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background-color: {layer_02};
    color: {text_primary};
    border: 1px solid {border_subtle};
    border-radius: 0;
    padding: 6px 8px;
    selection-background-color: {interactive};
    selection-color: {text_on_color};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {focus};
}}

QPlainTextEdit#Editor, QPlainTextEdit#editor {{
    font-family: "Space Mono", "JetBrains Mono", "Menlo", "Consolas", monospace;
    font-size: 13px;
    border: none;
    background-color: {background};
    padding: 16px;
}}

QLineEdit#TitleInput {{
    font-family: "Space Mono", "Menlo", "Consolas", monospace;
    font-size: 16px;
    font-weight: 600;
    background: transparent;
    border: none;
    padding: 8px 16px;
}}

QLabel[role="heading"] {{
    font-family: "Space Mono", "Menlo", "Consolas", monospace;
    font-size: 14px;
    font-weight: 700;
    color: {text_primary};
}}

QPushButton {{
    background-color: {layer_02};
    color: {text_primary};
    border: 1px solid {border_subtle};
    padding: 6px 12px;
    border-radius: 0;
}}

QPushButton:hover {{
    background-color: {layer_03};
}}

QPushButton:pressed {{
    background-color: {interactive_hover};
    color: {text_on_color};
}}

QPushButton[variant="primary"] {{
    background-color: {interactive};
    color: {text_on_color};
    border: 1px solid {interactive};
}}

QPushButton[variant="primary"]:hover {{
    background-color: {interactive_hover};
    border: 1px solid {interactive_hover};
}}

QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {text_primary};
}}

QPushButton[variant="ghost"]:hover {{
    background-color: {layer_02};
}}

QPushButton[variant="danger"] {{
    background-color: transparent;
    color: {danger};
    border: 1px solid transparent;
}}

QPushButton[variant="danger"]:hover {{
    background-color: {layer_02};
}}

QListWidget, QTreeWidget {{
    background-color: {layer_01};
    border: none;
    outline: none;
}}

QListWidget::item, QTreeWidget::item {{
    padding: 10px 12px;
    border-bottom: 1px solid {border_subtle};
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {layer_03};
    color: {text_primary};
}}

QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {layer_02};
}}

QScrollBar:vertical {{
    background: {layer_01};
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {layer_03};
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {border_strong};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QSplitter::handle {{
    background-color: {border_subtle};
    width: 1px;
}}

QMenu {{
    background-color: {layer_02};
    color: {text_primary};
    border: 1px solid {border_subtle};
}}

QMenu::item:selected {{
    background-color: {interactive};
    color: {text_on_color};
}}

QToolTip {{
    background-color: {layer_03};
    color: {text_primary};
    border: 1px solid {border_subtle};
    padding: 4px 6px;
}}

QStatusBar {{
    background-color: {layer_01};
    color: {text_secondary};
    border-top: 1px solid {border_subtle};
}}
"""


def stylesheet(theme: str) -> str:
    tokens = DARK if theme == "dark" else LIGHT
    return _QSS_TEMPLATE.format(**tokens)


def tokens(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


# Aliases used by other modules
build_stylesheet = stylesheet
tokens_for = tokens
