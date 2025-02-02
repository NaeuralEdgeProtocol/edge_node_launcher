from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation
from enum import Enum
from typing import Dict, Any

from utils.const import NOTIFICATION_TITLE_STRINGS_ENUM


class NotificationType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ToastWidget(QWidget):
    STYLES = {
        NotificationType.SUCCESS: {
            "bg_color": "#28A745",
            "icon": "✓",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['success'],
            "icon_color": "#4CAF50"
        },
        NotificationType.ERROR: {
            "bg_color": "#DC3545",
            "icon": "✗",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['error'],
            "icon_color": "#FF5252"
        },
        NotificationType.WARNING: {
            "bg_color": "#FFC107",
            "icon": "⚠",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['warning'],
            "icon_color": "#FFD740"
        },
        NotificationType.INFO: {
            "bg_color": "#17A2B8",
            "icon": "ℹ",
            "title": NOTIFICATION_TITLE_STRINGS_ENUM['info'],
            "icon_color": "#40C4FF"
        }
    }

    def __init__(self, parent=None, bottom_margin=20):
        super().__init__(parent)
        self.bottom_margin = bottom_margin
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.raise_()  # Bring to front
        self.fade_animation = None
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        self.icon = QLabel()
        self.icon.setObjectName("icon")
        self.title = QLabel()
        self.title.setObjectName("title")

        header.addWidget(self.icon)
        header.addWidget(self.title)
        header.addStretch()

        self.message = QLabel()
        self.message.setWordWrap(True)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addLayout(header)
        container_layout.addWidget(self.message)
        layout.addWidget(container)

    def _update_style(self, notification_type: NotificationType):
        style = self.STYLES[notification_type]
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {style['bg_color']};
                border-radius: 8px;
                color: white;
            }}
            QLabel {{
                padding: 4px;
                font-size: 13px;
            }}
            #icon {{
                color: {style['icon_color']};
                font-size: 16px;
                font-weight: bold;
            }}
            #title {{
                font-weight: bold;
                color: #FFFFFF;
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
        self.adjustSize()
        self._position_toast()
        self._start_fade_in(duration)


    def _position_toast(self):
        parent_rect = self.parentWidget().rect()
        x = parent_rect.width() - self.width() - 20
        y = parent_rect.height() - self.height() - self.bottom_margin
        self.move(x, y)

    def _start_fade_in(self, duration: int):
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setDuration(200)

        self.show()
        self.fade_animation.start()
        QTimer.singleShot(duration, self._fade_out)

    def _fade_out(self):
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setDuration(200)
        self.fade_animation.finished.connect(self._on_fade_out_finished)
        self.fade_animation.start()

    def _on_fade_out_finished(self):
        self.hide()
        self.fade_animation = None