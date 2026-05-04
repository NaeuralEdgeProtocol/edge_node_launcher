from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
    """Left navigation shell with contextual launcher control pages."""

    NAV_ITEMS = (
        ("nodes", "Nodes", "navNodesButton", QStyle.SP_ComputerIcon),
        ("apps", "Apps", "navAppsButton", QStyle.SP_FileDialogContentsView),
        ("logs", "Logs", "navLogsButton", QStyle.SP_FileDialogDetailedView),
        ("docker", "Docker", "navDockerButton", QStyle.SP_DriveHDIcon),
        ("settings", "Settings", "navSettingsButton", QStyle.SP_FileDialogDetailedView),
        ("network", "Network", "navNetworkButton", QStyle.SP_DriveNetIcon),
    )

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
        self._pages = {}
        self._nav_buttons = {}

        self._init_layout()

    def _init_layout(self) -> None:
        self.setObjectName("sidebarPanel")
        self.setProperty("role", "navigationSidebar")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 2, 8, 2)
        root_layout.setSpacing(8)
        root_layout.addWidget(self._create_navigation_rail())

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("launcherPageStack")
        self.page_stack.setAccessibleName("Launcher navigation pages")
        self.page_stack.setProperty("role", "navigationPageStack")
        self.page_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        root_layout.addWidget(self.page_stack, 1)

        self._add_page("nodes", self._create_nodes_page())
        self._add_page("apps", self._create_placeholder_page("Apps", "appsPage", "appsPageSectionLabel"))
        self._add_page("logs", self._create_placeholder_page("Logs", "logsPage", "logsPageSectionLabel"))
        self._add_page("docker", self._create_docker_page())
        self._add_page("settings", self._create_settings_page())
        self._add_page("network", self._create_network_page())
        self.show_page("nodes")

    def _create_navigation_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("navigationRail")
        rail.setAccessibleName("Launcher navigation")
        rail.setProperty("role", "navigationRail")
        rail.setFixedWidth(76)
        rail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        layout = QVBoxLayout(rail)
        layout.setObjectName("navigationRailLayout")
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(5)

        self.nav_button_group = QButtonGroup(self)
        self.nav_button_group.setExclusive(True)

        for page_name, text, object_name, icon_kind in self.NAV_ITEMS:
            button = self._create_nav_button(page_name, text, object_name, icon_kind)
            layout.addWidget(button)
            self.nav_button_group.addButton(button)
            self._nav_buttons[page_name] = button

        layout.addStretch(1)
        return rail

    def _create_nav_button(self, page_name: str, text: str, object_name: str, icon_kind) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setAccessibleName(f"{text} page")
        button.setToolTip(f"Show {text}")
        button.setText(text)
        button.setIcon(self.style().standardIcon(icon_kind))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setCheckable(True)
        button.setAutoRaise(False)
        button.setProperty("role", "navRailButton")
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setMinimumHeight(55)
        button.clicked.connect(lambda _checked=False, name=page_name: self.show_page(name))
        return button

    def _add_page(self, name: str, page: QWidget) -> None:
        self._pages[name] = page
        self.page_stack.addWidget(page)

    def show_page(self, name: str) -> None:
        page = self._pages.get(name)
        if page is None:
            return
        self.page_stack.setCurrentWidget(page)
        button = self._nav_buttons.get(name)
        if button is not None:
            button.setChecked(True)

    def current_page_name(self) -> str:
        current = self.page_stack.currentWidget()
        for name, page in self._pages.items():
            if page is current:
                return name
        return ""

    def _create_page(self, object_name: str) -> QWidget:
        page = QWidget()
        page.setObjectName(object_name)
        page.setAccessibleName(object_name.replace("Page", " page"))
        page.setProperty("role", "navigationPage")
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        return page

    def _create_nodes_page(self) -> QWidget:
        page = self._create_page("nodesPage")
        page_layout = QVBoxLayout(page)
        page_layout.setAlignment(Qt.AlignTop)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(5)

        top_button_area = QVBoxLayout()
        top_button_area.setObjectName("topButtonArea")
        top_button_area.setContentsMargins(0, 0, 0, 2)
        top_button_area.setSpacing(4)
        top_button_area.addWidget(create_sidebar_section_label("Node", "nodeControlsSectionLabel"))

        self.add_node_button = create_sidebar_action_button(
            "Add New Node",
            "addNodeButton",
            "secondary",
            ADD_NODE_TOOLTIP,
            self._add_node_handler,
        )
        top_button_area.addWidget(self.add_node_button)

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
        top_button_area.addWidget(self.container_combo)

        self.renameNodeButton = create_sidebar_action_button(
            RENAME_NODE_BUTTON_TEXT,
            "renameNodeButton",
            "secondary",
            RENAME_NODE_TOOLTIP,
            self._rename_handler,
        )
        top_button_area.addWidget(self.renameNodeButton)

        self.toggleButton = create_sidebar_action_button(
            LAUNCH_CONTAINER_BUTTON_TEXT,
            "startNodeButton",
            "primary",
            TOGGLE_NODE_TOOLTIP,
            self._toggle_handler,
        )
        top_button_area.addWidget(self.toggleButton)
        page_layout.addLayout(top_button_area)

        status_button_area = QVBoxLayout()
        status_button_area.setObjectName("statusButtonArea")
        status_button_area.setContentsMargins(0, 0, 0, 0)
        status_button_area.setSpacing(4)
        status_button_area.addWidget(create_sidebar_section_label("Status", "statusSectionLabel"))

        self.refreshButton = create_sidebar_action_button(
            "Refresh Node Info",
            "refreshNodeInfoButton",
            "secondary",
            REFRESH_NODE_INFO_TOOLTIP,
            self._refresh_handler,
        )
        status_button_area.addWidget(self.refreshButton)
        self.node_status_panel = NodeStatusPanel(
            self._copy_address_handler,
            self._copy_eth_handler,
            parent=self,
        )
        status_button_area.addWidget(self.node_status_panel)
        self.resource_status_panel = ResourceStatusPanel(parent=self)
        status_button_area.addWidget(self.resource_status_panel)
        page_layout.addLayout(status_button_area)

        return page

    def _create_docker_page(self) -> QWidget:
        page = self._create_page("dockerPage")
        layout = QVBoxLayout(page)
        layout.setObjectName("dockerButtonArea")
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(create_sidebar_section_label("Docker", "dockerSectionLabel"))

        self.docker_download_button = create_sidebar_action_button(
            DOWNLOAD_DOCKER_BUTTON_TEXT,
            "downloadDockerButton",
            "secondary",
            DOCKER_DOWNLOAD_TOOLTIP,
            self._docker_download_handler,
        )
        layout.addWidget(self.docker_download_button)
        layout.addStretch(1)
        return page

    def _create_settings_page(self) -> QWidget:
        page = self._create_page("settingsPage")
        layout = QVBoxLayout(page)
        layout.setObjectName("bottomButtonArea")
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
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
        layout.addStretch(1)
        return page

    def _create_network_page(self) -> QWidget:
        page = self._create_page("networkPage")
        layout = QVBoxLayout(page)
        layout.setObjectName("networkButtonArea")
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(create_sidebar_section_label("Network", "networkActionsSectionLabel"))

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
        layout.addStretch(1)
        return page

    def _create_placeholder_page(self, title: str, object_name: str, label_name: str) -> QWidget:
        page = self._create_page(object_name)
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(create_sidebar_section_label(title, label_name))

        placeholder = QLabel(title)
        placeholder.setObjectName(f"{object_name}PlaceholderLabel")
        placeholder.setAccessibleName(f"{title} placeholder")
        placeholder.setProperty("role", "pagePlaceholder")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setMinimumHeight(44)
        placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(placeholder)
        layout.addStretch(1)
        return page
