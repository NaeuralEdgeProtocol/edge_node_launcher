from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
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

from services.app_registry import AppRegistry
from services.sdk_error_messages import classify_sdk_error
from services.sdk_deployment_service import Ratio1SdkDeploymentClient
from services.sdk_identity_service import SdkIdentityService
from services.sdk_operation_worker import SdkOperationThread
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
from widgets.app_widgets.apps_page import AppsPage
from widgets.app_widgets.sidebar_controls import create_sidebar_action_button, create_sidebar_section_label
from widgets.app_widgets.sidebar_status_cards import NodeStatusPanel, ResourceStatusPanel


class CurrentPageStack(QStackedWidget):
    """QStackedWidget that sizes the sidebar from the active page only."""

    def sizeHint(self):
        current = self.currentWidget()
        return current.sizeHint() if current is not None else super().sizeHint()

    def minimumSizeHint(self):
        current = self.currentWidget()
        return current.minimumSizeHint() if current is not None else super().minimumSizeHint()


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
        page_changed_handler=None,
        sdk_identity_service=None,
        event_logger=None,
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
        self._page_changed_handler = page_changed_handler
        self._sdk_identity_service = sdk_identity_service or SdkIdentityService()
        self._event_logger = event_logger
        self._sdk_identity_worker = None
        self._sdk_identity_address = ""
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

        self.page_stack = CurrentPageStack()
        self.page_stack.setObjectName("launcherPageStack")
        self.page_stack.setAccessibleName("Launcher navigation pages")
        self.page_stack.setProperty("role", "navigationPageStack")
        self.page_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        root_layout.addWidget(self.page_stack, 1)

        self._add_page("nodes", self._create_nodes_page())
        self._add_page("apps", self._create_apps_page())
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
        self.page_stack.updateGeometry()
        button = self._nav_buttons.get(name)
        if button is not None:
            button.setChecked(True)
        if self._page_changed_handler is not None:
            self._page_changed_handler(name)

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

    def _create_apps_page(self) -> QWidget:
        app_registry = AppRegistry()
        deployment_client = Ratio1SdkDeploymentClient(app_registry=None)
        self.apps_page = AppsPage(
            app_registry=app_registry,
            deployment_client=deployment_client,
            parent=self,
        )
        self.apps_page.sdk_settings_requested.connect(lambda: self.show_page("settings"))
        page = self._create_page("appsSidebarPage")
        layout = QVBoxLayout(page)
        layout.setObjectName("appsSidebarPageLayout")
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(create_sidebar_section_label("Apps", "appsPageSectionLabel"))

        self.apps_workspace_label = QLabel("Deployment workspace")
        self.apps_workspace_label.setObjectName("appsWorkspaceSidebarLabel")
        self.apps_workspace_label.setAccessibleName("Apps workspace")
        self.apps_workspace_label.setProperty("role", "sidebarMutedText")
        self.apps_workspace_label.setWordWrap(True)
        layout.addWidget(self.apps_workspace_label)
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

        appearance_panel, appearance_layout = self._create_settings_panel(
            "settingsAppearancePanel",
            "Appearance settings",
        )
        appearance_layout.addWidget(self._create_settings_panel_title("Appearance", "settingsAppearanceTitle"))
        self.theme_state_label = self._create_settings_value_label("settingsThemeStateLabel")
        appearance_layout.addWidget(self.theme_state_label)
        self.themeToggleButton = create_sidebar_action_button(
            LIGHT_DASHBOARD_BUTTON_TEXT,
            "themeToggleButton",
            "utility",
            THEME_TOGGLE_TOOLTIP,
            self._theme_toggle_handler,
        )
        appearance_layout.addWidget(self.themeToggleButton)
        layout.addWidget(appearance_panel)

        diagnostics_panel, diagnostics_layout = self._create_settings_panel(
            "settingsDiagnosticsPanel",
            "Diagnostics settings",
        )
        diagnostics_layout.addWidget(self._create_settings_panel_title("Diagnostics", "settingsDiagnosticsTitle"))
        self.force_debug_checkbox = QCheckBox("Force Debug Mode")
        self.force_debug_checkbox.setObjectName("forceDebugCheckbox")
        self.force_debug_checkbox.setProperty("role", "settingsToggle")
        self.force_debug_checkbox.setAccessibleName("Force Debug Mode")
        self.force_debug_checkbox.setToolTip(FORCE_DEBUG_TOOLTIP)
        self.force_debug_checkbox.setChecked(self._force_debug)
        self.force_debug_checkbox.setFont(QFont("Segoe UI", 9, QFont.Medium))
        self.force_debug_checkbox.setMinimumHeight(32)
        self.force_debug_checkbox.stateChanged.connect(self._handle_force_debug_changed)
        diagnostics_layout.addWidget(self.force_debug_checkbox)
        self.force_debug_state_label = self._create_settings_value_label("settingsDebugStateLabel")
        diagnostics_layout.addWidget(self.force_debug_state_label)
        layout.addWidget(diagnostics_panel)

        sdk_panel, sdk_layout = self._create_settings_panel(
            "settingsSdkIdentityPanel",
            "SDK identity settings",
        )
        sdk_layout.addWidget(self._create_settings_panel_title("SDK Identity", "settingsSdkIdentityTitle"))
        sdk_layout.addWidget(self._create_sdk_identity_panel())
        layout.addWidget(sdk_panel)

        self.update_settings_state_labels()
        layout.addStretch(1)
        return page

    def _create_settings_panel(self, object_name: str, accessible_name: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setAccessibleName(accessible_name)
        panel.setProperty("role", "settingsPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        return panel, layout

    def _create_settings_panel_title(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(text)
        label.setProperty("role", "settingsPanelTitle")
        return label

    def _create_settings_value_label(self, object_name: str) -> QLabel:
        label = QLabel("")
        label.setObjectName(object_name)
        label.setAccessibleName(object_name.replace("settings", "Settings "))
        label.setProperty("role", "settingsValueText")
        label.setWordWrap(True)
        return label

    def update_settings_state_labels(self) -> None:
        if hasattr(self, "theme_state_label"):
            self.theme_state_label.setText("Dark theme active" if self._is_dark else "Light theme active")
        if hasattr(self, "force_debug_state_label"):
            self.force_debug_state_label.setText(
                "Debug logging is enabled for node container runs."
                if self.force_debug_checkbox.isChecked()
                else "Debug logging is disabled for node container runs."
            )

    def set_theme_state(self, is_dark: bool) -> None:
        self._is_dark = bool(is_dark)
        self.update_settings_state_labels()

    def _handle_force_debug_changed(self, state) -> None:
        self.update_settings_state_labels()
        self._force_debug_handler(state)

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

    def _create_sdk_identity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sdkIdentityPanel")
        panel.setAccessibleName("SDK identity settings")
        panel.setProperty("role", "sdkIdentityPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.sdk_identity_status_label = QLabel("Not loaded")
        self.sdk_identity_status_label.setObjectName("sdkIdentityStatusLabel")
        self.sdk_identity_status_label.setAccessibleName("SDK identity status")
        self.sdk_identity_status_label.setProperty("role", "sdkIdentityStatus")
        self.sdk_identity_status_label.setWordWrap(True)
        layout.addWidget(self.sdk_identity_status_label)

        fields = QGridLayout()
        fields.setObjectName("sdkIdentityFieldsLayout")
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setHorizontalSpacing(7)
        fields.setVerticalSpacing(3)
        fields.setColumnStretch(1, 1)

        self.sdk_identity_address_label = self._create_sdk_identity_field_label("Address", "sdkIdentityAddressLabel")
        self.sdk_identity_network_label = self._create_sdk_identity_field_label("Network", "sdkIdentityNetworkLabel")
        self.sdk_identity_cache_label = self._create_sdk_identity_field_label("Cache", "sdkIdentityCacheLabel")
        self._add_sdk_identity_field(fields, 0, "Address", self.sdk_identity_address_label)
        self._add_sdk_identity_field(fields, 1, "Network", self.sdk_identity_network_label)
        self._add_sdk_identity_field(fields, 2, "Cache", self.sdk_identity_cache_label)
        layout.addLayout(fields)

        actions = QHBoxLayout()
        actions.setObjectName("sdkIdentityActionsLayout")
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        self.refresh_sdk_identity_button = create_sidebar_action_button(
            "Refresh SDK",
            "refreshSdkIdentityButton",
            "secondary",
            "Load the launcher's Ratio1 SDK identity",
            self.refresh_sdk_identity,
        )
        self.copy_sdk_identity_address_button = create_sidebar_action_button(
            "Copy Address",
            "copySdkIdentityAddressButton",
            "utility",
            "Copy the launcher SDK address",
            self.copy_sdk_identity_address,
        )
        self.copy_sdk_identity_address_button.setEnabled(False)
        actions.addWidget(self.refresh_sdk_identity_button)
        actions.addWidget(self.copy_sdk_identity_address_button)
        layout.addLayout(actions)

        self._set_sdk_identity_placeholder()
        return panel

    def _create_sdk_identity_field_label(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(text)
        label.setProperty("role", "sdkIdentityField")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def _add_sdk_identity_field(self, layout: QGridLayout, row: int, name: str, value: QLabel) -> None:
        field_label = QLabel(name)
        field_label.setObjectName(f"sdkIdentity{name}FieldLabel")
        field_label.setAccessibleName(f"SDK identity {name.lower()} label")
        field_label.setProperty("role", "sdkIdentityFieldName")
        layout.addWidget(field_label, row, 0, Qt.AlignTop)
        layout.addWidget(value, row, 1)

    def _set_sdk_identity_placeholder(self) -> None:
        self._sdk_identity_address = ""
        self.sdk_identity_address_label.setText("-")
        self.sdk_identity_network_label.setText("-")
        self.sdk_identity_cache_label.setText("-")
        self.copy_sdk_identity_address_button.setEnabled(False)

    def refresh_sdk_identity(self) -> None:
        worker = self._sdk_identity_worker
        if worker is not None and worker.isRunning():
            return

        self._set_sdk_identity_loading(True)
        self._log_event("SDK identity refresh started", color="blue")
        worker = SdkOperationThread(
            "sdk_identity_refresh",
            self._sdk_identity_service.load_identity,
            parent=self,
        )
        self._sdk_identity_worker = worker
        worker.operation_finished.connect(
            lambda _name, result, item=worker: self._finish_sdk_identity_refresh(item, result)
        )
        worker.operation_failed.connect(
            lambda _name, error, item=worker: self._fail_sdk_identity_refresh(item, error)
        )
        worker.finished.connect(lambda item=worker: self._cleanup_sdk_identity_worker(item))
        worker.start()

    def _set_sdk_identity_loading(self, is_loading: bool) -> None:
        self.refresh_sdk_identity_button.setEnabled(not is_loading)
        self.copy_sdk_identity_address_button.setEnabled(False if is_loading else bool(self._sdk_identity_address))
        if is_loading:
            self.sdk_identity_status_label.setText("Loading SDK identity...")

    def _finish_sdk_identity_refresh(self, worker: SdkOperationThread, identity) -> None:
        self._sdk_identity_address = str(getattr(identity, "sdk_address", "") or "")
        self.sdk_identity_status_label.setText(f"Ready: {getattr(identity, 'alias', 'edge-node-launcher')}")
        self.sdk_identity_address_label.setText(_compact_middle(self._sdk_identity_address) or "-")
        self.sdk_identity_address_label.setToolTip(self._sdk_identity_address)
        network = str(getattr(identity, "evm_network", "") or "-")
        self.sdk_identity_network_label.setText(network)
        self.sdk_identity_network_label.setToolTip(network)
        cache_base = str(getattr(identity, "local_cache_base_folder", "") or "-")
        cache_app = str(getattr(identity, "local_cache_app_folder", "") or "")
        cache_path = f"{cache_base}/{cache_app}" if cache_app and cache_base != "-" else cache_base
        self.sdk_identity_cache_label.setText(_compact_middle(cache_path))
        self.sdk_identity_cache_label.setToolTip(cache_path)
        self.copy_sdk_identity_address_button.setEnabled(bool(self._sdk_identity_address))
        self.refresh_sdk_identity_button.setEnabled(True)
        self._log_event(
            f"SDK identity refresh complete: address={'yes' if self._sdk_identity_address else 'no'}",
            color="green",
        )

    def _fail_sdk_identity_refresh(self, worker: SdkOperationThread, error: str) -> None:
        self._set_sdk_identity_placeholder()
        error_message = classify_sdk_error(error)
        self.sdk_identity_status_label.setText(error_message.user_message)
        self.refresh_sdk_identity_button.setEnabled(True)
        self._log_event(
            f"SDK identity refresh failed: {error_message.user_message}",
            color="red",
        )
        if error_message.classified:
            self._log_event(
                f"SDK identity diagnostic ({error_message.category}): {error_message.diagnostic}",
                color="red",
                debug=True,
            )

    def _cleanup_sdk_identity_worker(self, worker: SdkOperationThread) -> None:
        if self._sdk_identity_worker is worker:
            self._sdk_identity_worker = None
        worker.deleteLater()

    def copy_sdk_identity_address(self) -> None:
        if not self._sdk_identity_address:
            return
        QApplication.clipboard().setText(self._sdk_identity_address)
        self._log_event("SDK identity address copied", color="blue", debug=True)

    def _log_event(self, message: str, *, color: str = "blue", debug: bool = False) -> None:
        if self._event_logger is None:
            return
        self._event_logger(message, color=color, debug=debug)


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


def _compact_middle(value: str, max_length: int = 34) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    prefix_length = max(8, max_length // 2 - 2)
    suffix_length = max_length - prefix_length - 3
    return f"{text[:prefix_length]}...{text[-suffix_length:]}"
