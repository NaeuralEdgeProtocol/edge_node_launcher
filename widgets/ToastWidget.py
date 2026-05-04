from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation
from enum import Enum

from utils.const import NOTIFICATION_TITLE_STRINGS_ENUM


class NotificationType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ToastWidget(QWidget):
    EDGE_MARGIN = 20
    MIN_VISIBLE_WIDTH = 220
    MIN_VISIBLE_HEIGHT = 96
    MIN_WIDTH = 320
    MAX_WIDTH = 460
    CONTENT_MARGIN_X = 16
    CONTENT_MARGIN_Y = 14
    MAX_WIDGET_SIZE = 16777215

    STYLES = {
        NotificationType.SUCCESS: {
            "bg_color": "#28A745",
            "icon": "OK",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['success'],
            "icon_color": "#FFFFFF",
            "text_color": "#FFFFFF",
        },
        NotificationType.ERROR: {
            "bg_color": "#DC3545",
            "icon": "X",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['error'],
            "icon_color": "#FFFFFF",
            "text_color": "#FFFFFF",
        },
        NotificationType.WARNING: {
            "bg_color": "#FFC107",
            "icon": "!",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['warning'],
            "icon_color": "#1F2937",
            "text_color": "#1F2937",
        },
        NotificationType.INFO: {
            "bg_color": "#17A2B8",
            "icon": "i",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['info'],
            "icon_color": "#FFFFFF",
            "text_color": "#FFFFFF",
        }
    }

    def __init__(self, parent=None, bottom_margin=20):
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setAccessibleName("Notification")
        self.bottom_margin = bottom_margin
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.raise_()  # Bring to front
        self.fade_animation = None
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self._fade_out)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        self.icon = QLabel()
        self.icon.setObjectName("toastIcon")
        self.icon.setAccessibleName("Notification type")
        self.icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.title = QLabel()
        self.title.setObjectName("toastTitle")
        self.title.setAccessibleName("Notification title")
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        header.setSpacing(8)
        self.icon.setFixedWidth(28)
        self.title.setMinimumWidth(180)
        header.addWidget(self.icon)
        header.addWidget(self.title)
        header.addStretch()

        self.message = QLabel()
        self.message.setObjectName("toastMessage")
        self.message.setAccessibleName("Notification message")
        self.message.setWordWrap(True)
        self.message.setMinimumWidth(260)
        self.message.setMaximumWidth(self.MAX_WIDTH - (self.CONTENT_MARGIN_X * 2))
        self.message.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.container = QWidget()
        self.container.setObjectName("toastContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(
            self.CONTENT_MARGIN_X,
            self.CONTENT_MARGIN_Y,
            self.CONTENT_MARGIN_X,
            self.CONTENT_MARGIN_Y,
        )
        container_layout.setSpacing(6)
        container_layout.addLayout(header)
        container_layout.addWidget(self.message)
        layout.addWidget(self.container)

    def _update_style(self, notification_type: NotificationType):
        style = self.STYLES[notification_type]
        self.setStyleSheet(f"""
            QWidget#toastContainer {{
                background-color: {style['bg_color']};
                border-radius: 8px;
                color: {style['text_color']};
            }}
            QLabel#toastIcon,
            QLabel#toastTitle,
            QLabel#toastMessage {{
                background: transparent;
                padding: 0;
                font-size: 13px;
                color: {style['text_color']};
            }}
            QLabel#toastIcon {{
                color: {style['icon_color']};
                font-size: 16px;
                font-weight: bold;
            }}
            QLabel#toastTitle {{
                font-weight: bold;
                color: {style['text_color']};
            }}
        """)

    def show_notification(self, notification_type: NotificationType, message: str, duration: int = 2000):
        self.raise_()  # Ensure toast is on top when shown
        style = self.STYLES[notification_type]
        self.icon.setText(style['icon'])
        self.title.setText(style['title'])
        self._update_style(notification_type)

        if self.fade_animation and self.fade_animation.state() == QPropertyAnimation.Running:
            self.fade_animation.stop()

        self.message.setText(message)
        self.message.setToolTip(message)
        self._fit_to_parent()
        self.adjustSize()
        self._position_toast()
        self._start_fade_in(duration)

    def _fit_to_parent(self):
        parent = self.parentWidget()
        if parent is None:
            self.setMinimumWidth(self.MIN_WIDTH)
            self.setMaximumWidth(self.MAX_WIDTH)
            self.setMaximumHeight(self.MAX_WIDGET_SIZE)
            self.message.setMaximumWidth(self.MAX_WIDTH - (self.CONTENT_MARGIN_X * 2))
            self.message.setMaximumHeight(self.MAX_WIDGET_SIZE)
            return

        parent_rect = parent.rect()
        available_width = max(
            self.MIN_VISIBLE_WIDTH,
            parent_rect.width() - (self.EDGE_MARGIN * 2),
        )
        target_width = min(self.MAX_WIDTH, available_width)
        self.setMinimumWidth(min(self.MIN_WIDTH, target_width))
        self.setMaximumWidth(target_width)
        self.message.setMaximumWidth(max(
            self.MIN_VISIBLE_WIDTH - (self.CONTENT_MARGIN_X * 2),
            target_width - (self.CONTENT_MARGIN_X * 2),
        ))

        available_height = parent_rect.height() - (self.EDGE_MARGIN * 2)
        if available_height <= 0:
            self.setMaximumHeight(self.MIN_VISIBLE_HEIGHT)
            self.message.setMaximumHeight(self.MIN_VISIBLE_HEIGHT)
            return

        target_height = max(self.MIN_VISIBLE_HEIGHT, available_height)
        header_height = max(self.title.sizeHint().height(), self.icon.sizeHint().height())
        message_height = max(
            32,
            target_height - (self.CONTENT_MARGIN_Y * 2) - header_height - 6,
        )
        self.setMaximumHeight(target_height)
        self.message.setMaximumHeight(message_height)

    def _position_toast(self):
        if self.parentWidget() is None:
            return

        parent_rect = self.parentWidget().rect()
        desired_x = parent_rect.width() - self.width() - self.EDGE_MARGIN
        desired_y = parent_rect.height() - self.height() - self.bottom_margin
        max_x = max(0, parent_rect.width() - self.width() - self.EDGE_MARGIN)
        max_y = max(0, parent_rect.height() - self.height() - self.EDGE_MARGIN)
        min_x = min(self.EDGE_MARGIN, max_x)
        min_y = min(self.EDGE_MARGIN, max_y)
        x = min(max(desired_x, min_x), max_x)
        y = min(max(desired_y, min_y), max_y)
        self.move(x, y)

    def _start_fade_in(self, duration: int):
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setDuration(200)

        self.show()
        self.fade_animation.start()
        self.dismiss_timer.stop()
        self.dismiss_timer.start(max(0, duration))

    def _fade_out(self):
        self.dismiss_timer.stop()
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setDuration(200)
        self.fade_animation.finished.connect(self._on_fade_out_finished)
        self.fade_animation.start()

    def _on_fade_out_finished(self):
        self.hide()
        self.fade_animation = None
