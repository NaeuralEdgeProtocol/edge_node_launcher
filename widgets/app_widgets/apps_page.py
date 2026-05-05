from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.app_deployment_models import (
    APP_TYPE_CONTAINER,
    APP_TYPE_WORKER,
    AppResourceSpec,
    ContainerAppSpec,
    DeploymentResult,
    FileVolumeSpec,
    ManagedAppRecord,
    SdkAppStatus,
    WorkerAppSpec,
    utc_now_iso,
)
from services.app_deployment_validation import (
    ValidationIssue,
    validate_container_spec,
    validate_file_volumes,
    validate_worker_spec,
)
from services.app_registry import AppRegistry
from services.app_secret_redaction import REDACTED_SECRET, redact_secret_text, redact_secrets
from services.sdk_error_messages import classify_sdk_error
from services.sdk_operation_worker import SdkOperationThread
from widgets.app_widgets.sidebar_controls import (
    create_sidebar_action_button,
    create_sidebar_section_label,
)

OTHER_NODE_OPTION = "__other_node__"


class CreateAppDialog(QDialog):
    """Modal workflow for creating CAR/WAR launcher-owned apps."""

    def __init__(self, form_widget: QWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deploy App")
        self.setObjectName("createAppDialog")
        self.setAccessibleName("Deploy App")
        self.setMinimumSize(760, 620)
        self.resize(860, 720)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Deploy App")
        title.setObjectName("createAppDialogTitle")
        title.setAccessibleName("Deploy App")
        title.setProperty("role", "appDialogTitle")
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("createAppDialogScrollArea")
        scroll_area.setAccessibleName("Deploy app form")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setWidget(form_widget)
        layout.addWidget(scroll_area, 1)


class AppsPage(QWidget):
    """CAR/WAR app deployment and launcher-owned app registry page."""

    selected_record_changed = pyqtSignal(object)
    sdk_settings_requested = pyqtSignal()

    def __init__(
        self,
        *,
        app_registry=None,
        deployment_client=None,
        launch_preflight_service=None,
        event_logger=None,
        parent=None,
    ):
        super().__init__(parent)
        self.app_registry = app_registry or AppRegistry()
        self.deployment_client = deployment_client
        self.launch_preflight_service = launch_preflight_service
        self.event_logger = event_logger
        self.target_container_name = ""
        self.management_target_container_name = ""
        self._target_node_options: list[dict] = []
        self._active_create_dialog: CreateAppDialog | None = None
        self._records_by_row: dict[int, ManagedAppRecord] = {}
        self._active_workers: list[SdkOperationThread] = []

        self._init_layout()
        self.refresh_apps()

    def _init_layout(self) -> None:
        self.setObjectName("appsPage")
        self.setAccessibleName("Apps page")
        self.setProperty("role", "navigationPage")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(10)
        layout.addWidget(create_sidebar_section_label("Apps", "appsPageSectionLabel"))

        self.apps_table = QTableWidget(0, 4)
        self.apps_table.setObjectName("appsTable")
        self.apps_table.setAccessibleName("Launcher-owned apps")
        self.apps_table.setHorizontalHeaderLabels(["Name", "Type", "Status", "Node"])
        self.apps_table.verticalHeader().hide()
        self.apps_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.apps_table.setSelectionMode(QTableWidget.SingleSelection)
        self.apps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.apps_table.setAlternatingRowColors(False)
        self.apps_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.apps_table.setMinimumHeight(136)
        self.apps_table.setMaximumHeight(180)
        self._configure_apps_table_columns()
        self.apps_table.itemSelectionChanged.connect(self._emit_selected_record_changed)
        layout.addWidget(self.apps_table)

        self.apps_empty_state = QLabel("No launcher-owned apps yet")
        self.apps_empty_state.setObjectName("appsEmptyStateLabel")
        self.apps_empty_state.setAccessibleName("No launcher-owned apps")
        self.apps_empty_state.setProperty("role", "appsEmptyState")
        self.apps_empty_state.setAlignment(Qt.AlignCenter)
        self.apps_empty_state.setWordWrap(True)
        self.apps_empty_state.setMinimumHeight(72)
        self.apps_empty_state.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.apps_empty_state)

        layout.addWidget(create_sidebar_section_label("Node scope", "appManagementTargetSectionLabel"))
        layout.addWidget(self._create_management_target_node_field())

        app_actions = QWidget()
        app_actions.setObjectName("appManagementActionBar")
        app_actions.setAccessibleName("App management actions")
        app_actions.setProperty("role", "appActionBar")
        actions_layout = QGridLayout(app_actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        for column in range(3):
            actions_layout.setColumnStretch(column, 1)

        self.create_app_button = create_sidebar_action_button(
            "Create App",
            "appCreateButton",
            "primary",
            "Open app deployment workflow",
            self.open_create_app_dialog,
        )
        self._set_workspace_button_size(self.create_app_button, 42)
        actions_layout.addWidget(self.create_app_button, 0, 0)

        self.refresh_button = create_sidebar_action_button(
            "Refresh",
            "appRefreshButton",
            "secondary",
            "Refresh launcher-owned app list",
            self.refresh_app_statuses,
        )
        self._set_workspace_button_size(self.refresh_button, 40)
        actions_layout.addWidget(self.refresh_button, 0, 1)

        self.stop_button = create_sidebar_action_button(
            "Stop",
            "appStopButton",
            "utility",
            "Stop selected launcher-owned app",
            self.stop_selected_app,
        )
        self._set_workspace_button_size(self.stop_button, 40)
        actions_layout.addWidget(self.stop_button, 0, 2)

        self.copy_url_button = create_sidebar_action_button(
            "Copy URL",
            "appCopyUrlButton",
            "utility",
            "Copy selected app URL",
            self.copy_selected_url,
        )
        self._set_workspace_button_size(self.copy_url_button, 40)
        actions_layout.addWidget(self.copy_url_button, 1, 0)

        self.check_sdk_access_button = create_sidebar_action_button(
            "Check SDK",
            "appCheckSdkAccessButton",
            "secondary",
            "Verify launcher SDK access on the selected node",
            self.check_sdk_access,
        )
        self._set_workspace_button_size(self.check_sdk_access_button, 40)
        actions_layout.addWidget(self.check_sdk_access_button, 1, 1)

        self.sdk_settings_button = create_sidebar_action_button(
            "Settings",
            "appSdkSettingsButton",
            "utility",
            "Open SDK and launcher settings",
            self.sdk_settings_requested.emit,
        )
        self._set_workspace_button_size(self.sdk_settings_button, 40)
        actions_layout.addWidget(self.sdk_settings_button, 1, 2)
        layout.addWidget(app_actions)

        self.management_message = QLabel("")
        self.management_message.setObjectName("appManagementMessageLabel")
        self.management_message.setAccessibleName("App management message")
        self.management_message.setProperty("role", "appValidationMessage")
        self.management_message.setWordWrap(True)
        self.management_message.hide()
        self.validation_message = self.management_message
        layout.addWidget(self.management_message)
        layout.addStretch(1)

    def _create_management_target_node_field(self) -> QWidget:
        field = QWidget()
        field.setObjectName("appManagementTargetNodeField")
        field.setAccessibleName("Management target node picker")
        field.setProperty("role", "appTargetNodeField")
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.management_node_address_combo = self._create_combo("appManagementNodeAddressCombo", "Node scope")
        self.management_node_address_combo.setToolTip("Node used for SDK access checks and app status refresh")
        self.management_node_address_combo.addItem("Other...", OTHER_NODE_OPTION)
        self.management_node_address_combo.currentIndexChanged.connect(self._sync_management_target_node_choice)
        layout.addWidget(self.management_node_address_combo)

        self.management_node_address_input = self._create_line_edit("appManagementNodeAddressInput", "0xai_...")
        self.management_node_address_input.setAccessibleName("Custom node address")
        layout.addWidget(self.management_node_address_input)
        self.management_node_address_input.textChanged.connect(lambda *_args: self._clear_message())
        self._sync_management_target_node_choice()
        return field

    def _create_deployment_panel(self) -> QWidget:
        deployment_panel = QWidget()
        deployment_panel.setObjectName("appDeploymentPanel")
        deployment_panel.setAccessibleName("App deployment form")
        deployment_panel.setProperty("role", "appDeploymentPanel")
        deployment_layout = QVBoxLayout(deployment_panel)
        deployment_layout.setContentsMargins(0, 0, 0, 0)
        deployment_layout.setSpacing(8)

        core_grid = QGridLayout()
        core_grid.setContentsMargins(0, 0, 0, 0)
        core_grid.setHorizontalSpacing(10)
        core_grid.setVerticalSpacing(5)
        core_grid.setColumnStretch(0, 1)
        core_grid.setColumnStretch(1, 1)

        self.runner_type_combo = self._create_combo("appRunnerTypeCombo", "App runner type")
        self.runner_type_combo.addItem("Container", APP_TYPE_CONTAINER)
        self.runner_type_combo.addItem("Worker", APP_TYPE_WORKER)
        self._add_grid_field(core_grid, 0, 0, "Runner", "appRunnerTypeLabel", self.runner_type_combo)

        self.app_name_input = self._create_line_edit("appNameInput", "App name")
        self._add_grid_field(core_grid, 0, 1, "App name", "appNameLabel", self.app_name_input)

        target_node_field = self._create_target_node_field()
        self._add_grid_field(core_grid, 1, 0, "Target node", "appNodeAddressLabel", target_node_field, 2)
        deployment_layout.addLayout(core_grid)

        self.runner_stack = QStackedWidget()
        self.runner_stack.setObjectName("appRunnerStack")
        self.runner_stack.setAccessibleName("App runner form fields")
        self.runner_stack.addWidget(self._create_container_fields())
        self.runner_stack.addWidget(self._create_worker_fields())
        deployment_layout.addWidget(self.runner_stack)
        self.runner_type_combo.currentIndexChanged.connect(self._sync_runner_stack)

        self.advanced_options_toggle = self._create_advanced_options_toggle()
        deployment_layout.addWidget(self.advanced_options_toggle)

        self.advanced_options_panel = self._create_advanced_options_panel()
        deployment_layout.addWidget(self.advanced_options_panel)
        self._sync_advanced_options_visibility(False)

        self.validation_message = QLabel("")
        self.validation_message.setObjectName("appValidationMessageLabel")
        self.validation_message.setAccessibleName("App validation message")
        self.validation_message.setProperty("role", "appValidationMessage")
        self.validation_message.setWordWrap(True)
        self.validation_message.hide()
        deployment_layout.addWidget(self.validation_message)

        launch_actions = QWidget()
        launch_actions.setObjectName("appLaunchActionBar")
        launch_actions.setAccessibleName("App launch actions")
        launch_actions.setProperty("role", "appActionBar")
        launch_actions_layout = QHBoxLayout(launch_actions)
        launch_actions_layout.setContentsMargins(0, 0, 0, 0)
        launch_actions_layout.setSpacing(8)

        self.validate_button = create_sidebar_action_button(
            "Validate",
            "appValidateButton",
            "secondary",
            "Validate app deployment fields",
            self.validate_current_form,
        )
        self._set_workspace_button_size(self.validate_button, 40)
        launch_actions_layout.addWidget(self.validate_button, 1)

        self.launch_button = create_sidebar_action_button(
            "Deploy",
            "appLaunchButton",
            "primary",
            "Launch selected app through the Ratio1 SDK",
            self.launch_current_app,
        )
        self._set_workspace_button_size(self.launch_button, 44)
        launch_actions_layout.addWidget(self.launch_button, 2)

        self.create_cancel_button = create_sidebar_action_button(
            "Cancel",
            "appCreateCancelButton",
            "utility",
            "Close app deployment workflow",
            self._reject_active_create_dialog,
        )
        self._set_workspace_button_size(self.create_cancel_button, 40)
        launch_actions_layout.addWidget(self.create_cancel_button, 1)
        deployment_layout.addWidget(launch_actions)

        self._sync_runner_stack()
        self._connect_form_message_reset()
        return deployment_panel

    def open_create_app_dialog(self) -> int:
        if self._active_create_dialog is not None and self._active_create_dialog.isVisible():
            self._active_create_dialog.raise_()
            self._active_create_dialog.activateWindow()
            return QDialog.Rejected

        dialog = CreateAppDialog(self._create_deployment_panel(), parent=self)
        self._active_create_dialog = dialog
        self._populate_create_dialog_targets()
        try:
            return dialog.exec_()
        finally:
            if self._active_create_dialog is dialog:
                self._active_create_dialog = None

    def _reject_active_create_dialog(self) -> None:
        if self._active_create_dialog is not None:
            self._active_create_dialog.reject()

    def _create_target_node_field(self) -> QWidget:
        field = QWidget()
        field.setObjectName("appTargetNodeField")
        field.setAccessibleName("Target node picker")
        field.setProperty("role", "appTargetNodeField")
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.node_address_combo = self._create_combo("appNodeAddressCombo", "Target node")
        self.node_address_combo.addItem("Other...", OTHER_NODE_OPTION)
        self.node_address_combo.currentIndexChanged.connect(self._sync_target_node_choice)
        layout.addWidget(self.node_address_combo)

        self.node_address_input = self._create_line_edit("appNodeAddressInput", "0xai_...")
        self.node_address_input.setAccessibleName("Custom node address")
        layout.addWidget(self.node_address_input)
        self._sync_target_node_choice()
        return field

    def _target_node_address(self) -> str:
        data = self.node_address_combo.currentData()
        if isinstance(data, dict):
            return str(data.get("address") or "").strip()
        return self.node_address_input.text().strip()

    def _management_target_node_address(self) -> str:
        data = self.management_node_address_combo.currentData()
        if isinstance(data, dict):
            return str(data.get("address") or "").strip()
        return self.management_node_address_input.text().strip()

    def _sync_target_node_choice(self) -> None:
        data = self.node_address_combo.currentData()
        use_manual_address = not isinstance(data, dict)
        self.node_address_input.setVisible(use_manual_address)
        if isinstance(data, dict):
            self.target_container_name = str(data.get("container_name") or "")
        else:
            self.target_container_name = ""

    def _sync_management_target_node_choice(self) -> None:
        data = self.management_node_address_combo.currentData()
        use_manual_address = not isinstance(data, dict)
        self.management_node_address_input.setVisible(use_manual_address)
        if isinstance(data, dict):
            self.management_target_container_name = str(data.get("container_name") or "")
        else:
            self.management_target_container_name = ""

    def _populate_create_dialog_targets(self) -> None:
        self._set_combo_target_node_options(
            self.node_address_combo,
            self.node_address_input,
            self._target_node_options,
            current_address=self._management_target_node_address(),
        )
        self._sync_target_node_choice()

    def _upsert_target_node_option(
        self,
        *,
        label: str,
        node_address: str,
        container_name: str | None,
        select: bool = False,
    ) -> None:
        node_address = (node_address or "").strip()
        if not node_address:
            return

        self._upsert_combo_target_node_option(
            self.node_address_combo,
            label=label,
            node_address=node_address,
            container_name=container_name,
            select=select,
        )

    def _upsert_management_target_node_option(
        self,
        *,
        label: str,
        node_address: str,
        container_name: str | None,
        select: bool = False,
    ) -> None:
        node_address = (node_address or "").strip()
        if not node_address:
            return
        self._upsert_combo_target_node_option(
            self.management_node_address_combo,
            label=label,
            node_address=node_address,
            container_name=container_name,
            select=select,
        )
        self._sync_management_target_node_choice()

    def _upsert_combo_target_node_option(
        self,
        combo: QComboBox,
        *,
        label: str,
        node_address: str,
        container_name: str | None,
        select: bool = False,
    ) -> None:
        insert_index = max(0, combo.count() - 1)
        for index in range(combo.count()):
            data = combo.itemData(index)
            same_address = isinstance(data, dict) and data.get("address") == node_address
            same_container = (
                isinstance(data, dict)
                and container_name
                and data.get("container_name") == container_name
            )
            if same_address or same_container:
                combo.setItemText(index, f"{label} ({_short_node_address(node_address)})")
                data["address"] = node_address
                data["container_name"] = container_name or ""
                combo.setItemData(index, data)
                if select:
                    combo.setCurrentIndex(index)
                return

        combo.insertItem(
            insert_index,
            f"{label} ({_short_node_address(node_address)})",
            {"address": node_address, "container_name": container_name or ""},
        )
        if select:
            combo.setCurrentIndex(insert_index)

    def _set_combo_target_node_options(
        self,
        combo: QComboBox,
        manual_input: QLineEdit,
        nodes: list[dict],
        *,
        current_address: str = "",
    ) -> None:
        manual_text = manual_input.text().strip() or current_address

        combo.blockSignals(True)
        combo.clear()
        seen_addresses = set()
        selected_index = -1
        for node in nodes:
            node_address = str(node.get("node_address") or node.get("address") or "").strip()
            if not node_address or node_address in seen_addresses:
                continue
            seen_addresses.add(node_address)
            label = str(
                node.get("label")
                or node.get("node_alias")
                or node.get("container_name")
                or _short_node_address(node_address)
            ).strip()
            container_name = str(node.get("container_name") or "").strip()
            item_label = f"{label} ({_short_node_address(node_address)})"
            combo.addItem(
                item_label,
                {"address": node_address, "container_name": container_name},
            )
            if node_address == current_address:
                selected_index = combo.count() - 1

        combo.addItem("Other...", OTHER_NODE_OPTION)
        if selected_index >= 0:
            combo.setCurrentIndex(selected_index)
        else:
            combo.setCurrentIndex(combo.count() - 1)
            if manual_text:
                manual_input.setText(manual_text)
        combo.blockSignals(False)

    def _create_advanced_options_toggle(self) -> QToolButton:
        button = QToolButton()
        button.setObjectName("appAdvancedOptionsToggle")
        button.setAccessibleName("Show advanced app options")
        button.setToolTip("Show CPU, memory, volumes, environment, and deployment policies")
        button.setText("Advanced options")
        button.setCheckable(True)
        button.setChecked(False)
        button.setArrowType(Qt.RightArrow)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setProperty("role", "appDisclosureButton")
        button.setMinimumHeight(34)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.toggled.connect(self._sync_advanced_options_visibility)
        return button

    def _create_advanced_options_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("appAdvancedOptionsPanel")
        panel.setAccessibleName("Advanced app options")
        panel.setProperty("role", "appAdvancedOptionsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.advanced_options_tabs = QTabWidget()
        self.advanced_options_tabs.setObjectName("appAdvancedOptionsTabs")
        self.advanced_options_tabs.setAccessibleName("Advanced app option groups")
        self.advanced_options_tabs.setProperty("role", "appAdvancedOptionsTabs")
        self.advanced_options_tabs.setDocumentMode(True)
        self.advanced_options_tabs.setTabPosition(QTabWidget.North)
        self.advanced_options_tabs.addTab(self._create_runtime_options_tab(), "Runtime")
        self.advanced_options_tabs.addTab(self._create_storage_options_tab(), "Storage")
        self.advanced_options_tabs.addTab(self._create_environment_options_tab(), "Environment")
        layout.addWidget(self.advanced_options_tabs)
        return panel

    def _sync_advanced_options_visibility(self, checked: bool) -> None:
        if hasattr(self, "advanced_options_panel"):
            self.advanced_options_panel.setVisible(checked)
        self.advanced_options_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.advanced_options_toggle.setAccessibleName(
            "Hide advanced app options" if checked else "Show advanced app options"
        )

    def _create_container_fields(self) -> QWidget:
        page = QWidget()
        page.setObjectName("containerAppFields")
        page.setAccessibleName("Container app fields")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(5)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        self.car_image_input = self._create_line_edit("carImageInput", "nginx:alpine")
        self.car_port_input = self._create_line_edit("carPortInput", "5000")
        self.car_registry_input = self._create_line_edit("carRegistryInput", "docker.io")
        self.car_registry_input.setText("docker.io")
        self.car_registry_user_input = self._create_line_edit("carRegistryUserInput", "Registry user")
        self.car_registry_password_input = self._create_line_edit(
            "carRegistryPasswordInput",
            "Registry password",
        )
        self.car_registry_password_input.setEchoMode(QLineEdit.Password)

        self._add_grid_field(layout, 0, 0, "Image", "carImageLabel", self.car_image_input, 2)
        self._add_grid_field(layout, 1, 0, "Port", "carPortLabel", self.car_port_input)
        self._add_grid_field(layout, 1, 1, "Registry", "carRegistryLabel", self.car_registry_input)
        self._add_grid_field(layout, 2, 0, "Registry user", "carRegistryUserLabel", self.car_registry_user_input)
        self._add_grid_field(
            layout,
            2,
            1,
            "Registry password",
            "carRegistryPasswordLabel",
            self.car_registry_password_input,
        )
        layout.setRowStretch(6, 1)

        return page

    def _create_worker_fields(self) -> QWidget:
        page = QWidget()
        page.setObjectName("workerAppFields")
        page.setAccessibleName("Worker app fields")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(5)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        self.worker_repo_input = self._create_line_edit(
            "workerRepoInput",
            "https://github.com/org/repo",
        )
        self.worker_branch_input = self._create_line_edit("workerBranchInput", "main")
        self.worker_branch_input.setText("main")
        self.worker_image_input = self._create_line_edit("workerImageInput", "node:22")
        self.worker_image_input.setText("node:22")
        self.worker_port_input = self._create_line_edit("workerPortInput", "4173")
        self.worker_port_input.setText("4173")
        self.worker_github_user_input = self._create_line_edit("workerGithubUserInput", "GitHub user")
        self.worker_github_token_input = self._create_line_edit(
            "workerGithubTokenInput",
            "GitHub token",
        )
        self.worker_github_token_input.setEchoMode(QLineEdit.Password)
        self.worker_commands_input = self._create_plain_text(
            "workerCommandsInput",
            "npm install\nnpm run build\nnpm run start",
        )
        self.worker_commands_input.setPlainText("npm install\nnpm run build\nnpm run start")
        self.worker_commands_input.setMaximumHeight(88)

        self._add_grid_field(layout, 0, 0, "GitHub repo", "workerRepoLabel", self.worker_repo_input, 2)
        self._add_grid_field(layout, 1, 0, "Branch", "workerBranchLabel", self.worker_branch_input)
        self._add_grid_field(layout, 1, 1, "Base image", "workerImageLabel", self.worker_image_input)
        self._add_grid_field(layout, 2, 0, "Port", "workerPortLabel", self.worker_port_input)
        self._add_grid_field(layout, 2, 1, "GitHub user", "workerGithubUserLabel", self.worker_github_user_input)
        self._add_grid_field(layout, 3, 0, "GitHub token", "workerGithubTokenLabel", self.worker_github_token_input, 2)
        self.worker_registry_input = self._create_line_edit("workerRegistryInput", "docker.io")
        self.worker_registry_input.setText("docker.io")
        self.worker_registry_user_input = self._create_line_edit("workerRegistryUserInput", "Registry user")
        self.worker_registry_password_input = self._create_line_edit(
            "workerRegistryPasswordInput",
            "Registry password",
        )
        self.worker_registry_password_input.setEchoMode(QLineEdit.Password)
        self.worker_vcs_poll_input = self._create_line_edit("workerVcsPollInput", "60")
        self.worker_vcs_poll_input.setText("60")

        self._add_grid_field(layout, 4, 0, "Registry", "workerRegistryLabel", self.worker_registry_input)
        self._add_grid_field(layout, 4, 1, "Registry user", "workerRegistryUserLabel", self.worker_registry_user_input)
        self._add_grid_field(
            layout,
            5,
            0,
            "Registry password",
            "workerRegistryPasswordLabel",
            self.worker_registry_password_input,
        )
        self._add_grid_field(layout, 5, 1, "VCS poll (s)", "workerVcsPollLabel", self.worker_vcs_poll_input)
        self._add_grid_field(layout, 6, 0, "Commands", "workerCommandsLabel", self.worker_commands_input, 2)
        layout.setRowStretch(14, 1)

        return page

    def _create_runtime_fields(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("appRuntimePanel")
        panel.setAccessibleName("App runtime settings")
        panel.setProperty("role", "appRuntimePanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(5)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        self.app_cpu_input = self._create_line_edit("appCpuInput", "1")
        self.app_cpu_input.setText("1")
        self.app_memory_input = self._create_line_edit("appMemoryInput", "512m")
        self.app_memory_input.setText("512m")
        self.app_restart_policy_combo = self._create_combo("appRestartPolicyCombo", "Restart policy")
        self.app_restart_policy_combo.addItems(["always", "on-failure", "never"])
        self.app_pull_policy_combo = self._create_combo("appImagePullPolicyCombo", "Image pull policy")
        self.app_pull_policy_combo.addItems(["always", "if-not-present", "never"])
        self.app_tunnel_engine_combo = self._create_combo("appTunnelEngineCombo", "Tunnel engine")
        self.app_tunnel_engine_combo.addItems(["cloudflare", "ngrok"])
        self.app_tunnel_enabled_checkbox = QCheckBox("Expose through tunnel")
        self.app_tunnel_enabled_checkbox.setObjectName("appTunnelEnabledCheckbox")
        self.app_tunnel_enabled_checkbox.setAccessibleName("Expose app through tunnel")
        self.app_tunnel_enabled_checkbox.setProperty("role", "appToggle")
        self.app_tunnel_enabled_checkbox.setChecked(True)
        self.app_tunnel_enabled_checkbox.setMinimumHeight(34)
        self.app_tunnel_enabled_checkbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._add_grid_field(layout, 0, 0, "CPU", "appCpuLabel", self.app_cpu_input)
        self._add_grid_field(layout, 0, 1, "Memory", "appMemoryLabel", self.app_memory_input)
        self._add_grid_field(
            layout,
            1,
            0,
            "Restart",
            "appRestartPolicyLabel",
            self.app_restart_policy_combo,
        )
        self._add_grid_field(
            layout,
            1,
            1,
            "Pull policy",
            "appImagePullPolicyLabel",
            self.app_pull_policy_combo,
        )
        self._add_grid_field(layout, 2, 0, "Tunnel engine", "appTunnelEngineLabel", self.app_tunnel_engine_combo)
        self._add_grid_field(layout, 2, 1, "Tunnel", "appTunnelEnabledLabel", self.app_tunnel_enabled_checkbox)
        layout.setRowStretch(6, 1)
        return panel

    def _create_runtime_options_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appRuntimeOptionsTab")
        page.setAccessibleName("Runtime options")
        page.setProperty("role", "appAdvancedOptionsTabPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(create_sidebar_section_label("Runtime", "appRuntimeSectionLabel"))
        layout.addWidget(self._create_runtime_fields())
        layout.addStretch(1)
        return page

    def _create_storage_options_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appStorageOptionsTab")
        page.setAccessibleName("Storage options")
        page.setProperty("role", "appAdvancedOptionsTabPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._label("Volumes", "appVolumesLabel"))
        layout.addWidget(self._create_volume_editor())
        layout.addWidget(self._label("Config files", "appFileVolumesLabel"))
        layout.addWidget(self._create_file_volume_editor())
        layout.addStretch(1)
        return page

    def _create_environment_options_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appEnvironmentOptionsTab")
        page.setAccessibleName("Environment options")
        page.setProperty("role", "appAdvancedOptionsTabPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.env_input = self._create_plain_text("appEnvInput", "KEY=value")
        self.env_input.setMinimumHeight(96)
        self.env_input.setMaximumHeight(140)
        layout.addWidget(self._label("Environment", "appEnvLabel"))
        layout.addWidget(self.env_input)
        layout.addStretch(1)
        return page

    def _create_volume_editor(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("appVolumeEditor")
        panel.setAccessibleName("Volume mount editor")
        panel.setProperty("role", "appVolumeEditor")
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(5)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 3)

        self.app_volume_source_input = self._create_line_edit("appVolumeSourceInput", "volume_name")
        self.app_volume_mount_input = self._create_line_edit("appVolumeMountInput", "/container/path")
        layout.addWidget(self.app_volume_source_input, 0, 0)
        layout.addWidget(self.app_volume_mount_input, 0, 1)

        volume_actions = QWidget()
        volume_actions.setObjectName("appVolumeActionBar")
        volume_actions.setAccessibleName("Volume mount actions")
        volume_actions.setProperty("role", "appActionBar")
        volume_action_layout = QHBoxLayout(volume_actions)
        volume_action_layout.setContentsMargins(0, 0, 0, 0)
        volume_action_layout.setSpacing(8)

        self.add_volume_button = create_sidebar_action_button(
            "Add Mount",
            "appAddVolumeButton",
            "secondary",
            "Add the volume mount row",
            self.add_volume_mount,
        )
        self._set_workspace_button_size(self.add_volume_button, 34)
        volume_action_layout.addWidget(self.add_volume_button)

        self.remove_volume_button = create_sidebar_action_button(
            "Remove Selected",
            "appRemoveVolumeButton",
            "utility",
            "Remove the selected volume mount",
            self.remove_selected_volume_mount,
        )
        self._set_workspace_button_size(self.remove_volume_button, 34)
        volume_action_layout.addWidget(self.remove_volume_button)
        layout.addWidget(volume_actions, 1, 0, 1, 2)

        self.app_volumes_table = QTableWidget(0, 2)
        self.app_volumes_table.setObjectName("appVolumesTable")
        self.app_volumes_table.setAccessibleName("Configured volume mounts")
        self.app_volumes_table.setHorizontalHeaderLabels(["Source", "Mount path"])
        self.app_volumes_table.verticalHeader().hide()
        self.app_volumes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.app_volumes_table.setSelectionMode(QTableWidget.SingleSelection)
        self.app_volumes_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.app_volumes_table.setAlternatingRowColors(False)
        self.app_volumes_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.app_volumes_table.setMinimumHeight(76)
        self.app_volumes_table.setMaximumHeight(96)
        header = self.app_volumes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.app_volumes_table, 2, 0, 1, 2)
        return panel

    def _create_file_volume_editor(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("appFileVolumeEditor")
        panel.setAccessibleName("Config file volume editor")
        panel.setProperty("role", "appFileVolumeEditor")
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(5)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 3)

        self.app_file_volume_name_input = self._create_line_edit("appFileVolumeNameInput", "settings")
        self.app_file_volume_mount_input = self._create_line_edit("appFileVolumeMountInput", "/app/settings.ini")
        layout.addWidget(self.app_file_volume_name_input, 0, 0)
        layout.addWidget(self.app_file_volume_mount_input, 0, 1)

        self.app_file_volume_content_input = self._create_plain_text(
            "appFileVolumeContentInput",
            "file content",
        )
        self.app_file_volume_content_input.setMaximumHeight(72)
        layout.addWidget(self.app_file_volume_content_input, 1, 0, 1, 2)

        file_actions = QWidget()
        file_actions.setObjectName("appFileVolumeActionBar")
        file_actions.setAccessibleName("Config file volume actions")
        file_actions.setProperty("role", "appActionBar")
        file_action_layout = QHBoxLayout(file_actions)
        file_action_layout.setContentsMargins(0, 0, 0, 0)
        file_action_layout.setSpacing(8)

        self.add_file_volume_button = create_sidebar_action_button(
            "Add File",
            "appAddFileVolumeButton",
            "secondary",
            "Add the config file volume row",
            self.add_file_volume,
        )
        self._set_workspace_button_size(self.add_file_volume_button, 34)
        file_action_layout.addWidget(self.add_file_volume_button)

        self.remove_file_volume_button = create_sidebar_action_button(
            "Remove File",
            "appRemoveFileVolumeButton",
            "utility",
            "Remove the selected config file volume",
            self.remove_selected_file_volume,
        )
        self._set_workspace_button_size(self.remove_file_volume_button, 34)
        file_action_layout.addWidget(self.remove_file_volume_button)
        layout.addWidget(file_actions, 2, 0, 1, 2)

        self.app_file_volumes_table = QTableWidget(0, 2)
        self.app_file_volumes_table.setObjectName("appFileVolumesTable")
        self.app_file_volumes_table.setAccessibleName("Configured config file volumes")
        self.app_file_volumes_table.setHorizontalHeaderLabels(["Name", "Mount path"])
        self.app_file_volumes_table.verticalHeader().hide()
        self.app_file_volumes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.app_file_volumes_table.setSelectionMode(QTableWidget.SingleSelection)
        self.app_file_volumes_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.app_file_volumes_table.setAlternatingRowColors(False)
        self.app_file_volumes_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.app_file_volumes_table.setMinimumHeight(76)
        self.app_file_volumes_table.setMaximumHeight(96)
        header = self.app_file_volumes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.app_file_volumes_table, 3, 0, 1, 2)
        return panel

    def add_volume_mount(self) -> bool:
        source = self.app_volume_source_input.text().strip()
        mount_path = self.app_volume_mount_input.text().strip()
        issue = self._validate_volume_values(source, mount_path)
        if issue is not None:
            self._show_message(_format_issue(issue), error=True)
            self._log_event(f"SDK Apps volume mount rejected: {_format_issue(issue)}", color="yellow")
            return False
        if self._find_volume_row(source) is not None:
            issue = ValidationIssue("volumes", f"Duplicate volume source: {source}.")
            self._show_message(_format_issue(issue), error=True)
            self._log_event(f"SDK Apps volume mount rejected: {_format_issue(issue)}", color="yellow")
            return False
        self._append_volume_row(source, mount_path)
        self.app_volume_source_input.clear()
        self.app_volume_mount_input.clear()
        self._clear_message()
        return True

    def remove_selected_volume_mount(self) -> bool:
        selected = self.app_volumes_table.selectionModel().selectedRows()
        if not selected:
            self._show_message("volumes: Select a volume mount to remove.", error=True)
            return False
        for model_index in sorted(selected, key=lambda item: item.row(), reverse=True):
            self.app_volumes_table.removeRow(model_index.row())
        self._clear_message()
        return True

    def add_file_volume(self) -> bool:
        name = self.app_file_volume_name_input.text().strip()
        mount_path = self.app_file_volume_mount_input.text().strip()
        content = self.app_file_volume_content_input.toPlainText()
        issue = self._validate_file_volume_values(name, mount_path, content)
        if issue is not None:
            self._show_message(_format_issue(issue), error=True)
            self._log_event(f"SDK Apps file volume rejected: {_format_issue(issue)}", color="yellow")
            return False
        if self._find_file_volume_row(name) is not None:
            issue = ValidationIssue("file_volumes", f"Duplicate file volume name: {name}.")
            self._show_message(_format_issue(issue), error=True)
            self._log_event(f"SDK Apps file volume rejected: {_format_issue(issue)}", color="yellow")
            return False
        if self._find_file_volume_mount_row(mount_path) is not None:
            issue = ValidationIssue("file_volumes", f"Duplicate file volume mount path: {mount_path}.")
            self._show_message(_format_issue(issue), error=True)
            self._log_event(f"SDK Apps file volume rejected: {_format_issue(issue)}", color="yellow")
            return False
        self._append_file_volume_row(name, mount_path, content)
        self.app_file_volume_name_input.clear()
        self.app_file_volume_mount_input.clear()
        self.app_file_volume_content_input.clear()
        self._clear_message()
        return True

    def remove_selected_file_volume(self) -> bool:
        selected = self.app_file_volumes_table.selectionModel().selectedRows()
        if not selected:
            self._show_message("file_volumes: Select a config file to remove.", error=True)
            return False
        for model_index in sorted(selected, key=lambda item: item.row(), reverse=True):
            self.app_file_volumes_table.removeRow(model_index.row())
        self._clear_message()
        return True

    def set_launch_preflight_service(self, launch_preflight_service) -> None:
        self.launch_preflight_service = launch_preflight_service

    def set_event_logger(self, event_logger) -> None:
        self.event_logger = event_logger

    def set_target_node_address(self, node_address: str) -> None:
        self.set_target_node(node_address=node_address)

    def set_target_node(self, *, node_address: str = "", container_name: str | None = None) -> None:
        if container_name is not None:
            self.target_container_name = container_name
            self.management_target_container_name = container_name
        if node_address:
            label = container_name or _short_node_address(node_address)
            self._remember_target_node_option(
                label=label,
                node_address=node_address,
                container_name=container_name if container_name is not None else self.management_target_container_name,
            )
            self._upsert_management_target_node_option(
                label=label,
                node_address=node_address,
                container_name=container_name if container_name is not None else self.management_target_container_name,
                select=True,
            )
            if not self.management_node_address_input.text().strip():
                self.management_node_address_input.setText(node_address)
            if hasattr(self, "node_address_combo"):
                self._upsert_target_node_option(
                    label=label,
                    node_address=node_address,
                    container_name=container_name if container_name is not None else self.target_container_name,
                    select=True,
                )
            if hasattr(self, "node_address_input") and not self.node_address_input.text().strip():
                self.node_address_input.setText(node_address)
            if hasattr(self, "node_address_combo"):
                self._sync_target_node_choice()

    def set_target_node_options(self, nodes: list[dict]) -> None:
        self._target_node_options = list(nodes or [])
        self._set_combo_target_node_options(
            self.management_node_address_combo,
            self.management_node_address_input,
            self._target_node_options,
            current_address=self._management_target_node_address(),
        )
        self._sync_management_target_node_choice()
        if hasattr(self, "node_address_combo"):
            self._set_combo_target_node_options(
                self.node_address_combo,
                self.node_address_input,
                self._target_node_options,
                current_address=self._target_node_address(),
            )
            self._sync_target_node_choice()

    def _select_dialog_target_node(self, *, node_address: str, container_name: str | None) -> None:
        if not hasattr(self, "node_address_combo"):
            return
        self._upsert_target_node_option(
            label=container_name or _short_node_address(node_address),
            node_address=node_address,
            container_name=container_name if container_name is not None else self.target_container_name,
            select=True,
        )
        self._sync_target_node_choice()

    def _remember_target_node_option(self, *, label: str, node_address: str, container_name: str | None) -> None:
        node_address = (node_address or "").strip()
        if not node_address:
            return
        for option in self._target_node_options:
            same_address = option.get("node_address") == node_address or option.get("address") == node_address
            same_container = container_name and option.get("container_name") == container_name
            if same_address or same_container:
                option["label"] = label
                option["node_address"] = node_address
                option["container_name"] = container_name or ""
                return
        self._target_node_options.append(
            {
                "label": label,
                "node_address": node_address,
                "container_name": container_name or "",
            }
        )

    def validate_current_form(self):
        spec, issues = self._build_current_spec()
        if issues:
            issue_text = _format_issue(issues[0])
            self._show_message(issue_text, error=True)
            self._log_event(f"SDK Apps validation failed: {issue_text}", color="yellow")
            return None
        self._show_message("Ready", error=False)
        self._log_event(
            "SDK Apps validation ready: "
            f"type={spec.app_type} app={spec.app_name or '-'} node={_short_node_address(spec.node_address)}",
            color="blue",
        )
        return spec

    def launch_current_app(self) -> None:
        spec = self.validate_current_form()
        if spec is None:
            return
        if self.deployment_client is None:
            self._show_message("SDK launch worker pending", error=True)
            self._log_event("SDK Apps launch unavailable: deployment client is not configured", color="red")
            return
        target_container_name = self.target_container_name
        self._log_event(
            "SDK Apps launch requested: "
            f"type={spec.app_type} app={spec.app_name} node={_short_node_address(spec.node_address)} "
            f"container={target_container_name or '-'}",
            color="blue",
        )
        if spec.app_type == APP_TYPE_CONTAINER:
            operation = lambda: self._launch_with_preflight(
                lambda: self.deployment_client.launch_container_app(spec),
                target_container_name,
            )
        else:
            operation = lambda: self._launch_with_preflight(
                lambda: self.deployment_client.launch_worker_app(spec),
                target_container_name,
            )
        self._start_sdk_operation(
            "launch",
            operation,
            lambda result: self._handle_launch_success(result, spec),
            "Launching...",
        )

    def check_sdk_access(self) -> None:
        if self.launch_preflight_service is None:
            self._show_message("SDK access check unavailable", error=True)
            self._log_event("SDK Apps access check unavailable: preflight service is not configured", color="red")
            return
        target_container_name = self.management_target_container_name
        if not target_container_name:
            self._show_message("Target container is required", error=True)
            self._log_event("SDK Apps access check blocked: target container is required", color="yellow")
            return
        self._log_event(
            f"SDK Apps access check requested: container={target_container_name}",
            color="blue",
        )
        self._start_sdk_operation(
            "access check",
            lambda: self.launch_preflight_service.prepare(target_container_name),
            lambda result: self._handle_access_check_success(result, target_container_name),
            "Checking SDK access...",
        )

    def _launch_with_preflight(self, launch_operation, target_container_name: str):
        if self.launch_preflight_service is not None:
            self.launch_preflight_service.prepare(target_container_name)
        return launch_operation()

    def _handle_access_check_success(self, result, target_container_name: str) -> None:
        allowlist = getattr(result, "allowlist", None)
        changed = bool(getattr(allowlist, "changed", False))
        target_label = target_container_name or "target node"
        message = (
            f"SDK access added to {target_label}"
            if changed
            else f"SDK access ready for {target_label}"
        )
        self._show_message(message, error=False)
        self._log_event(
            f"SDK Apps access check complete: container={target_label} changed={changed}",
            color="green",
        )

    def refresh_app_statuses(self) -> None:
        if self.deployment_client is None:
            self.refresh_apps()
            self._show_message("Refreshed", error=False)
            self._log_event("SDK Apps refresh used local registry because deployment client is not configured", color="blue")
            return
        node_address = self._management_target_node_address()
        if not node_address:
            self.refresh_apps()
            self._show_message("Target node is required", error=True)
            self._log_event("SDK Apps refresh blocked: target node is required", color="yellow")
            return
        self._log_event(
            f"SDK Apps refresh requested: node={_short_node_address(node_address)}",
            color="blue",
        )
        self._start_sdk_operation(
            "refresh",
            lambda: self.deployment_client.list_node_apps(node_address),
            self._handle_refresh_success,
            "Refreshing...",
        )

    def refresh_apps(self, selected_app_id: str | None = None) -> None:
        if selected_app_id is None:
            selected = self._selected_record()
            selected_app_id = selected.app_id if selected is not None else None
        records = self.app_registry.list_apps()
        self._records_by_row = {}
        self.apps_table.setRowCount(len(records))
        self._sync_apps_empty_state(bool(records))
        selected_row = None
        for row, record in enumerate(records):
            self._records_by_row[row] = record
            if selected_app_id and record.app_id == selected_app_id:
                selected_row = row
            details = (
                f"Node: {record.node_address}\n"
                f"Pipeline: {record.pipeline_name}\n"
                f"URL: {record.app_url or '-'}"
            )
            self._set_table_item(row, 0, record.app_name, details)
            self._set_table_item(row, 1, record.app_type)
            self._set_table_item(row, 2, record.status)
            self._set_table_item(row, 3, _short_node_address(record.node_address), record.node_address)
        self._configure_apps_table_columns()
        if selected_row is not None:
            self.apps_table.selectRow(selected_row)
        else:
            self.apps_table.clearSelection()
        self._emit_selected_record_changed()

    def _sync_apps_empty_state(self, has_records: bool) -> None:
        self.apps_table.setVisible(has_records)
        self.apps_empty_state.setVisible(not has_records)

    def stop_selected_app(self) -> None:
        record = self._selected_record()
        if record is None:
            self._show_message("Select an app first", error=True)
            self._log_event("SDK Apps stop blocked: no app selected", color="yellow")
            return
        self._log_event(
            "SDK Apps stop requested: "
            f"app={record.app_name} node={_short_node_address(record.node_address)} pipeline={record.pipeline_name}",
            color="blue",
        )
        if self.deployment_client is not None:
            self._start_sdk_operation(
                "stop",
                lambda: self.deployment_client.stop_app(record.node_address, record.pipeline_name),
                lambda _result: self._mark_record_stopped(record),
                "Stopping...",
            )
            return
        self._mark_record_stopped(record)

    def _mark_record_stopped(self, record: ManagedAppRecord) -> None:
        record.status = "stopped"
        record.last_action = "stopped"
        self.app_registry.upsert(record)
        self.refresh_apps(selected_app_id=record.app_id)
        self._show_message("Stopped", error=False)
        self._log_event(
            "SDK Apps stop complete: "
            f"app={record.app_name} node={_short_node_address(record.node_address)}",
            color="green",
        )

    def copy_selected_url(self) -> None:
        record = self._selected_record()
        if record is None or not record.app_url:
            self._show_message("No URL selected", error=True)
            self._log_event("SDK Apps copy URL blocked: no URL selected", color="yellow")
            return
        QApplication.clipboard().setText(record.app_url)
        self._show_message("URL copied", error=False)
        self._log_event(
            f"SDK Apps URL copied: app={record.app_name} node={_short_node_address(record.node_address)}",
            color="blue",
        )

    def _build_current_spec(self):
        env, env_issues = self._parse_env()
        volumes, volume_issues = self._parse_volumes()
        file_volumes, file_volume_issues = self._parse_file_volumes()
        resources, resource_issues = self._parse_resources()
        common_issues = [*env_issues, *volume_issues, *file_volume_issues, *resource_issues]
        try:
            if self.runner_type_combo.currentData() == APP_TYPE_CONTAINER:
                spec = ContainerAppSpec(
                    app_name=self.app_name_input.text().strip(),
                    node_address=self._target_node_address(),
                    image=self.car_image_input.text().strip(),
                    port=_to_int(self.car_port_input.text()),
                    registry_server=self.car_registry_input.text().strip() or "docker.io",
                    registry_username=self.car_registry_user_input.text().strip(),
                    registry_password=self.car_registry_password_input.text(),
                    env=env,
                    volumes=volumes,
                    file_volumes=file_volumes,
                    resources=resources,
                    tunnel_engine_enabled=self.app_tunnel_enabled_checkbox.isChecked(),
                    tunnel_engine=self.app_tunnel_engine_combo.currentText(),
                    restart_policy=self.app_restart_policy_combo.currentText(),
                    image_pull_policy=self.app_pull_policy_combo.currentText(),
                )
                return spec, [*common_issues, *validate_container_spec(spec)]

            spec = WorkerAppSpec(
                app_name=self.app_name_input.text().strip(),
                node_address=self._target_node_address(),
                repo_url=self.worker_repo_input.text().strip(),
                branch=self.worker_branch_input.text().strip() or "main",
                image=self.worker_image_input.text().strip() or "node:22",
                port=_to_int(self.worker_port_input.text()),
                github_username=self.worker_github_user_input.text().strip(),
                github_token=self.worker_github_token_input.text(),
                registry_server=self.worker_registry_input.text().strip() or "docker.io",
                registry_username=self.worker_registry_user_input.text().strip(),
                registry_password=self.worker_registry_password_input.text(),
                commands=[
                    line.strip()
                    for line in self.worker_commands_input.toPlainText().splitlines()
                    if line.strip()
                ],
                env=env,
                volumes=volumes,
                file_volumes=file_volumes,
                resources=resources,
                tunnel_engine_enabled=self.app_tunnel_enabled_checkbox.isChecked(),
                tunnel_engine=self.app_tunnel_engine_combo.currentText(),
                restart_policy=self.app_restart_policy_combo.currentText(),
                image_pull_policy=self.app_pull_policy_combo.currentText(),
                vcs_poll_interval=_to_int(self.worker_vcs_poll_input.text()),
            )
            return spec, [*common_issues, *validate_worker_spec(spec)]
        except Exception as exc:
            return None, [ValidationIssue("form", str(exc))]

    def _parse_env(self) -> tuple[dict[str, str], list[ValidationIssue]]:
        env = {}
        issues = []
        for line in self.env_input.toPlainText().splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if "=" not in normalized:
                issues.append(ValidationIssue("env", "Environment rows must use KEY=value."))
                continue
            key, value = normalized.split("=", 1)
            env[key.strip()] = value.strip()
        return env, issues

    def _parse_volumes(self) -> tuple[dict[str, str], list[ValidationIssue]]:
        volumes = {}
        issues = []
        for source, target in self._volume_rows():
            issue = self._validate_volume_values(source, target)
            if issue is not None:
                issues.append(issue)
                continue
            if source in volumes:
                issues.append(ValidationIssue("volumes", f"Duplicate volume source: {source}."))
                continue
            volumes[source] = target

        pending_source = self.app_volume_source_input.text().strip()
        pending_target = self.app_volume_mount_input.text().strip()
        if pending_source or pending_target:
            issue = self._validate_volume_values(pending_source, pending_target)
            if issue is not None:
                issues.append(issue)
            elif pending_source in volumes:
                issues.append(ValidationIssue("volumes", f"Duplicate volume source: {pending_source}."))
            else:
                volumes[pending_source] = pending_target
        return volumes, issues

    def _parse_file_volumes(self) -> tuple[dict[str, FileVolumeSpec], list[ValidationIssue]]:
        file_volumes = {}
        issues = []
        mount_paths = set()
        for name, mount_path, content in self._file_volume_rows():
            issue = self._validate_file_volume_values(name, mount_path, content)
            if issue is not None:
                issues.append(issue)
                continue
            if name in file_volumes:
                issues.append(ValidationIssue("file_volumes", f"Duplicate file volume name: {name}."))
                continue
            if mount_path in mount_paths:
                issues.append(ValidationIssue("file_volumes", f"Duplicate file volume mount path: {mount_path}."))
                continue
            file_volumes[name] = FileVolumeSpec(content=content, mounting_point=mount_path)
            mount_paths.add(mount_path)

        pending_name = self.app_file_volume_name_input.text().strip()
        pending_mount = self.app_file_volume_mount_input.text().strip()
        pending_content = self.app_file_volume_content_input.toPlainText()
        if pending_name or pending_mount or pending_content.strip():
            issue = self._validate_file_volume_values(pending_name, pending_mount, pending_content)
            if issue is not None:
                issues.append(issue)
            elif pending_name in file_volumes:
                issues.append(ValidationIssue("file_volumes", f"Duplicate file volume name: {pending_name}."))
            elif pending_mount in mount_paths:
                issues.append(ValidationIssue("file_volumes", f"Duplicate file volume mount path: {pending_mount}."))
            else:
                file_volumes[pending_name] = FileVolumeSpec(
                    content=pending_content,
                    mounting_point=pending_mount,
                )
        return file_volumes, issues

    def _volume_rows(self) -> list[tuple[str, str]]:
        rows = []
        for row in range(self.app_volumes_table.rowCount()):
            source_item = self.app_volumes_table.item(row, 0)
            target_item = self.app_volumes_table.item(row, 1)
            rows.append(
                (
                    source_item.text().strip() if source_item is not None else "",
                    target_item.text().strip() if target_item is not None else "",
                )
            )
        return rows

    def _file_volume_rows(self) -> list[tuple[str, str, str]]:
        rows = []
        for row in range(self.app_file_volumes_table.rowCount()):
            name_item = self.app_file_volumes_table.item(row, 0)
            mount_item = self.app_file_volumes_table.item(row, 1)
            rows.append(
                (
                    name_item.text().strip() if name_item is not None else "",
                    mount_item.text().strip() if mount_item is not None else "",
                    str(name_item.data(Qt.UserRole) if name_item is not None else ""),
                )
            )
        return rows

    def _validate_volume_values(self, source: str, mount_path: str) -> ValidationIssue | None:
        if not source or not mount_path:
            return ValidationIssue("volumes", "Volume source and mount path are required.")
        if not mount_path.startswith("/"):
            return ValidationIssue("volumes", "Volume mount path must start with /.")
        return None

    def _validate_file_volume_values(
        self,
        name: str,
        mount_path: str,
        content: str,
    ) -> ValidationIssue | None:
        if not name or not mount_path:
            return ValidationIssue("file_volumes", "File volume name and mount path are required.")
        if not mount_path.startswith("/"):
            return ValidationIssue("file_volumes", "File volume mount path must start with /.")
        if not content.strip():
            return ValidationIssue("file_volumes", "File volume content is required.")
        issues = validate_file_volumes(
            {name: FileVolumeSpec(content=content, mounting_point=mount_path)}
        )
        if issues:
            return issues[0]
        return None

    def _find_volume_row(self, source: str) -> int | None:
        for row, (row_source, _mount_path) in enumerate(self._volume_rows()):
            if row_source == source:
                return row
        return None

    def _find_file_volume_row(self, name: str) -> int | None:
        for row, (row_name, _mount_path, _content) in enumerate(self._file_volume_rows()):
            if row_name == name:
                return row
        return None

    def _find_file_volume_mount_row(self, mount_path: str) -> int | None:
        for row, (_row_name, row_mount_path, _content) in enumerate(self._file_volume_rows()):
            if row_mount_path == mount_path:
                return row
        return None

    def _append_volume_row(self, source: str, mount_path: str) -> None:
        row = self.app_volumes_table.rowCount()
        self.app_volumes_table.insertRow(row)
        self.app_volumes_table.setItem(row, 0, QTableWidgetItem(source))
        self.app_volumes_table.setItem(row, 1, QTableWidgetItem(mount_path))

    def _append_file_volume_row(self, name: str, mount_path: str, content: str) -> None:
        row = self.app_file_volumes_table.rowCount()
        self.app_file_volumes_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.UserRole, content)
        name_item.setToolTip("Content is kept in memory until launch and is not shown in the table.")
        mount_item = QTableWidgetItem(mount_path)
        mount_item.setToolTip(mount_path)
        self.app_file_volumes_table.setItem(row, 0, name_item)
        self.app_file_volumes_table.setItem(row, 1, mount_item)

    def _parse_resources(self) -> tuple[AppResourceSpec, list[ValidationIssue]]:
        try:
            cpu = float(self.app_cpu_input.text().strip())
        except ValueError:
            return AppResourceSpec(), [ValidationIssue("resources.cpu", "CPU must be numeric.")]
        return (
            AppResourceSpec(
                cpu=cpu,
                memory=self.app_memory_input.text().strip() or "512m",
            ),
            [],
        )

    def _persist_result_if_needed(self, result: DeploymentResult, spec) -> None:
        if self.app_registry.get(result.app_id) is not None:
            return
        self.app_registry.upsert(result.to_record(metadata=spec.to_record_metadata()))

    def _handle_launch_success(self, result: DeploymentResult, spec) -> None:
        self._persist_result_if_needed(result, spec)
        self.refresh_apps(selected_app_id=result.app_id)
        self._show_message("Launched", error=False)
        self._log_event(
            "SDK Apps launch complete: "
            f"type={result.app_type} app={result.app_name} status={result.status} url={'yes' if result.app_url else 'no'}",
            color="green",
        )
        if self._active_create_dialog is not None:
            self._active_create_dialog.accept()

    def _handle_refresh_success(self, statuses: list[SdkAppStatus]) -> None:
        selected = self._selected_record()
        selected_app_id = selected.app_id if selected is not None else None
        records = self.app_registry.list_apps()
        changed = 0
        for record in records:
            status = _matching_status(record, statuses)
            if status is None:
                continue
            self._apply_status_to_record(record, status)
            self.app_registry.upsert(record)
            changed += 1
        self.refresh_apps(selected_app_id=selected_app_id)
        self._show_message("Status updated" if changed else "No launcher-owned status changes", error=False)
        self._log_event(
            f"SDK Apps refresh complete: statuses={len(statuses or [])} updated={changed}",
            color="green" if changed else "blue",
        )

    def _apply_status_to_record(self, record: ManagedAppRecord, status: SdkAppStatus) -> None:
        checked_at = utc_now_iso()
        record.status = status.status
        if status.url:
            record.app_url = status.url
        record.last_action = "status refreshed"
        record.updated_at = checked_at

        metadata = dict(record.metadata or {})
        metadata["last_status_checked_at"] = checked_at
        safe_error = redact_secret_text(status.last_error).strip()
        if safe_error:
            metadata["last_error"] = safe_error
        else:
            metadata.pop("last_error", None)
        record.metadata = redact_secrets(metadata)

    def _start_sdk_operation(self, operation_name: str, operation, on_success, message: str) -> None:
        self._set_busy(True, message)
        self._log_event(f"SDK Apps {operation_name} started", color="blue")
        worker = SdkOperationThread(operation_name, operation, parent=self)
        self._active_workers.append(worker)
        worker.operation_finished.connect(
            lambda _name, result, item=worker: self._finish_sdk_operation(item, on_success, result)
        )
        worker.operation_failed.connect(
            lambda _name, error, item=worker: self._fail_sdk_operation(item, error)
        )
        worker.finished.connect(lambda item=worker: self._cleanup_worker(item))
        worker.start()

    def _finish_sdk_operation(self, worker: SdkOperationThread, on_success, result) -> None:
        self._set_busy(False)
        on_success(result)

    def _fail_sdk_operation(self, worker: SdkOperationThread, error: str) -> None:
        self._set_busy(False)
        safe_error = self._redact_active_secrets(error)
        error_message = classify_sdk_error(safe_error)
        self._show_message(error_message.user_message, error=True)
        self._log_event(
            f"SDK Apps {worker.operation_name} failed: {error_message.user_message}",
            color="red",
        )
        if error_message.classified:
            diagnostic = (
                f"SDK Apps {worker.operation_name} diagnostic "
                f"({error_message.category}): {error_message.diagnostic}"
            )
            self._log_event(
                diagnostic,
                color="red",
                debug=True,
            )

    def _cleanup_worker(self, worker: SdkOperationThread) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        worker.deleteLater()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        for button in (
            getattr(self, "create_app_button", None),
            getattr(self, "launch_button", None),
            getattr(self, "refresh_button", None),
            getattr(self, "stop_button", None),
            getattr(self, "copy_url_button", None),
            getattr(self, "check_sdk_access_button", None),
            getattr(self, "sdk_settings_button", None),
            getattr(self, "validate_button", None),
            getattr(self, "create_cancel_button", None),
        ):
            if button is not None:
                button.setEnabled(not busy)
        if message:
            self._show_message(message, error=False)

    def _selected_record(self) -> ManagedAppRecord | None:
        selected = self.apps_table.selectionModel().selectedRows()
        if not selected:
            return None
        return self._records_by_row.get(selected[0].row())

    def _emit_selected_record_changed(self) -> None:
        self.selected_record_changed.emit(self._selected_record())

    def _set_table_item(self, row: int, column: int, value: str, tooltip: str = "") -> None:
        item = QTableWidgetItem(value or "-")
        item.setToolTip(tooltip or value or "")
        self.apps_table.setItem(row, column, item)

    def _configure_apps_table_columns(self) -> None:
        header = self.apps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setStretchLastSection(True)

    def _sync_runner_stack(self) -> None:
        is_container = self.runner_type_combo.currentData() == APP_TYPE_CONTAINER
        self.runner_stack.setCurrentIndex(0 if is_container else 1)
        if hasattr(self, "app_tunnel_engine_combo"):
            default_engine = "ngrok" if is_container else "cloudflare"
            index = self.app_tunnel_engine_combo.findText(default_engine)
            if index >= 0:
                self.app_tunnel_engine_combo.setCurrentIndex(index)

    def _connect_form_message_reset(self) -> None:
        self.runner_type_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
        self.node_address_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
        for widget in (
            self.app_name_input,
            self.node_address_input,
            self.car_image_input,
            self.car_port_input,
            self.car_registry_input,
            self.car_registry_user_input,
            self.car_registry_password_input,
            self.worker_repo_input,
            self.worker_branch_input,
            self.worker_image_input,
            self.worker_port_input,
            self.worker_github_user_input,
            self.worker_github_token_input,
            self.worker_registry_input,
            self.worker_registry_user_input,
            self.worker_registry_password_input,
            self.worker_vcs_poll_input,
            self.app_cpu_input,
            self.app_memory_input,
            self.app_volume_source_input,
            self.app_volume_mount_input,
            self.app_file_volume_name_input,
            self.app_file_volume_mount_input,
        ):
            widget.textChanged.connect(lambda *_args: self._clear_message())
        self.env_input.textChanged.connect(self._clear_message)
        self.app_file_volume_content_input.textChanged.connect(self._clear_message)
        self.worker_commands_input.textChanged.connect(self._clear_message)
        self.app_restart_policy_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
        self.app_pull_policy_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
        self.app_tunnel_engine_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
        self.app_tunnel_enabled_checkbox.stateChanged.connect(lambda *_args: self._clear_message())

    def _clear_message(self) -> None:
        message_label = self._message_label()
        if message_label.text() in {
            "Launching...",
            "Refreshing...",
            "Stopping...",
            "Checking SDK access...",
        }:
            return
        self._show_message("", error=False)

    def _show_message(self, text: str, *, error: bool) -> None:
        message_label = self._message_label()
        message_label.setText(text)
        message_label.setVisible(bool(text))
        message_label.setProperty("state", "error" if error else "ok")
        message_label.style().unpolish(message_label)
        message_label.style().polish(message_label)

    def _message_label(self) -> QLabel:
        if (
            self._active_create_dialog is not None
            and self._active_create_dialog.isVisible()
            and hasattr(self, "validation_message")
        ):
            return self.validation_message
        return self.management_message

    def _log_event(self, message: str, *, color: str = "blue", debug: bool = False) -> None:
        if self.event_logger is None:
            return
        self.event_logger(self._redact_active_secrets(message), color=color, debug=debug)

    def _redact_active_secrets(self, text: str) -> str:
        safe_text = str(text)
        for value in (
            getattr(self, "car_registry_password_input", None),
            getattr(self, "worker_github_token_input", None),
            getattr(self, "worker_registry_password_input", None),
            getattr(self, "app_file_volume_content_input", None),
        ):
            if value is None:
                continue
            try:
                secret = value.toPlainText() if hasattr(value, "toPlainText") else value.text()
            except RuntimeError:
                continue
            if secret:
                safe_text = safe_text.replace(secret, REDACTED_SECRET)
        return safe_text

    def _create_line_edit(self, object_name: str, placeholder: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setObjectName(object_name)
        widget.setAccessibleName(placeholder)
        widget.setPlaceholderText(placeholder)
        widget.setProperty("role", "appTextInput")
        widget.setMinimumHeight(34)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return widget

    def _create_plain_text(self, object_name: str, placeholder: str) -> QPlainTextEdit:
        widget = QPlainTextEdit()
        widget.setObjectName(object_name)
        widget.setAccessibleName(placeholder)
        widget.setPlaceholderText(placeholder)
        widget.setProperty("role", "appTextInput")
        widget.setMinimumHeight(54)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return widget

    def _create_combo(self, object_name: str, accessible_name: str) -> QComboBox:
        widget = QComboBox()
        widget.setObjectName(object_name)
        widget.setAccessibleName(accessible_name)
        widget.setProperty("role", "appCombo")
        widget.setMinimumHeight(34)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return widget

    def _add_grid_field(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        text: str,
        object_name: str,
        widget: QWidget,
        column_span: int = 1,
    ) -> None:
        label_row = row * 2
        layout.addWidget(self._label(text, object_name), label_row, column, 1, column_span)
        layout.addWidget(widget, label_row + 1, column, 1, column_span)

    def _label(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(text)
        label.setProperty("role", "appFormLabel")
        return label

    def _set_workspace_button_size(self, button: QPushButton, height: int) -> None:
        button.setMinimumHeight(height)
        button.setMaximumHeight(height)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


def _to_int(value: str) -> int:
    return int((value or "").strip())


def _format_issue(issue: ValidationIssue) -> str:
    return f"{issue.field}: {issue.message}"


def _matching_status(record: ManagedAppRecord, statuses: list[SdkAppStatus]) -> SdkAppStatus | None:
    for status in statuses or []:
        if status.node_address and status.node_address != record.node_address:
            continue
        if status.app_name and status.app_name != record.app_name:
            continue
        if status.plugin_signature and status.plugin_signature != record.plugin_signature:
            continue
        return status
    return None


def _short_node_address(value: str) -> str:
    normalized = (value or "").strip()
    if len(normalized) <= 24:
        return normalized or "-"
    return f"{normalized[:8]}...{normalized[-6:]}"
