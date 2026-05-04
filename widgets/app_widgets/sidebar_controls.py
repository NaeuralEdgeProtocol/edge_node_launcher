from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLabel, QPushButton, QSizePolicy


def create_sidebar_section_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setAccessibleName(f"{text} section")
    label.setProperty("role", "sidebarSection")
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
    label.setMinimumHeight(30)
    return label


def create_sidebar_action_button(
    text: str,
    object_name: str,
    action_role: str,
    tooltip: str,
    handler,
) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(object_name)
    button.setProperty("actionRole", action_role)
    button.setToolTip(tooltip)
    button.setAccessibleName(text)
    button.setMinimumWidth(0)
    button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    button.clicked.connect(handler)
    return button
