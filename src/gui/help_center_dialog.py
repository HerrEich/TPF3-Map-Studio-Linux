"""Hilfe-Fenster: Inhaltsverzeichnis links, Kapitel rechts (Hilfe > Anleitungen)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLineEdit, QSplitter, QTextBrowser, QTreeWidget, QWidget,
    QTreeWidgetItem, QVBoxLayout,
)

from src import help_content
from src.i18n import get_language, tr


class HelpCenterDialog(QDialog):

    def __init__(self, parent=None, start_id: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Anleitungen"))
        self.resize(1000, 680)

        self._language = get_language()
        self._pages = help_content.load_index(self._language)
        self._items: dict[str, QTreeWidgetItem] = {}

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("Suchen..."))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.currentItemChanged.connect(self._on_item_changed)

        left = QVBoxLayout()
        left.addWidget(self._search)
        left.addWidget(self._tree)
        left_box = QWidget()
        left_box.setLayout(left)

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_link)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_box)
        splitter.addWidget(self._browser)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 720])

        layout = QHBoxLayout(self)
        layout.addWidget(splitter)

        self._fill_tree(self._pages)
        first = start_id if start_id in self._items else self._pages[0].id
        self.show_page(first)

    def _fill_tree(self, pages, parent=None, visible=None):
        for page in pages:
            if visible is not None and page.id not in visible:
                continue
            item = QTreeWidgetItem([page.title])
            item.setData(0, Qt.UserRole, page.id)
            if parent is None:
                self._tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            self._items[page.id] = item
            self._fill_tree(page.children, item, visible)
            item.setExpanded(True)

    def show_page(self, page_id: str):
        item = self._items.get(page_id)
        if item is None:
            return
        self._tree.setCurrentItem(item)

    def _on_item_changed(self, current, _previous):
        if current is None:
            return
        page = help_content.find_page(self._pages, current.data(0, Qt.UserRole))
        if page is not None:
            self._browser.setMarkdown(help_content.read_page(page, self._language))

    def _on_link(self, url: QUrl):
        if url.scheme() == "help":
            self.show_page(url.path() or url.host())
        elif url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)

    def _on_search(self, text: str):
        hits = {p.id for p in help_content.search(self._pages, text, self._language)}
        self._tree.clear()
        self._items = {}
        flat = text.strip() != ""
        if flat:
            for page in help_content.flatten(self._pages):
                if page.id in hits:
                    item = QTreeWidgetItem([page.title])
                    item.setData(0, Qt.UserRole, page.id)
                    self._tree.addTopLevelItem(item)
                    self._items[page.id] = item
        else:
            self._fill_tree(self._pages)
        if self._items:
            self._tree.setCurrentItem(next(iter(self._items.values())))
