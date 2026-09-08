"""Syntax highlighting for snippet bodies, via Pygments.

Ties into the snippet's `language` field (the same field used by markdown
front matter and CSV import/export) so highlighting round-trips with the
rest of the app instead of being a separate concept.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name
    from pygments.styles import get_style_by_name
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except Exception:  # pragma: no cover - Pygments ships in requirements.txt
    PYGMENTS_AVAILABLE = False


# Shown in the editor's "Language" dropdown. The second item of each tuple is
# both the Pygments lexer alias *and* what gets stored in Snippet.language /
# round-tripped through markdown front matter and CSV.
LANGUAGE_CHOICES: list[tuple[str, Optional[str]]] = [
    ("Plain text", None),
    ("Python", "python"),
    ("JavaScript", "javascript"),
    ("TypeScript", "typescript"),
    ("HTML", "html"),
    ("CSS", "css"),
    ("JSON", "json"),
    ("YAML", "yaml"),
    ("Bash / Shell", "bash"),
    ("SQL", "sql"),
    ("PHP", "php"),
    ("Ruby", "ruby"),
    ("Go", "go"),
    ("Rust", "rust"),
    ("Java", "java"),
    ("C", "c"),
    ("C++", "cpp"),
    ("C#", "csharp"),
    ("Markdown", "markdown"),
    ("XML", "xml"),
]

# A handful of shorthands people naturally type/import that differ from the
# canonical Pygments lexer alias.
_LANGUAGE_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "yml": "yaml",
    "py": "python",
    "c++": "cpp",
    "c#": "csharp",
    "md": "markdown",
}

# Built-in Pygments styles chosen to sit well against our Carbon-derived
# dark/light backgrounds. Swap these if the app's palette changes.
STYLE_FOR_THEME = {
    "dark": "monokai",
    "light": "friendly",
}


class SnippetHighlighter(QSyntaxHighlighter):
    """Colors a QPlainTextEdit's body according to the snippet's language.

    Re-lexes the full document text whenever it changes and caches the
    resulting spans keyed by the Qt document's revision, so one keystroke
    triggers one lex pass, not one per visible line. Snippet bodies are
    short (this is a snippet manager, not an IDE), so relexing the whole
    document on every edit is cheap.
    """

    def __init__(self, document, theme_name: str = "dark") -> None:
        super().__init__(document)
        self._language: Optional[str] = None
        self._lexer = None
        self._style_cls = None
        self._format_cache: dict = {}
        self._span_cache_revision: int = -1
        self._span_cache: list[tuple[int, int, QTextCharFormat]] = []
        if PYGMENTS_AVAILABLE:
            self._load_style(STYLE_FOR_THEME.get(theme_name, "monokai"))

    # ---------- configuration ----------

    def set_theme(self, theme_name: str) -> None:
        if not PYGMENTS_AVAILABLE:
            return
        self._load_style(STYLE_FOR_THEME.get(theme_name, "monokai"))
        self._invalidate()

    def set_language(self, language: Optional[str]) -> None:
        language = (language or "").strip().lower() or None
        if language == self._language:
            return
        self._language = language
        self._lexer = self._build_lexer(language)
        self._invalidate()

    def _load_style(self, style_name: str) -> None:
        try:
            self._style_cls = get_style_by_name(style_name)
        except Exception:
            self._style_cls = get_style_by_name("default")
        self._format_cache = {}

    def _build_lexer(self, language: Optional[str]):
        if not PYGMENTS_AVAILABLE or not language:
            return None
        alias = _LANGUAGE_ALIASES.get(language, language)
        try:
            return get_lexer_by_name(alias, stripnl=False)
        except ClassNotFound:
            return None

    def _invalidate(self) -> None:
        self._span_cache_revision = -1
        self.rehighlight()

    # ---------- Qt hook ----------

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        if not PYGMENTS_AVAILABLE or self._lexer is None or self._style_cls is None:
            return

        doc = self.document()
        revision = doc.revision()
        if revision != self._span_cache_revision:
            self._span_cache = self._compute_spans(doc.toPlainText())
            self._span_cache_revision = revision

        block_start = self.currentBlock().position()
        block_end = block_start + len(text)
        for start, end, fmt in self._span_cache:
            if end <= block_start or start >= block_end:
                continue
            s = max(start, block_start) - block_start
            e = min(end, block_end) - block_start
            if e > s:
                self.setFormat(s, e - s, fmt)

    # ---------- lexing ----------

    def _compute_spans(self, full_text: str) -> list[tuple[int, int, QTextCharFormat]]:
        spans: list[tuple[int, int, QTextCharFormat]] = []
        pos = 0
        try:
            tokens = list(lex(full_text, self._lexer))
        except Exception:
            return spans
        for ttype, value in tokens:
            length = len(value)
            if length and value.strip():
                spans.append((pos, pos + length, self._format_for(ttype)))
            pos += length
        return spans

    def _format_for(self, ttype) -> QTextCharFormat:
        cached = self._format_cache.get(ttype)
        if cached is not None:
            return cached

        style = None
        t = ttype
        while t is not None:
            try:
                style = self._style_cls.style_for_token(t)
                break
            except KeyError:
                t = t.parent
        style = style or {}

        fmt = QTextCharFormat()
        if style.get("color"):
            fmt.setForeground(QColor(f"#{style['color']}"))
        if style.get("bold"):
            fmt.setFontWeight(QFont.Bold)
        if style.get("italic"):
            fmt.setFontItalic(True)
        if style.get("underline"):
            fmt.setFontUnderline(True)
        self._format_cache[ttype] = fmt
        return fmt
