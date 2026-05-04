from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel


class ElidedLabel(QLabel):
    """One-line label that renders elided text while preserving the full value."""

    def __init__(self, text="", *, elide_mode=Qt.ElideRight, compact_prefix=None, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._elide_mode = elide_mode
        self._compact_prefix = compact_prefix
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._update_display_text()

    def text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display_text()

    def _update_display_text(self):
        available_width = max(24, self.contentsRect().width() - 4)
        font_metrics = self.fontMetrics()
        if self._compact_prefix is not None:
            full_prefix, compact_prefix = self._compact_prefix
            if self._full_text.startswith(full_prefix):
                value_text = self._full_text[len(full_prefix):].replace("% used)", "%)")
                prefix_width = font_metrics.horizontalAdvance(compact_prefix)
                value_width = max(24, available_width - prefix_width)
                display_text = compact_prefix + font_metrics.elidedText(
                    value_text,
                    self._elide_mode,
                    value_width,
                )
                QLabel.setText(self, display_text)
                return

        display_text = font_metrics.elidedText(
            self._full_text,
            self._elide_mode,
            available_width,
        )
        QLabel.setText(self, display_text)
