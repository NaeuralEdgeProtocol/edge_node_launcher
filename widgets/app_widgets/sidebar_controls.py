from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLabel, QPushButton, QSizePolicy

SIDEBAR_SECTION_LABEL_HEIGHT = 24
SIDEBAR_ACTION_BUTTON_HEIGHTS = {
    "primary": 48,
    "secondary": 50,
    "utility": 48,
}


def create_sidebar_section_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setAccessibleName(f"{text} section")
    label.setProperty("role", "sidebarSection")
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
    label.setMinimumHeight(SIDEBAR_SECTION_LABEL_HEIGHT)
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
    button_height = SIDEBAR_ACTION_BUTTON_HEIGHTS.get(
        action_role,
        SIDEBAR_ACTION_BUTTON_HEIGHTS["secondary"],
    )
    button.setMinimumHeight(button_height)
    button.setMaximumHeight(button_height)
    button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    button.clicked.connect(handler)
    return button
