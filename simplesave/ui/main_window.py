"""Main window: tag bar, toolbar, sidebar (folders + tags), snippet list, editor."""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QSize, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pyperclip

from simplesave import __version__, config, io_formats, theme
from simplesave.db import Database
from simplesave.models import Snippet, Tag
from simplesave.ui.dialogs import NewTagDialog, PreferencesDialog
from simplesave.ui.highlighter import LANGUAGE_CHOICES, SnippetHighlighter
from simplesave.ui.tag_pill import TagPill

# All top-toolbar controls (tag pills, icon buttons, text buttons) share
# this exact height so the toolbar reads as one consistent row instead of
# a jumble of differently-sized controls with different natural heights.
_TOOLBAR_CONTROL_HEIGHT = 32


class MainWindow(QMainWindow):
    def __init__(self, db: Database, prefs: dict) -> None:
        super().__init__()
        self.db = db
        self.prefs = prefs
        self.setWindowTitle(f"simpleSave v{__version__}")
        self.resize(1200, 760)

        self._current_snippet: Optional[Snippet] = None
        self._active_tag_ids: set[int] = set(prefs.get("active_tag_ids") or [])
        self._search_text: str = ""
        self._suspend_autosave: bool = False
        # Snippet table sort state -- Description ascending by default,
        # matching the original alphabetized-index ordering.
        self._sort_column: int = 1
        self._sort_ascending: bool = True

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._do_autosave)

        self._build_ui()
        self._wire_shortcuts()
        self._reload_all()

    # ---------- build ----------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_list_pane())
        splitter.addWidget(self._build_editor_pane())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 480])
        v.addWidget(splitter, 1)

    def _build_top_bar(self) -> QWidget:
        # Single top bar containing: tag pills (left, scrollable), toolbar (right)
        bar = QWidget()
        bar.setObjectName("tagBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(8)

        # left: scrollable tag pills
        self._tag_bar_inner = QWidget()
        self._tag_bar_layout = QHBoxLayout(self._tag_bar_inner)
        self._tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self._tag_bar_layout.setSpacing(6)
        self._tag_bar_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(self._tag_bar_inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMaximumHeight(44)
        h.addWidget(scroll, 1)

        # right: toolbar
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(6)

        new_tag_btn = QPushButton("+ Tag")
        new_tag_btn.setProperty("variant", "secondary")
        new_tag_btn.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
        new_tag_btn.clicked.connect(self._new_tag)
        tb.addWidget(new_tag_btn)

        theme_btn = QPushButton()
        theme_btn.setProperty("variant", "ghost")
        theme_btn.setIcon(self._theme_icon(self.prefs["theme"]))
        theme_btn.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        theme_btn.setFixedSize(_TOOLBAR_CONTROL_HEIGHT, _TOOLBAR_CONTROL_HEIGHT)
        theme_btn.setToolTip("Toggle theme")
        theme_btn.clicked.connect(self._toggle_theme)
        self._theme_btn = theme_btn
        tb.addWidget(theme_btn)

        template_btn = QPushButton("Template")
        template_btn.setProperty("variant", "secondary")
        template_btn.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
        template_btn.setToolTip(
            "Save a blank CSV in the exact format simpleSave expects,\n"
            "so you can fill it in and bulk-import it back."
        )
        template_btn.clicked.connect(self._export_import_template)
        tb.addWidget(template_btn)

        import_btn = QPushButton("Import")
        import_btn.setProperty("variant", "secondary")
        import_btn.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
        import_btn.clicked.connect(self._import_files)
        tb.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.setProperty("variant", "secondary")
        export_btn.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
        export_btn.clicked.connect(self._export_dialog)
        tb.addWidget(export_btn)

        prefs_btn = QPushButton("Preferences")
        prefs_btn.setProperty("variant", "ghost")
        prefs_btn.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
        prefs_btn.clicked.connect(self._open_preferences)
        tb.addWidget(prefs_btn)

        h.addWidget(toolbar)
        return bar

    def _build_list_pane(self) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("sidebar")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # A small toolbar sits above the column headers, like a web app's
        # table controls: search on the left, the primary add action on
        # the right.
        list_toolbar = QWidget()
        list_toolbar.setObjectName("listToolbar")
        lt = QHBoxLayout(list_toolbar)
        lt.setContentsMargins(12, 10, 12, 10)
        lt.setSpacing(8)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search snippets…")
        self._search_edit.textChanged.connect(self._on_search_changed)
        lt.addWidget(self._search_edit, 1)

        add_btn = QPushButton("+   Add New Snippet")
        add_btn.setProperty("variant", "primary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._new_snippet)
        lt.addWidget(add_btn)

        v.addWidget(list_toolbar)

        self._snippet_list = QTableWidget(0, 3)
        self._snippet_list.setHorizontalHeaderLabels(["Snippet", "Description", ""])
        self._snippet_list.verticalHeader().setVisible(False)
        # Real breathing room per row -- the old default height was cramped
        # enough to look broken rather than just dense.
        self._snippet_list.verticalHeader().setDefaultSectionSize(44)
        self._snippet_list.setShowGrid(False)
        self._snippet_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._snippet_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._snippet_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._snippet_list.setAlternatingRowColors(True)
        # Snippet and Description are freely resizable (including the
        # divider between them) rather than auto-stretching, which blocked
        # dragging that boundary. The trailing Copy column stays a fixed,
        # narrow width -- it's a button, not data.
        self._snippet_list.horizontalHeader().setStretchLastSection(False)
        self._snippet_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._snippet_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self._snippet_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._snippet_list.setColumnWidth(0, 460)
        self._snippet_list.setColumnWidth(1, 420)
        self._snippet_list.setColumnWidth(2, 56)
        # Click a header to sort by it (click again to flip direction) --
        # the Copy column ignores clicks, it isn't sortable data.
        self._snippet_list.horizontalHeader().setSortIndicatorShown(True)
        self._snippet_list.horizontalHeader().setSectionsClickable(True)
        self._snippet_list.horizontalHeader().setCursor(Qt.PointingHandCursor)
        self._snippet_list.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self._snippet_list.itemSelectionChanged.connect(self._on_snippet_selected)
        self._snippet_list.cellDoubleClicked.connect(self._on_snippet_double_clicked)
        v.addWidget(self._snippet_list, 1)

        return wrap

    def _build_editor_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("editorPane")
        v = QVBoxLayout(pane)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)

        # title, styled as a heading (see QLineEdit#TitleInput in theme.py) so
        # a snippet reads as "description, then code" rather than a form.
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("TitleInput")
        self._title_edit.setPlaceholderText("Title")
        self._title_edit.textChanged.connect(self._schedule_autosave)
        title_row.addWidget(self._title_edit, 1)

        # Folder / Language / Tags are metadata, not part of the reading
        # view -- collapsed behind a disclosure toggle by default so the
        # main view stays just "title + code".
        self._details_toggle_btn = QPushButton()
        self._details_toggle_btn.setProperty("variant", "ghost")
        self._details_toggle_btn.setCheckable(True)
        self._details_toggle_btn.setChecked(bool(self.prefs.get("details_expanded", False)))
        self._details_toggle_btn.clicked.connect(self._toggle_details)
        title_row.addWidget(self._details_toggle_btn)

        v.addLayout(title_row)

        # folder + language + tags row (collapsible)
        self._meta_widget = QWidget()
        meta = QHBoxLayout(self._meta_widget)
        meta.setContentsMargins(0, 4, 0, 4)
        meta.setSpacing(8)

        meta.addWidget(QLabel("Folder:"))
        self._folder_combo = QComboBox()
        self._folder_combo.currentIndexChanged.connect(self._on_editor_folder_changed)
        meta.addWidget(self._folder_combo)

        meta.addSpacing(12)
        meta.addWidget(QLabel("Language:"))
        self._language_combo = QComboBox()
        for label, value in LANGUAGE_CHOICES:
            self._language_combo.addItem(label, value)
        self._language_combo.setToolTip("Controls syntax color-coding for this snippet's body.")
        self._language_combo.currentIndexChanged.connect(self._on_editor_language_changed)
        meta.addWidget(self._language_combo)

        meta.addSpacing(12)
        meta.addWidget(QLabel("Tags:"))

        self._editor_tags_host = QWidget()
        self._editor_tags_layout = QHBoxLayout(self._editor_tags_host)
        self._editor_tags_layout.setContentsMargins(0, 0, 0, 0)
        self._editor_tags_layout.setSpacing(6)
        self._editor_tags_layout.addStretch(1)
        meta.addWidget(self._editor_tags_host, 1)

        add_tag_btn = QPushButton("+")
        add_tag_btn.setProperty("variant", "ghost")
        add_tag_btn.setFixedWidth(28)
        add_tag_btn.clicked.connect(self._add_tag_to_current)
        meta.addWidget(add_tag_btn)

        v.addWidget(self._meta_widget)
        self._meta_widget.setVisible(self._details_toggle_btn.isChecked())
        self._update_details_toggle_text()

        # editor
        self._editor = QPlainTextEdit()
        self._editor.setObjectName("editor")
        self._editor.setPlaceholderText("Write your snippet here…")
        self._editor.textChanged.connect(self._schedule_autosave)
        v.addWidget(self._editor, 1)

        self._highlighter = SnippetHighlighter(self._editor.document(), theme_name=self.prefs["theme"])

        # bottom actions
        bottom = QHBoxLayout()
        copy_btn = QPushButton("Copy")
        copy_btn.setProperty("variant", "secondary")
        copy_btn.clicked.connect(self._copy_current)
        bottom.addWidget(copy_btn)

        export_one_btn = QPushButton("Export this")
        export_one_btn.setProperty("variant", "secondary")
        export_one_btn.clicked.connect(self._export_current)
        bottom.addWidget(export_one_btn)

        del_btn = QPushButton("Delete")
        del_btn.setProperty("variant", "danger")
        del_btn.clicked.connect(self._delete_current)
        bottom.addWidget(del_btn)

        bottom.addStretch(1)
        self._status_label = QLabel("")
        self._status_label.setProperty("role", "muted")
        bottom.addWidget(self._status_label)

        v.addLayout(bottom)
        return pane

    def _toggle_details(self) -> None:
        expanded = self._details_toggle_btn.isChecked()
        self._meta_widget.setVisible(expanded)
        self._update_details_toggle_text()
        self.prefs["details_expanded"] = expanded
        config.save_prefs(self.prefs)

    def _update_details_toggle_text(self) -> None:
        expanded = self._details_toggle_btn.isChecked()
        self._details_toggle_btn.setText("\u25be Details" if expanded else "\u25b8 Details")

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._new_snippet)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self._search_edit.setFocus())
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._do_autosave)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self._copy_current)

    # ---------- data refresh ----------

    def _reload_all(self) -> None:
        self._reload_tag_bar()
        self._reload_folder_combo()
        self._reload_snippets()

    def _reload_tag_bar(self) -> None:
        # clear all pill widgets but keep the trailing stretch
        while self._tag_bar_layout.count() > 1:
            item = self._tag_bar_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        tags = self.db.list_tags()
        if not tags:
            placeholder = QLabel("No tags yet — click '+ Tag' to add one.")
            placeholder.setProperty("role", "muted")
            self._tag_bar_layout.insertWidget(0, placeholder)
            return

        insert_at = 0
        for t in tags:
            pill = TagPill(t, active=(t.id in self._active_tag_ids))
            pill.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
            pill.clicked.connect(self._toggle_tag_filter)
            self._tag_bar_layout.insertWidget(insert_at, pill)
            insert_at += 1

    def _reload_folder_combo(self) -> None:
        self._folder_combo.blockSignals(True)
        self._folder_combo.clear()
        self._folder_combo.addItem("(none)", None)
        for f in self.db.list_folders():
            self._folder_combo.addItem(f.name, f.id)
        self._folder_combo.blockSignals(False)

    def _reload_snippets(self) -> None:
        self._snippet_list.blockSignals(True)
        self._snippet_list.setRowCount(0)

        snippets = self.db.list_snippets(
            tag_ids=list(self._active_tag_ids) or None,
            search=self._search_text or None,
        )

        # Sort by whichever column header was last clicked (Description
        # ascending by default -- an A-Z reference index, not
        # most-recent-first).
        if self._sort_column == 0:
            key_fn = lambda s: self._snippet_preview(s.body).lower()
        else:
            key_fn = lambda s: (s.title or "").lower()
        snippets.sort(key=key_fn, reverse=not self._sort_ascending)

        self._snippet_list.setRowCount(len(snippets))

        for row_idx, s in enumerate(snippets):
            tag_names = ", ".join(t.name for t in s.tags)

            # Plain items (not a custom widget) render as literal text --
            # a QLabel would auto-detect any preview starting with "<" as
            # HTML and silently render it as a (invisible) table/div/link/
            # meta/title tag instead of showing the code.
            snippet_item = QTableWidgetItem(self._snippet_preview(s.body))
            snippet_item.setData(Qt.UserRole, s.id)
            snippet_item.setToolTip(tag_names)
            mono = QFont("Space Mono")
            mono.setStyleHint(QFont.Monospace)
            snippet_item.setFont(mono)
            self._snippet_list.setItem(row_idx, 0, snippet_item)

            desc_item = QTableWidgetItem(s.title or "(untitled)")
            desc_item.setData(Qt.UserRole, s.id)
            desc_item.setToolTip(tag_names)
            self._snippet_list.setItem(row_idx, 1, desc_item)

            copy_placeholder = QTableWidgetItem()
            copy_placeholder.setData(Qt.UserRole, s.id)
            copy_placeholder.setFlags(Qt.ItemIsEnabled)
            self._snippet_list.setItem(row_idx, 2, copy_placeholder)
            self._snippet_list.setCellWidget(row_idx, 2, self._build_copy_button(s.id))

        self._snippet_list.horizontalHeader().setSortIndicator(
            self._sort_column,
            Qt.AscendingOrder if self._sort_ascending else Qt.DescendingOrder,
        )

        self._snippet_list.blockSignals(False)

        # try to restore selection on current snippet
        if self._current_snippet is not None:
            for i in range(self._snippet_list.rowCount()):
                if self._snippet_list.item(i, 0).data(Qt.UserRole) == self._current_snippet.id:
                    self._snippet_list.selectRow(i)
                    return

        if self._snippet_list.rowCount() > 0:
            self._snippet_list.selectRow(0)
        else:
            self._load_into_editor(None)

    def _on_header_clicked(self, column: int) -> None:
        if column == 2:
            return  # the Copy column isn't sortable data
        if column == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        self._reload_snippets()

    _ICON_SIZE = 16

    def _glyph_icon(self, kind: str, color: str) -> QIcon:
        """Draw a tiny copy/checkmark glyph on the fly instead of relying
        on a font character (which can render blank if the font lacks it)
        or a bundled image asset (one more thing to package correctly)."""
        size = self._ICON_SIZE
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color))
        if kind == "check":
            pen.setWidthF(1.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(3, size / 2)
            path.lineTo(size / 2 - 1, size - 4)
            path.lineTo(size - 3, 3.5)
            painter.drawPath(path)
        elif kind == "moon":
            # A crescent drawn as a filled circle with an offset circle
            # subtracted out -- not a "☾" font glyph, which can silently
            # fall back to the wrong character on a system that lacks it
            # (the exact bug that broke the old text "Copy" button).
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            outer = QPainterPath()
            outer.addEllipse(2.0, 2.0, size - 4.0, size - 4.0)
            inner = QPainterPath()
            inner.addEllipse(5.0, 1.0, size - 4.0, size - 4.0)
            painter.drawPath(outer.subtracted(inner))
        elif kind == "sun":
            pen.setWidthF(1.4)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(QColor(color))
            cx = cy = size / 2
            r = 3.0
            painter.drawEllipse(QPointF(cx, cy), r, r)
            for i in range(8):
                angle = math.radians(i * 45)
                x1 = cx + math.cos(angle) * (r + 1.6)
                y1 = cy + math.sin(angle) * (r + 1.6)
                x2 = cx + math.cos(angle) * (r + 4.0)
                y2 = cy + math.sin(angle) * (r + 4.0)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        else:
            pen.setWidthF(1.3)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            # Two overlapping rounded squares -- the universal "copy" glyph.
            painter.drawRoundedRect(2, 4, size - 6, size - 6, 2, 2)
            painter.drawRoundedRect(5, 1, size - 6, size - 6, 2, 2)
        painter.end()
        return QIcon(pm)

    def _theme_icon(self, theme_name: str) -> QIcon:
        tokens = theme.tokens(theme_name)
        return self._glyph_icon("moon" if theme_name == "dark" else "sun", tokens["text_primary"])

    def _build_copy_button(self, snippet_id: int) -> QWidget:
        """A plain icon, no visible button chrome -- click to copy, a
        quick checkmark confirms it. Minimal, the way copy affordances
        work on most code-snippet websites (no bordered "Copy" pill)."""
        cell = QWidget()
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(0, 0, 0, 0)
        tokens = theme.tokens(self.prefs["theme"])
        btn = QPushButton()
        btn.setIcon(self._glyph_icon("copy", tokens["text_secondary"]))
        btn.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        btn.setProperty("variant", "icon-ghost")
        btn.setFixedSize(32, 32)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Copy")
        btn.clicked.connect(lambda _checked=False, sid=snippet_id, b=btn: self._copy_snippet_by_id(sid, b))
        lay.addWidget(btn, 0, Qt.AlignCenter)
        return cell

    def _copy_snippet_by_id(self, snippet_id: int, button: Optional[QPushButton] = None) -> None:
        snippet = self.db.get_snippet(int(snippet_id))
        if snippet is None:
            return
        try:
            pyperclip.copy(snippet.body)
            self._status_label.setText("copied to clipboard")
            if button is not None:
                tokens = theme.tokens(self.prefs["theme"])
                button.setIcon(self._glyph_icon("check", tokens["success"]))
                button.setToolTip("Copied")
                QTimer.singleShot(1200, lambda b=button: self._reset_copy_button(b))
        except Exception as e:
            QMessageBox.warning(self, "Clipboard error", str(e))

    def _reset_copy_button(self, button: QPushButton) -> None:
        # The row may have been rebuilt (search/filter/reload) before this
        # timer fires, in which case the button no longer exists.
        try:
            tokens = theme.tokens(self.prefs["theme"])
            button.setIcon(self._glyph_icon("copy", tokens["text_secondary"]))
            button.setToolTip("Copy")
        except RuntimeError:
            pass

    @staticmethod
    def _snippet_preview(body: str) -> str:
        lines = (body or "").strip().splitlines()
        preview = lines[0].strip() if lines else ""
        if not preview:
            return "(empty)"
        if len(preview) > 60:
            return preview[:57] + "..."
        if len(lines) > 1:
            return preview + "  \u2026"
        return preview

    # ---------- selection handlers ----------

    def _on_snippet_selected(self) -> None:
        item = self._snippet_list.currentItem()
        if item is None:
            self._load_into_editor(None)
            return
        sid = item.data(Qt.UserRole)
        snippet = self.db.get_snippet(int(sid))
        self._load_into_editor(snippet)
        if snippet is not None:
            self._copy_current()

    def _on_snippet_double_clicked(self, row: int, column: int) -> None:
        if column == 2:
            return  # the Copy column handles its own click
        item = self._snippet_list.item(row, 0)
        if item is None:
            return
        # Selection (single-click) already loaded + copied the snippet;
        # double-click just moves focus into the field you meant to change,
        # rather than editing the truncated preview text in the cell itself
        # -- risky for a multi-line snippet body.
        if column == 1:
            self._title_edit.setFocus()
            self._title_edit.selectAll()
        else:
            self._editor.setFocus()
            self._editor.moveCursor(QTextCursor.End)

    def _toggle_tag_filter(self, tag_id: int) -> None:
        if tag_id in self._active_tag_ids:
            self._active_tag_ids.remove(tag_id)
        else:
            self._active_tag_ids.add(tag_id)
        self.prefs["active_tag_ids"] = list(self._active_tag_ids)
        config.save_prefs(self.prefs)
        self._reload_tag_bar()
        self._reload_snippets()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self._reload_snippets()

    # ---------- editor load/save ----------

    def _load_into_editor(self, snippet: Optional[Snippet]) -> None:
        self._suspend_autosave = True
        self._current_snippet = snippet
        if snippet is None:
            self._title_edit.clear()
            self._editor.clear()
            self._folder_combo.setCurrentIndex(0)
            self._language_combo.setCurrentIndex(0)
            self._highlighter.set_language(None)
            self._rebuild_editor_tag_pills([])
            self._status_label.clear()
            self._suspend_autosave = False
            return

        self._title_edit.setText(snippet.title)
        self._editor.setPlainText(snippet.body)
        # folder
        idx = self._folder_combo.findData(snippet.folder_id)
        self._folder_combo.setCurrentIndex(idx if idx >= 0 else 0)
        # language — fall back to "Plain text" in the dropdown for a value
        # outside our curated list, but still highlight using the snippet's
        # real language so nothing imported gets silently un-highlighted.
        lidx = self._language_combo.findData(snippet.language)
        self._language_combo.setCurrentIndex(lidx if lidx >= 0 else 0)
        self._highlighter.set_language(snippet.language)
        self._rebuild_editor_tag_pills(snippet.tags)
        self._status_label.setText(f"updated {snippet.updated_at}")
        self._suspend_autosave = False

    def _rebuild_editor_tag_pills(self, tags: list[Tag]) -> None:
        while self._editor_tags_layout.count() > 1:
            item = self._editor_tags_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        insert_at = 0
        for t in tags:
            pill = TagPill(t, removable=True, active=True)
            pill.removed.connect(self._remove_tag_from_current)
            self._editor_tags_layout.insertWidget(insert_at, pill)
            insert_at += 1

    def _schedule_autosave(self) -> None:
        if self._suspend_autosave or self._current_snippet is None:
            return
        self._autosave_timer.start(int(self.prefs.get("autosave_ms", 500)))

    def _do_autosave(self) -> None:
        if self._current_snippet is None:
            return
        title = self._title_edit.text().strip() or "(untitled)"
        body = self._editor.toPlainText()
        folder_id = self._folder_combo.currentData()
        language = self._language_combo.currentData()
        self.db.update_snippet(
            self._current_snippet.id,
            title=title,
            body=body,
            folder_id=folder_id,
            language=language,
        )
        # refresh just this row's two columns without rebuilding the table
        refreshed = self.db.get_snippet(self._current_snippet.id)
        if refreshed is not None:
            self._current_snippet = refreshed
            row = self._snippet_list.currentRow()
            if row >= 0:
                snippet_item = self._snippet_list.item(row, 0)
                if snippet_item is not None:
                    snippet_item.setText(self._snippet_preview(refreshed.body))
                desc_item = self._snippet_list.item(row, 1)
                if desc_item is not None:
                    desc_item.setText(refreshed.title)
            self._status_label.setText(f"updated {refreshed.updated_at}")

    def _on_editor_folder_changed(self, _idx: int) -> None:
        if self._suspend_autosave or self._current_snippet is None:
            return
        self._schedule_autosave()

    def _on_editor_language_changed(self, _idx: int) -> None:
        self._highlighter.set_language(self._language_combo.currentData())
        if self._suspend_autosave or self._current_snippet is None:
            return
        self._schedule_autosave()

    # ---------- actions ----------

    def _new_snippet(self) -> None:
        s = self.db.create_snippet(title="Untitled", body="", folder_id=None)
        self._reload_snippets()
        self._current_snippet = s
        # select row
        for i in range(self._snippet_list.rowCount()):
            if self._snippet_list.item(i, 0).data(Qt.UserRole) == s.id:
                self._snippet_list.selectRow(i)
                break
        self._title_edit.setFocus()
        self._title_edit.selectAll()

    def _new_tag(self) -> None:
        # Auto-cycle the default color through the palette so each new tag
        # starts with a different color than the last one.
        existing_count = len(self.db.list_tags())
        dlg = NewTagDialog(self, palette_index=existing_count)
        if dlg.exec() == NewTagDialog.Accepted:
            name, color = dlg.get_result()
            if not name:
                return
            self.db.upsert_tag(name, color)
            self._reload_tag_bar()

    def _add_tag_to_current(self) -> None:
        if self._current_snippet is None:
            return
        tags = self.db.list_tags()
        if not tags:
            QMessageBox.information(self, "No tags", "Create a tag first with '+ Tag'.")
            return
        names = [t.name for t in tags]
        name, ok = QInputDialog.getItem(self, "Add tag", "Tag:", names, 0, False)
        if not ok:
            return
        chosen = next((t for t in tags if t.name == name), None)
        if chosen is None:
            return
        current_ids = [t.id for t in self._current_snippet.tags if t.id is not None]
        if chosen.id not in current_ids:
            current_ids.append(chosen.id)  # type: ignore[arg-type]
            self.db.set_snippet_tags(self._current_snippet.id, current_ids)
            self._current_snippet = self.db.get_snippet(self._current_snippet.id)
            self._rebuild_editor_tag_pills(self._current_snippet.tags if self._current_snippet else [])

    def _remove_tag_from_current(self, tag_id: int) -> None:
        if self._current_snippet is None:
            return
        new_ids = [t.id for t in self._current_snippet.tags if t.id != tag_id]
        self.db.set_snippet_tags(self._current_snippet.id, [i for i in new_ids if i is not None])
        self._current_snippet = self.db.get_snippet(self._current_snippet.id)
        self._rebuild_editor_tag_pills(self._current_snippet.tags if self._current_snippet else [])

    def _copy_current(self) -> None:
        if self._current_snippet is None:
            return
        try:
            pyperclip.copy(self._editor.toPlainText())
            self._status_label.setText("copied to clipboard")
        except Exception as e:
            QMessageBox.warning(self, "Clipboard error", str(e))

    def _delete_current(self) -> None:
        if self._current_snippet is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete snippet",
            f"Delete '{self._current_snippet.title}'?",
        )
        if confirm != QMessageBox.Yes:
            return
        self.db.delete_snippet(self._current_snippet.id)
        self._current_snippet = None
        self._reload_snippets()

    def _current_stylesheet(self) -> str:
        active_theme = self.prefs["theme"]
        return theme.build_stylesheet(
            active_theme,
            font_size=int(self.prefs.get("font_size", theme.DEFAULT_FONT_SIZE)),
            text_color=self.prefs.get(f"text_color_{active_theme}") or None,
        )

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(self._current_stylesheet())

    def _toggle_theme(self) -> None:
        new_theme = "light" if self.prefs["theme"] == "dark" else "dark"
        self.prefs["theme"] = new_theme
        config.save_prefs(self.prefs)
        self._apply_theme()
        self._theme_btn.setIcon(self._theme_icon(new_theme))
        self._highlighter.set_theme(new_theme)
        # tag pills bake colors in their stylesheet — rebuild them; the
        # copy icons are baked pixmaps too, so the row list needs a
        # refresh as well or they'd keep the old theme's color.
        self._reload_tag_bar()
        if self._current_snippet is not None:
            self._rebuild_editor_tag_pills(self._current_snippet.tags)
        self._reload_snippets()

    def _open_preferences(self) -> None:
        dlg = PreferencesDialog(self, prefs=self.prefs, on_change=self._on_prefs_changed)
        dlg.exec()
        config.save_prefs(self.prefs)

    def _on_prefs_changed(self) -> None:
        config.save_prefs(self.prefs)
        self._apply_theme()

    # ---------- reveal in file manager ----------

    def _reveal_path(self, path: Path) -> None:
        """Open the exported file's location. On macOS this reveals and
        highlights the file itself in Finder; elsewhere it opens the
        containing folder (Qt has no cross-platform "select this file" API).
        """
        if sys.platform == "darwin":
            try:
                subprocess.run(["open", "-R", str(path)], check=False)
                return
            except Exception:
                pass
        target = path if path.is_dir() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    # ---------- import / export ----------

    def _import_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import snippets",
            "",
            "Snippet files (*.md *.markdown *.txt *.csv);;All files (*)",
        )
        if not paths:
            return

        md_paths = [Path(p) for p in paths if Path(p).suffix.lower() in (".md", ".markdown")]
        txt_paths = [Path(p) for p in paths if Path(p).suffix.lower() == ".txt"]
        csv_paths = [Path(p) for p in paths if Path(p).suffix.lower() == ".csv"]

        total_created = 0
        total_skipped = 0
        errors: list[str] = []

        if md_paths:
            r = io_formats.import_markdown(self.db, md_paths)
            total_created += r.created
            total_skipped += r.skipped
            errors.extend(r.errors)
        if txt_paths:
            r = io_formats.import_plaintext(self.db, txt_paths)
            total_created += r.created
            total_skipped += r.skipped
            errors.extend(r.errors)
        for cp in csv_paths:
            r = io_formats.import_csv(self.db, cp)
            total_created += r.created
            total_skipped += r.skipped
            errors.extend(r.errors)

        self._reload_all()
        msg = f"Imported {total_created} snippet(s)."
        if total_skipped:
            msg += f"\nSkipped {total_skipped}."
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Import complete", msg)

    def _export_import_template(self) -> None:
        """Save a blank CSV in the exact shape bulk import expects, so it's
        obvious what columns to fill in before importing many snippets at
        once."""
        default_path = Path(self.prefs["default_export_dir"]) / "simplesave-import-template.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save import template",
            str(default_path),
            "CSV (*.csv)",
        )
        if not path:
            return
        out_path = Path(path)
        if out_path.suffix.lower() != ".csv":
            out_path = out_path.with_suffix(".csv")
        io_formats.export_csv_template(out_path)
        self.prefs["default_export_dir"] = str(out_path.parent)
        config.save_prefs(self.prefs)
        self._status_label.setText(f"template saved → {out_path.name}")
        self._reveal_path(out_path)

    def _export_dialog(self) -> None:
        if self._snippet_list.rowCount() == 0:
            QMessageBox.information(self, "Nothing to export", "No snippets in the current view.")
            return
        fmt, ok = QInputDialog.getItem(
            self, "Export", "Format:",
            ["Markdown (.md)", "Plain text (.txt)", "CSV (.csv)"], 0, False,
        )
        if not ok:
            return

        # collect snippets currently visible in the list
        ids = [self._snippet_list.item(i, 0).data(Qt.UserRole) for i in range(self._snippet_list.rowCount())]
        snippets = [self.db.get_snippet(int(i)) for i in ids]
        snippets = [s for s in snippets if s is not None]

        if fmt.startswith("CSV"):
            # A single named file — this is the one export format where
            # "name the export" means something (Markdown/plain text export
            # one file per snippet, named from the snippet's own title).
            default_name = self.prefs.get("last_csv_export_name") or "simplesave-export.csv"
            default_path = Path(self.prefs["default_export_dir"]) / default_name
            path, _ = QFileDialog.getSaveFileName(
                self, "Export as CSV", str(default_path), "CSV (*.csv)",
            )
            if not path:
                return
            out_path = Path(path)
            if out_path.suffix.lower() != ".csv":
                out_path = out_path.with_suffix(".csv")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            self.prefs["default_export_dir"] = str(out_path.parent)
            self.prefs["last_csv_export_name"] = out_path.name
            config.save_prefs(self.prefs)

            n = io_formats.export_csv(self.db, snippets, out_path)
            QMessageBox.information(self, "Export complete", f"Exported {n} snippet(s) to:\n{out_path}")
            self._reveal_path(out_path)
            return

        dest = QFileDialog.getExistingDirectory(
            self, "Export to folder", self.prefs["default_export_dir"]
        )
        if not dest:
            return
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)
        self.prefs["default_export_dir"] = str(dest_path)
        config.save_prefs(self.prefs)

        if fmt.startswith("Markdown"):
            n = io_formats.export_markdown(self.db, snippets, dest_path)
        else:
            n = io_formats.export_plaintext(self.db, snippets, dest_path)

        QMessageBox.information(
            self, "Export complete",
            f"Exported {n} snippet(s) to:\n{dest_path}",
        )
        self._reveal_path(dest_path)

    def _export_current(self) -> None:
        if self._current_snippet is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export snippet",
            _safe_filename(self._current_snippet.title) + ".md",
            "Markdown (*.md);;Plain text (*.txt)",
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() == ".txt":
            p.write_text(self._current_snippet.body or "", encoding="utf-8")
        else:
            p.write_text(
                io_formats.snippet_to_markdown(self.db, self._current_snippet),
                encoding="utf-8",
            )
        self._status_label.setText(f"exported → {p.name}")
        self._reveal_path(p)

    # ---------- close ----------

    def closeEvent(self, event) -> None:  # noqa: N802
        self._do_autosave()
        self.prefs["window_geometry"] = bytes(self.saveGeometry()).hex()
        config.save_prefs(self.prefs)
        super().closeEvent(event)


def _safe_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    out = "".join("_" if c in bad else c for c in name).strip()
    return out or "untitled"
