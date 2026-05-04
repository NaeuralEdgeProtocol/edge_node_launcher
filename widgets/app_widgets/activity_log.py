from PyQt5 import sip
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QHBoxLayout,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


DEFAULT_ACTIVITY_LOG_MAX_BLOCKS = 1000


class ActivityLogWidget(QWidget):
    """Dashboard activity log with stable automation targets."""

    def __init__(self, parent=None, max_blocks: int = DEFAULT_ACTIVITY_LOG_MAX_BLOCKS):
        super().__init__(parent)
        self.setObjectName("activityLogPanel")
        self.setProperty("role", "activityLogPanel")
        self.setAccessibleName("Activity log")

        self.header = self._create_header()
        self.title_label = self._create_section_title()
        self.copy_button = self._create_action_button(
            "activityLogCopyButton",
            "Copy activity log",
            "Copy activity log to clipboard",
            "edit-copy",
            QStyle.SP_FileDialogDetailedView,
        )
        self.clear_button = self._create_action_button(
            "activityLogClearButton",
            "Clear activity log",
            "Clear activity log",
            "edit-clear",
            QStyle.SP_DialogDiscardButton,
        )
        self.log_view = self._create_log_view(max_blocks)

        self._init_layout()
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.clear_button.clicked.connect(self.clear_log)
        self.update_actions()

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("activityLogHeader")
        header.setProperty("role", "activityLogHeader")
        return header

    def _create_section_title(self) -> QLabel:
        label = QLabel("Activity Log")
        label.setObjectName("activityLogTitle")
        label.setProperty("role", "dashboardSectionTitle")
        label.setAccessibleName("Activity log section")
        label.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        label.setMinimumHeight(24)
        return label

    def _create_action_button(
        self,
        object_name: str,
        accessible_name: str,
        tooltip: str,
        theme_icon_name: str,
        fallback_icon,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setProperty("role", "activityLogToolButton")
        button.setAccessibleName(accessible_name)
        button.setToolTip(tooltip)
        button.setIcon(
            QIcon.fromTheme(theme_icon_name, self.style().standardIcon(fallback_icon))
        )
        button.setAutoRaise(False)
        button.setFixedSize(30, 30)
        return button

    def _create_log_view(self, max_blocks: int) -> QTextEdit:
        log_view = QTextEdit()
        log_view.setObjectName("logView")
        log_view.setAccessibleName("Activity log output")
        log_view.setReadOnly(True)
        log_view.setMinimumHeight(120)
        log_view.setLineWrapMode(QTextEdit.WidgetWidth)
        log_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        log_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        log_view.document().setMaximumBlockCount(max_blocks)
        log_view.setFont(QFont("Courier New"))
        return log_view

    def _init_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.copy_button)
        header_layout.addWidget(self.clear_button)

        layout.addWidget(self.header)
        layout.addWidget(self.log_view)

    def text(self) -> str:
        return self.log_view.toPlainText()

    def append_log_line(self, line: str, schedule_scroll: bool = True) -> None:
        document = self.log_view.document()
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.End)
        if not document.isEmpty():
            cursor.insertBlock()
        cursor.insertText(line)

        visible_cursor = QTextCursor(document)
        visible_cursor.movePosition(QTextCursor.End)
        visible_cursor.movePosition(QTextCursor.StartOfLine)
        self.log_view.setTextCursor(visible_cursor)
        self.update_actions()
        if schedule_scroll:
            self.schedule_scroll_to_latest()

    def schedule_scroll_to_latest(self) -> None:
        log_view = self.log_view

        def scroll_to_latest() -> None:
            if not sip.isdeleted(log_view):
                log_view.ensureCursorVisible()

        QTimer.singleShot(0, scroll_to_latest)

    def update_actions(self) -> None:
        has_log_text = bool(self.text().strip())
        self.copy_button.setEnabled(has_log_text)
        self.clear_button.setEnabled(has_log_text)

    def copy_to_clipboard(self) -> None:
        text = self.text()
        if text:
            QApplication.clipboard().setText(text)

    def clear_log(self) -> None:
        self.log_view.clear()
        self.update_actions()
