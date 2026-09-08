"""Main window: tag bar, toolbar, sidebar (folders + tags), snippet list, editor."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pyperclip

from simplesave import config, io_formats, theme
from simplesave.db import Database
from simplesave.models import Snippet, Tag
from simplesave.ui.dialogs import NewTagDialog
from simplesave.ui.tag_pill import TagPill


class MainWindow(QMainWindow):
    def __init__(self, db: Database, prefs: dict) -> None:
        super().__init__()
        self.db = db
        self.prefs = prefs
        self.setWindowTitle("simpleSave")
        self.resize(1200, 760)

        self._current_snippet: Optional[Snippet] = None
        self._active_tag_ids: set[int] = set(prefs.get("active_tag_ids") or [])
        self._active_folder_id: Optional[int] = prefs.get("active_folder_id")
        self._search_text: str = ""
        self._suspend_autosave: bool = False

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
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_list_pane())
        splitter.addWidget(self._build_editor_pane())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([220, 280, 700])
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

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search…")
        self._search_edit.setFixedWidth(220)
        self._search_edit.textChanged.connect(self._on_search_changed)
        tb.addWidget(self._search_edit)

        new_btn = QPushButton("+ New")
        new_btn.clicked.connect(self._new_snippet)
        tb.addWidget(new_btn)

        new_tag_btn = QPushButton("+ Tag")
        new_tag_btn.setProperty("variant", "secondary")
        new_tag_btn.clicked.connect(self._new_tag)
        tb.addWidget(new_tag_btn)

        theme_btn = QPushButton("☾" if self.prefs["theme"] == "dark" else "☼")
        theme_btn.setProperty("variant", "ghost")
        theme_btn.setToolTip("Toggle theme")
        theme_btn.clicked.connect(self._toggle_theme)
        self._theme_btn = theme_btn
        tb.addWidget(theme_btn)

        import_btn = QPushButton("Import")
        import_btn.setProperty("variant", "secondary")
        import_btn.clicked.connect(self._import_files)
        tb.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.setProperty("variant", "secondary")
        export_btn.clicked.connect(self._export_dialog)
        tb.addWidget(export_btn)

        h.addWidget(toolbar)
        return bar

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QLabel("Folders")
        header.setProperty("role", "heading")
        header.setContentsMargins(12, 12, 12, 8)
        v.addWidget(header)

        self._folder_tree = QTreeWidget()
        self._folder_tree.setHeaderHidden(True)
        self._folder_tree.itemSelectionChanged.connect(self._on_folder_selected)
        v.addWidget(self._folder_tree, 1)

        actions = QWidget()
        ah = QHBoxLayout(actions)
        ah.setContentsMargins(8, 8, 8, 8)
        ah.setSpacing(6)
        new_folder = QPushButton("+ Folder")
        new_folder.setProperty("variant", "ghost")
        new_folder.clicked.connect(self._new_folder)
        ah.addWidget(new_folder)
        del_folder = QPushButton("Delete")
        del_folder.setProperty("variant", "ghost")
        del_folder.clicked.connect(self._delete_folder)
        ah.addWidget(del_folder)
        ah.addStretch(1)
        v.addWidget(actions)

        return side

    def _build_list_pane(self) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("sidebar")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QLabel("Snippets")
        header.setProperty("role", "heading")
        header.setContentsMargins(12, 12, 12, 8)
        v.addWidget(header)

        self._snippet_list = QListWidget()
        self._snippet_list.itemSelectionChanged.connect(self._on_snippet_selected)
        v.addWidget(self._snippet_list, 1)

        return wrap

    def _build_editor_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("editorPane")
        v = QVBoxLayout(pane)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)

        # title
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Title")
        self._title_edit.textChanged.connect(self._schedule_autosave)
        v.addWidget(self._title_edit)

        # folder + tags row
        meta = QHBoxLayout()
        meta.setSpacing(8)

        meta.addWidget(QLabel("Folder:"))
        self._folder_combo = QComboBox()
        self._folder_combo.currentIndexChanged.connect(self._on_editor_folder_changed)
        meta.addWidget(self._folder_combo)

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

        v.addLayout(meta)

        # editor
        self._editor = QPlainTextEdit()
        self._editor.setObjectName("editor")
        self._editor.setPlaceholderText("Write your snippet here…")
        self._editor.textChanged.connect(self._schedule_autosave)
        v.addWidget(self._editor, 1)

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

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._new_snippet)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self._search_edit.setFocus())
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._do_autosave)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self._copy_current)

    # ---------- data refresh ----------

    def _reload_all(self) -> None:
        self._reload_tag_bar()
        self._reload_folders()
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
            pill.clicked.connect(self._toggle_tag_filter)
            self._tag_bar_layout.insertWidget(insert_at, pill)
            insert_at += 1

    def _reload_folders(self) -> None:
        self._folder_tree.blockSignals(True)
        self._folder_tree.clear()

        all_root = QTreeWidgetItem(["All snippets"])
        all_root.setData(0, Qt.UserRole, "__all__")
        self._folder_tree.addTopLevelItem(all_root)

        none_root = QTreeWidgetItem(["Unfiled"])
        none_root.setData(0, Qt.UserRole, "__none__")
        self._folder_tree.addTopLevelItem(none_root)

        folders = self.db.list_folders()
        items_by_id: dict[int, QTreeWidgetItem] = {}
        # first pass: roots
        for f in folders:
            item = QTreeWidgetItem([f.name])
            item.setData(0, Qt.UserRole, f.id)
            items_by_id[f.id] = item  # type: ignore[index]
            if f.parent_id is None:
                self._folder_tree.addTopLevelItem(item)
        # second pass: children
        for f in folders:
            if f.parent_id is not None:
                parent = items_by_id.get(f.parent_id)
                child = items_by_id.get(f.id)  # type: ignore[arg-type]
                if parent is not None and child is not None:
                    parent.addChild(child)

        self._folder_tree.expandAll()

        # restore selection
        if self._active_folder_id is None:
            self._folder_tree.setCurrentItem(all_root)
        else:
            target = items_by_id.get(self._active_folder_id)
            if target is not None:
                self._folder_tree.setCurrentItem(target)
            else:
                self._folder_tree.setCurrentItem(all_root)
        self._folder_tree.blockSignals(False)

    def _reload_folder_combo(self) -> None:
        self._folder_combo.blockSignals(True)
        self._folder_combo.clear()
        self._folder_combo.addItem("(none)", None)
        for f in self.db.list_folders():
            self._folder_combo.addItem(f.name, f.id)
        self._folder_combo.blockSignals(False)

    def _reload_snippets(self) -> None:
        self._snippet_list.blockSignals(True)
        self._snippet_list.clear()

        snippets = self.db.list_snippets(
            folder_id=self._active_folder_id if self._active_folder_id != "__none__" else None,
            tag_ids=list(self._active_tag_ids) or None,
            search=self._search_text or None,
        )
        if self._active_folder_id == "__none__":
            snippets = [s for s in snippets if s.folder_id is None]

        for s in snippets:
            item = QListWidgetItem(s.title or "(untitled)")
            item.setData(Qt.UserRole, s.id)
            tag_names = ", ".join(t.name for t in s.tags)
            item.setToolTip(tag_names)
            self._snippet_list.addItem(item)

        self._snippet_list.blockSignals(False)

        # try to restore selection on current snippet
        if self._current_snippet is not None:
            for i in range(self._snippet_list.count()):
                if self._snippet_list.item(i).data(Qt.UserRole) == self._current_snippet.id:
                    self._snippet_list.setCurrentRow(i)
                    return

        if self._snippet_list.count() > 0:
            self._snippet_list.setCurrentRow(0)
        else:
            self._load_into_editor(None)

    # ---------- selection handlers ----------

    def _on_folder_selected(self) -> None:
        items = self._folder_tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.UserRole)
        if data == "__all__":
            self._active_folder_id = None
        elif data == "__none__":
            self._active_folder_id = "__none__"  # type: ignore[assignment]
        else:
            self._active_folder_id = int(data)
        self.prefs["active_folder_id"] = (
            self._active_folder_id if isinstance(self._active_folder_id, int) else None
        )
        config.save_prefs(self.prefs)
        self._reload_snippets()

    def _on_snippet_selected(self) -> None:
        item = self._snippet_list.currentItem()
        if item is None:
            self._load_into_editor(None)
            return
        sid = item.data(Qt.UserRole)
        snippet = self.db.get_snippet(int(sid))
        self._load_into_editor(snippet)

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
            self._rebuild_editor_tag_pills([])
            self._status_label.clear()
            self._suspend_autosave = False
            return

        self._title_edit.setText(snippet.title)
        self._editor.setPlainText(snippet.body)
        # folder
        idx = self._folder_combo.findData(snippet.folder_id)
        self._folder_combo.setCurrentIndex(idx if idx >= 0 else 0)
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
            pill = TagPill(t, removable=True)
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
        self.db.update_snippet(
            self._current_snippet.id,
            title=title,
            body=body,
            folder_id=folder_id,
        )
        # refresh just the list row label without rebuilding everything
        refreshed = self.db.get_snippet(self._current_snippet.id)
        if refreshed is not None:
            self._current_snippet = refreshed
            row = self._snippet_list.currentRow()
            if row >= 0:
                self._snippet_list.item(row).setText(refreshed.title)
            self._status_label.setText(f"updated {refreshed.updated_at}")

    def _on_editor_folder_changed(self, _idx: int) -> None:
        if self._suspend_autosave or self._current_snippet is None:
            return
        self._schedule_autosave()

    # ---------- actions ----------

    def _new_snippet(self) -> None:
        folder_id = self._active_folder_id if isinstance(self._active_folder_id, int) else None
        s = self.db.create_snippet(title="Untitled", body="", folder_id=folder_id)
        self._reload_snippets()
        self._current_snippet = s
        # select row
        for i in range(self._snippet_list.count()):
            if self._snippet_list.item(i).data(Qt.UserRole) == s.id:
                self._snippet_list.setCurrentRow(i)
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

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New folder", "Folder name:")
        if not ok or not name.strip():
            return
        self.db.create_folder(name.strip())
        self._reload_folders()
        self._reload_folder_combo()

    def _delete_folder(self) -> None:
        if not isinstance(self._active_folder_id, int):
            return
        confirm = QMessageBox.question(
            self,
            "Delete folder",
            "Delete this folder? Snippets inside will become unfiled.",
        )
        if confirm != QMessageBox.Yes:
            return
        # detach snippets first so they aren't cascade-deleted… actually our
        # schema sets folder_id to NULL on folder delete, so we can just delete.
        self.db.delete_folder(self._active_folder_id)
        self._active_folder_id = None
        self.prefs["active_folder_id"] = None
        config.save_prefs(self.prefs)
        self._reload_folders()
        self._reload_folder_combo()
        self._reload_snippets()

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

    def _toggle_theme(self) -> None:
        new_theme = "light" if self.prefs["theme"] == "dark" else "dark"
        self.prefs["theme"] = new_theme
        config.save_prefs(self.prefs)
        QApplication.instance().setStyleSheet(theme.build_stylesheet(new_theme))
        self._theme_btn.setText("☾" if new_theme == "dark" else "☼")
        # tag pills bake colors in their stylesheet — rebuild them
        self._reload_tag_bar()
        if self._current_snippet is not None:
            self._rebuild_editor_tag_pills(self._current_snippet.tags)

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

    def _export_dialog(self) -> None:
        if self._snippet_list.count() == 0:
            QMessageBox.information(self, "Nothing to export", "No snippets in the current view.")
            return
        fmt, ok = QInputDialog.getItem(
            self, "Export", "Format:",
            ["Markdown (.md)", "Plain text (.txt)", "CSV (.csv)"], 0, False,
        )
        if not ok:
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

        # collect snippets currently visible in the list
        ids = [self._snippet_list.item(i).data(Qt.UserRole) for i in range(self._snippet_list.count())]
        snippets = [self.db.get_snippet(int(i)) for i in ids]
        snippets = [s for s in snippets if s is not None]

        if fmt.startswith("Markdown"):
            n = io_formats.export_markdown(self.db, snippets, dest_path)
        elif fmt.startswith("Plain text"):
            n = io_formats.export_plaintext(self.db, snippets, dest_path)
        else:
            n = io_formats.export_csv(self.db, snippets, dest_path / "simplesave-export.csv")

        QMessageBox.information(
            self, "Export complete",
            f"Exported {n} snippet(s) to:\n{dest_path}",
        )

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
