"""Carbon Design System theme tokens and QSS stylesheets.

Token values are IBM Carbon's actual Gray 100 (dark) and White (light)
theme values -- not approximations -- including the parts people usually
get wrong when they eyeball "Carbon-ish" colors: the accent/link blue
used for TEXT is a lighter blue in dark mode (Blue 40, #78a9ff) than the
blue used for solid button fills (Blue 60, #0f62fe), because a mid blue
that reads fine as a filled button with white text on it does not have
enough contrast to read well as blue TEXT on a near-black background.
Same idea for the danger/error color used as button text. Fill colors
("interactive") stay identical across themes; text/accent colors
("accent_text") do not.
"""
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
    # Solid fills (buttons, selection highlight) -- identical across themes;
    # white text on top of these has strong contrast either way.
    "interactive":       "#0f62fe",
    "interactive_hover": "#0353e9",
    # Text/accent color -- Blue 40, the correct Carbon g100 link color.
    # Using the fill blue here instead (a common mistake) reads as dull
    # and low-contrast against a near-black background.
    "accent_text":       "#78a9ff",
    "accent_text_hover": "#a6c8ff",
    "focus":             "#ffffff",
    # Text-error (Red 40) -- lighter than the icon/fill red so it stays
    # legible as button text on dark surfaces.
    "danger":            "#ff8389",
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
    # Blue 60 is the correct link color against a white/near-white
    # background, i.e. the same blue as the button fill.
    "accent_text":       "#0f62fe",
    "accent_text_hover": "#0043ce",
    "focus":             "#0f62fe",
    "danger":            "#da1e28",
    "success":           "#24a148",
}


SPACING = {"02": 4, "03": 8, "04": 12, "05": 16, "06": 24, "07": 32}

DEFAULT_FONT_SIZE = 13


_QSS_TEMPLATE = """
* {{
    font-family: "Work Sans", "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: {font_size}px;
    color: {text_primary};
}}

QMainWindow, QWidget {{
    background-color: {background};
    color: {text_primary};
}}

/* Panels sit one step up from the page background, giving the app real
   depth instead of one flat, undifferentiated slab of color -- this is
   the core Carbon "layering" idea. Object names below must match
   setObjectName(...) in main_window.py exactly (Qt selectors are
   case-sensitive). */
#tagBar {{
    background-color: {layer_01};
    border-bottom: 1px solid {border_subtle};
}}

#sidebar {{
    background-color: {layer_01};
}}

#listToolbar {{
    background-color: {layer_01};
    border-bottom: 1px solid {border_subtle};
}}

#editorPane {{
    background-color: {background};
    border-left: 1px solid {border_subtle};
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
    border-radius: 10px;
    padding: 6px 8px;
    selection-background-color: {interactive};
    selection-color: {text_on_color};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {focus};
}}

QPlainTextEdit#Editor, QPlainTextEdit#editor {{
    font-family: "Space Mono", "JetBrains Mono", "Menlo", "Consolas", monospace;
    font-size: {font_size}px;
    border: none;
    background-color: {background};
    padding: 16px;
}}

QLineEdit#TitleInput {{
    font-family: "Space Mono", "Menlo", "Consolas", monospace;
    font-size: {title_font_size}px;
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
    border-radius: 10px;
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

/* The "+ Add New Snippet" bar spanning the top row of the snippet table --
   styled as an obvious control (accent left edge, accent text), not
   another data row. */
QPushButton[variant="add-row"] {{
    background-color: {layer_02};
    border: none;
    border-left: 3px solid {accent_text};
    border-bottom: 1px solid {border_subtle};
    color: {accent_text};
    font-weight: 600;
    text-align: left;
    padding-left: 16px;
    border-radius: 10px;
}}

QPushButton[variant="add-row"]:hover {{
    background-color: {layer_03};
}}

/* The per-row copy control: a plain icon with no visible button chrome
   at rest -- like the copy affordance on most code-snippet websites,
   not a bordered "Copy" pill. A soft rounded highlight on hover is the
   only feedback until it's clicked. */
QPushButton[variant="icon-ghost"] {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0;
}}

QPushButton[variant="icon-ghost"]:hover {{
    background-color: {layer_03};
}}

QPushButton[variant="icon-ghost"]:pressed {{
    background-color: {border_strong};
}}

QListWidget, QTreeWidget, QTableWidget {{
    background-color: {layer_01};
    border: none;
    outline: none;
    gridline-color: {border_subtle};
}}

QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: 12px 14px;
    border-bottom: 1px solid {border_subtle};
}}

QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background-color: {layer_03};
    color: {text_primary};
}}

QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover {{
    background-color: {layer_02};
}}

QHeaderView::section {{
    background-color: {layer_02};
    color: {text_secondary};
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid {border_subtle};
    border-right: 1px solid {border_subtle};
}}

QHeaderView::section:hover {{
    background-color: {layer_03};
    color: {text_primary};
}}

QTableWidget {{
    alternate-background-color: {layer_02};
}}

QTableWidget QTableCornerButton::section {{
    background-color: {layer_02};
    border: none;
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


def stylesheet(theme: str, *, font_size: int = DEFAULT_FONT_SIZE, text_color: str | None = None) -> str:
    """Build the QSS for `theme` ('dark' | 'light').

    `font_size` scales the base UI + editor font. `text_color`, when given,
    overrides that theme's default primary text color (used by the
    Preferences dialog's "text color" pickers) — the rest of the palette
    (backgrounds, borders, accents) stays put so contrast is preserved.
    """
    base = DARK if theme == "dark" else LIGHT
    tok = dict(base)
    if text_color:
        tok["text_primary"] = text_color
    tok["font_size"] = int(font_size)
    tok["title_font_size"] = int(font_size) + 3
    return _QSS_TEMPLATE.format(**tok)


def tokens(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


# Aliases used by other modules
build_stylesheet = stylesheet
tokens_for = tokens
