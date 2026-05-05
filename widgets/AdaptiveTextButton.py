from __future__ import annotations

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtWidgets import QPushButton


_COMPACT_LABELS = {
    "Start Edge Node": "Start Node",
    "Stop Edge Node": "Stop Node",
    "Change Node Alias": "Rename Node",
    "Refresh Node Info": "Refresh",
    "Switch to Light Theme": "Light Theme",
    "Switch to Dark Theme": "Dark Theme",
    "Download Docker": "Docker",
    "Create Anyway": "Create",
    "Add New Address": "Add Address",
    "No Container Found": "No Node",
    "Docker Not Found": "No Docker",
    "Docker Not Running": "Docker Off",
    "Docker Check Failed": "Docker Failed",
    "Container Check Failed": "Check Failed",
    "Connection Failed": "Offline",
}


class AdaptiveTextButton(QPushButton):
    """A QPushButton that avoids silently clipping action text at narrow widths."""

    TEXT_HORIZONTAL_INSET = 24

    def __init__(self, text: str = "", parent=None, *, compact_text: str | None = None):
        self._updating_display_text = False
        self._full_text = text
        self._compact_text = compact_text
        super().__init__(text, parent)
        self._sync_text_properties()

    def setText(self, text: str) -> None:
        if not getattr(self, "_updating_display_text", False):
            self._full_text = text
            self._compact_text = None
        super().setText(text)
        if not getattr(self, "_updating_display_text", False):
            self._sync_text_properties()
            self._update_display_text()

    def full_text(self) -> str:
        return self._full_text

    def set_compact_text(self, compact_text: str | None) -> None:
        self._compact_text = compact_text
        self._update_display_text()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        full_text_width = self.fontMetrics().horizontalAdvance(self._full_text)
        return QSize(
            max(hint.width(), full_text_width + self.TEXT_HORIZONTAL_INSET + 10),
            hint.height(),
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_display_text()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_display_text()

    def _sync_text_properties(self) -> None:
        self.setProperty("fullText", self._full_text)
        self.setProperty("responsiveText", True)

    def _compact_label(self) -> str:
        if self._compact_text:
            return self._compact_text
        return _COMPACT_LABELS.get(self._full_text, self._full_text)

    def _available_text_width(self) -> int:
        icon_width = 0
        if not self.icon().isNull():
            icon_width = self.iconSize().width() + 6
        return max(8, self.contentsRect().width() - self.TEXT_HORIZONTAL_INSET - icon_width)

    def _fits(self, text: str, available_width: int) -> bool:
        return self.fontMetrics().horizontalAdvance(text) <= available_width

    def _update_display_text(self) -> None:
        if getattr(self, "_updating_display_text", False):
            return
        if self.width() <= 0:
            return

        available_width = self._available_text_width()
        full_text = self._full_text
        compact_text = self._compact_label()

        if self._fits(full_text, available_width):
            display_text = full_text
        elif compact_text != full_text and self._fits(compact_text, available_width):
            display_text = compact_text
        else:
            base_text = compact_text if compact_text != full_text else full_text
            display_text = self.fontMetrics().elidedText(base_text, Qt.ElideRight, available_width)

        if display_text == super().text():
            return

        self._updating_display_text = True
        try:
            super().setText(display_text)
        finally:
            self._updating_display_text = False
