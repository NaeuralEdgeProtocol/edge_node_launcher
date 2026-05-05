import webbrowser
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QLabel, QWidget, QSizePolicy)
from PyQt5.QtCore import Qt

from utils.const import DARK_STYLESHEET
from utils.screen_geometry import available_screen_geometry
from widgets.AdaptiveTextButton import AdaptiveTextButton

class DockerCheckDialog(QDialog):
    def __init__(self, parent=None, icon=None):
        super().__init__(parent)
        self.setWindowTitle("Docker Check")
        self.setObjectName("dockerCheckDialog")
        self.setAccessibleName("Docker Check")
        if icon:
            self.setWindowIcon(icon)
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(460)
        self._has_centered = False
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(14)
        
        # Message label
        self.message = QLabel(
            'Docker is not installed or not running.\n'
            'Please install Docker and start it to continue.'
        )
        self.message.setObjectName("dockerCheckMessageLabel")
        self.message.setAccessibleName("Docker status message")
        self.message.setWordWrap(True)
        self.message.setMinimumWidth(380)
        layout.addWidget(self.message)
        
        # Button layout
        self.button_row = QWidget()
        self.button_row.setObjectName("dockerCheckButtonRow")
        self.button_row.setAccessibleName("Docker check actions")
        button_layout = QHBoxLayout(self.button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        # Download Docker button - apply toggle_button_start styles
        self.download_button = AdaptiveTextButton('Download Docker', compact_text='Docker')
        self.download_button.setObjectName("dockerCheckDownloadButton")
        self.download_button.setAccessibleName("Download Docker")
        self.download_button.setToolTip("Open Docker Desktop download page")
        self.download_button.clicked.connect(self.open_docker_download)
        self.download_button.setProperty("type", "toggle_button_start")
        self.download_button.setProperty("actionRole", "primary")
        self._prepare_button(self.download_button)
        button_layout.addWidget(self.download_button)
        
        # Try Again button - apply toggle_button_start styles
        self.retry_button = AdaptiveTextButton('Try Again')
        self.retry_button.setObjectName("dockerCheckRetryButton")
        self.retry_button.setAccessibleName("Try Docker check again")
        self.retry_button.setToolTip("Check Docker again")
        self.retry_button.setProperty("type", "toggle_button_start")
        self.retry_button.setProperty("actionRole", "secondary")
        self._prepare_button(self.retry_button)
        self.retry_button.clicked.connect(self.accept)
        button_layout.addWidget(self.retry_button)
        
        # Quit button - explicitly using toggle_button_stop styles
        self.quit_button = AdaptiveTextButton('Quit')
        self.quit_button.setObjectName("dockerCheckQuitButton")
        self.quit_button.setAccessibleName("Quit launcher")
        self.quit_button.setToolTip("Close the launcher")
        # Set the property to use toggle_button_stop styles
        self.quit_button.setProperty("type", "toggle_button_stop")
        self.quit_button.setProperty("actionRole", "destructive")
        self._prepare_button(self.quit_button)
        self.quit_button.clicked.connect(self.reject)
        button_layout.addWidget(self.quit_button)
        
        layout.addWidget(self.button_row)
        self.setLayout(layout)
        
        # Apply base dialog styling with system colors
        is_dark = parent and getattr(parent, "_current_stylesheet", "") == DARK_STYLESHEET
        dialog_bg = "#122033" if is_dark else "#FFFFFF"
        text_color = "#E8EEF8" if is_dark else "#1F2937"
        secondary_bg = "#1E293B" if is_dark else "#F8FAFC"
        secondary_border = "#334155" if is_dark else "#CBD5E1"
        secondary_hover = "#24324A" if is_dark else "#EEF2F7"

        self.setStyleSheet(f"""
            QDialog#dockerCheckDialog {{
                background-color: {dialog_bg};
                color: {text_color};
                border: none;
                border-radius: 8px;
            }}
            QLabel#dockerCheckMessageLabel {{
                background-color: transparent;
                color: {text_color};
                font-size: 13px;
            }}
            QPushButton[actionRole="primary"],
            QPushButton[actionRole="secondary"],
            QPushButton[actionRole="destructive"] {{
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
                font-weight: 600;
                min-height: 24px;
            }}
            QPushButton[actionRole="primary"] {{
                background-color: #1B47F7;
                color: white;
                border: 1px solid transparent;
            }}
            QPushButton[actionRole="primary"]:hover {{
                background-color: #4458FF;
            }}
            QPushButton[actionRole="secondary"] {{
                background-color: {secondary_bg};
                color: {text_color};
                border: 1px solid {secondary_border};
            }}
            QPushButton[actionRole="secondary"]:hover {{
                background-color: {secondary_hover};
            }}
            QPushButton[actionRole="destructive"] {{
                background-color: #FADC33 !important;
                color: #1F2937;
                border: 1px solid transparent;
            }}
            QPushButton[actionRole="destructive"]:hover {{
                background-color: #FFE138 !important;
            }}
        """)
        
        self.adjustSize()
        self._center_on_parent_or_screen()

    def _prepare_button(self, button):
        button.setMinimumHeight(44)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def open_docker_download(self):
        """Open the Docker download page in the default browser."""
        webbrowser.open('https://www.docker.com/products/docker-desktop')

    def _center_on_parent_or_screen(self):
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            center_point = parent.frameGeometry().center()
        else:
            center_point = available_screen_geometry(parent or self).center()

        frame = self.frameGeometry()
        frame.moveCenter(center_point)
        self.move(frame.topLeft())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_centered:
            self._center_on_parent_or_screen()
            self._has_centered = True
