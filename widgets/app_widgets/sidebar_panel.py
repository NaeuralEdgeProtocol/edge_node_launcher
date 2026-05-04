from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QCheckBox, QSizePolicy, QVBoxLayout, QWidget

from utils.const import (
    ADD_NODE_TOOLTIP,
    DAPP_BUTTON_TEXT,
    DAPP_TOOLTIP,
    DOCKER_DOWNLOAD_TOOLTIP,
    DOWNLOAD_DOCKER_BUTTON_TEXT,
    EXPLORER_BUTTON_TEXT,
    EXPLORER_TOOLTIP,
    FORCE_DEBUG_TOOLTIP,
    LAUNCH_CONTAINER_BUTTON_TEXT,
    LIGHT_DASHBOARD_BUTTON_TEXT,
    REFRESH_NODE_INFO_TOOLTIP,
    RENAME_NODE_BUTTON_TEXT,
    RENAME_NODE_TOOLTIP,
    THEME_TOGGLE_TOOLTIP,
    TOGGLE_NODE_TOOLTIP,
)
from widgets.CenteredComboBox import CenteredComboBox
from widgets.app_widgets.sidebar_controls import create_sidebar_action_button, create_sidebar_section_label
from widgets.app_widgets.sidebar_status_cards import NodeStatusPanel, ResourceStatusPanel


class SidebarPanel(QWidget):
    """Main launcher sidebar content with stable automation targets."""

    def __init__(
        self,
        *,
        is_dark: bool,
        force_debug: bool,
        add_node_handler,
        container_selected_handler,
        rename_handler,
        toggle_handler,
        docker_download_handler,
        dapp_handler,
        explorer_handler,
        refresh_handler,
        copy_address_handler,
        copy_eth_handler,
        theme_toggle_handler,
        force_debug_handler,
        parent=None,
    ):
        super().__init__(parent)
        self._is_dark = is_dark
        self._force_debug = force_debug
        self._add_node_handler = add_node_handler
        self._container_selected_handler = container_selected_handler
        self._rename_handler = rename_handler
        self._toggle_handler = toggle_handler
        self._docker_download_handler = docker_download_handler
        self._dapp_handler = dapp_handler
        self._explorer_handler = explorer_handler
        self._refresh_handler = refresh_handler
        self._copy_address_handler = copy_address_handler
        self._copy_eth_handler = copy_eth_handler
        self._theme_toggle_handler = theme_toggle_handler
        self._force_debug_handler = force_debug_handler

        self._init_layout()

    def _init_layout(self) -> None:
        self.setObjectName("sidebarPanel")
        self.setProperty("role", "navigationSidebar")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        menu_layout = QVBoxLayout(self)
        menu_layout.setAlignment(Qt.AlignTop)
        menu_layout.setContentsMargins(0, 2, 8, 2)

        top_button_area = self._create_top_section()
        menu_layout.addLayout(top_button_area)
        menu_layout.addSpacing(10)
        menu_layout.addLayout(self._create_settings_section())

    def _create_top_section(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setObjectName("topButtonArea")
        layout.setContentsMargins(5, 0, 8, 4)
        layout.addWidget(create_sidebar_section_label("Node", "nodeControlsSectionLabel"))

        container_selector_layout = QVBoxLayout()
        self.add_node_button = create_sidebar_action_button(
            "Add New Node",
            "addNodeButton",
            "secondary",
            ADD_NODE_TOOLTIP,
            self._add_node_handler,
        )
        container_selector_layout.addWidget(self.add_node_button)

        self.container_combo = CenteredComboBox()
        self.container_combo.setObjectName("nodeSelectorCombo")
        self.container_combo.setAccessibleName("Node selector")
        self.container_combo.setToolTip("Select active node")
        self.container_combo.setFont(QFont("Courier New", 10))
        self.container_combo.currentTextChanged.connect(self._container_selected_handler)
        self.container_combo.setMinimumHeight(36)
        self.container_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if hasattr(self.container_combo, "set_theme"):
            self.container_combo.set_theme(self._is_dark)
        container_selector_layout.addWidget(self.container_combo)

        layout.addLayout(container_selector_layout)

        self.renameNodeButton = create_sidebar_action_button(
            RENAME_NODE_BUTTON_TEXT,
            "renameNodeButton",
            "secondary",
            RENAME_NODE_TOOLTIP,
            self._rename_handler,
        )
        layout.addWidget(self.renameNodeButton)

        self.toggleButton = create_sidebar_action_button(
            LAUNCH_CONTAINER_BUTTON_TEXT,
            "startNodeButton",
            "primary",
            TOGGLE_NODE_TOOLTIP,
            self._toggle_handler,
        )
        layout.addWidget(self.toggleButton)

        layout.addWidget(create_sidebar_section_label("Network", "networkActionsSectionLabel"))

        self.docker_download_button = create_sidebar_action_button(
            DOWNLOAD_DOCKER_BUTTON_TEXT,
            "downloadDockerButton",
            "secondary",
            DOCKER_DOWNLOAD_TOOLTIP,
            self._docker_download_handler,
        )
        layout.addWidget(self.docker_download_button)

        self.dapp_button = create_sidebar_action_button(
            DAPP_BUTTON_TEXT,
            "openDappButton",
            "secondary",
            DAPP_TOOLTIP,
            self._dapp_handler,
        )
        layout.addWidget(self.dapp_button)

        self.explorer_button = create_sidebar_action_button(
            EXPLORER_BUTTON_TEXT,
            "openExplorerButton",
            "secondary",
            EXPLORER_TOOLTIP,
            self._explorer_handler,
        )
        layout.addWidget(self.explorer_button)

        layout.addSpacing(7)
        layout.addWidget(create_sidebar_section_label("Status", "statusSectionLabel"))

        self.refreshButton = create_sidebar_action_button(
            "Refresh Node Info",
            "refreshNodeInfoButton",
            "secondary",
            REFRESH_NODE_INFO_TOOLTIP,
            self._refresh_handler,
        )
        layout.addWidget(self.refreshButton)

        layout.addSpacing(7)
        self.node_status_panel = NodeStatusPanel(
            self._copy_address_handler,
            self._copy_eth_handler,
            parent=self,
        )
        layout.addWidget(self.node_status_panel)
        layout.addSpacing(7)
        self.resource_status_panel = ResourceStatusPanel(parent=self)
        layout.addWidget(self.resource_status_panel)

        return layout

    def _create_settings_section(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setObjectName("bottomButtonArea")
        layout.setContentsMargins(5, 4, 8, 0)
        layout.addWidget(create_sidebar_section_label("Settings", "settingsSectionLabel"))

        self.themeToggleButton = create_sidebar_action_button(
            LIGHT_DASHBOARD_BUTTON_TEXT,
            "themeToggleButton",
            "utility",
            THEME_TOGGLE_TOOLTIP,
            self._theme_toggle_handler,
        )
        layout.addWidget(self.themeToggleButton)

        self.force_debug_checkbox = QCheckBox("Force Debug Mode")
        self.force_debug_checkbox.setObjectName("forceDebugCheckbox")
        self.force_debug_checkbox.setProperty("role", "settingsToggle")
        self.force_debug_checkbox.setAccessibleName("Force Debug Mode")
        self.force_debug_checkbox.setToolTip(FORCE_DEBUG_TOOLTIP)
        self.force_debug_checkbox.setChecked(self._force_debug)
        self.force_debug_checkbox.setFont(QFont("Segoe UI", 9, QFont.Medium))
        self.force_debug_checkbox.setMinimumHeight(32)
        self.force_debug_checkbox.stateChanged.connect(self._force_debug_handler)
        layout.addWidget(self.force_debug_checkbox)

        return layout
