from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.app_deployment_models import (
    APP_TYPE_CONTAINER,
    APP_TYPE_WORKER,
    AppResourceSpec,
    ContainerAppSpec,
    DeploymentResult,
    ManagedAppRecord,
    SdkAppStatus,
    WorkerAppSpec,
)
from services.app_deployment_validation import (
    ValidationIssue,
    validate_container_spec,
    validate_worker_spec,
)
from services.app_registry import AppRegistry
from services.app_secret_redaction import REDACTED_SECRET
from services.sdk_error_messages import classify_sdk_error
from services.sdk_operation_worker import SdkOperationThread
from widgets.app_widgets.sidebar_controls import (
    create_sidebar_action_button,
    create_sidebar_section_label,
)


class AppsPage(QWidget):
    """CAR/WAR app deployment and launcher-owned app registry page."""

    selected_record_changed = pyqtSignal(object)

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

        app_actions = QWidget()
        app_actions.setObjectName("appManagementActionBar")
        app_actions.setAccessibleName("App management actions")
        app_actions.setProperty("role", "appActionBar")
        actions_layout = QHBoxLayout(app_actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.refresh_button = create_sidebar_action_button(
            "Refresh Apps",
            "appRefreshButton",
            "secondary",
            "Refresh launcher-owned app list",
            self.refresh_app_statuses,
        )
        self._set_workspace_button_size(self.refresh_button, 40)
        actions_layout.addWidget(self.refresh_button)

        self.stop_button = create_sidebar_action_button(
            "Stop Selected",
            "appStopButton",
            "utility",
            "Stop selected launcher-owned app",
            self.stop_selected_app,
        )
        self._set_workspace_button_size(self.stop_button, 40)
        actions_layout.addWidget(self.stop_button)

        self.copy_url_button = create_sidebar_action_button(
            "Copy URL",
            "appCopyUrlButton",
            "utility",
            "Copy selected app URL",
            self.copy_selected_url,
        )
        self._set_workspace_button_size(self.copy_url_button, 40)
        actions_layout.addWidget(self.copy_url_button)
        layout.addWidget(app_actions)

        layout.addWidget(create_sidebar_section_label("Deployment", "appDeploymentSectionLabel"))

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

        self.node_address_input = self._create_line_edit("appNodeAddressInput", "0xai_...")
        self._add_grid_field(core_grid, 1, 0, "Target node", "appNodeAddressLabel", self.node_address_input, 2)
        deployment_layout.addLayout(core_grid)

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
            "Launch App",
            "appLaunchButton",
            "primary",
            "Launch selected app through the Ratio1 SDK",
            self.launch_current_app,
        )
        self._set_workspace_button_size(self.launch_button, 44)
        launch_actions_layout.addWidget(self.launch_button, 2)
        deployment_layout.addWidget(launch_actions)

        self.runner_stack = QStackedWidget()
        self.runner_stack.setObjectName("appRunnerStack")
        self.runner_stack.setAccessibleName("App runner form fields")
        self.runner_stack.addWidget(self._create_container_fields())
        self.runner_stack.addWidget(self._create_worker_fields())
        deployment_layout.addWidget(self.runner_stack)
        self.runner_type_combo.currentIndexChanged.connect(self._sync_runner_stack)

        deployment_layout.addWidget(create_sidebar_section_label("Runtime", "appRuntimeSectionLabel"))
        deployment_layout.addWidget(self._create_runtime_fields())

        self.env_input = self._create_plain_text("appEnvInput", "KEY=value")
        self.env_input.setMaximumHeight(86)
        deployment_layout.addWidget(self._label("Environment", "appEnvLabel"))
        deployment_layout.addWidget(self.env_input)
        layout.addWidget(deployment_panel)
        layout.addStretch(1)
        self._sync_runner_stack()
        self._connect_form_message_reset()

    def _create_container_fields(self) -> QWidget:
        page = QWidget()
        page.setObjectName("containerAppFields")
        page.setAccessibleName("Container app fields")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
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

        return page

    def _create_worker_fields(self) -> QWidget:
        page = QWidget()
        page.setObjectName("workerAppFields")
        page.setAccessibleName("Worker app fields")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
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

        return page

    def _create_runtime_fields(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("appRuntimePanel")
        panel.setAccessibleName("App runtime settings")
        panel.setProperty("role", "appRuntimePanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
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
        self.app_volumes_input = self._create_plain_text(
            "appVolumesInput",
            "volume_name:/container/path",
        )
        self.app_volumes_input.setMaximumHeight(64)

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
        self._add_grid_field(layout, 2, 0, "Volumes", "appVolumesLabel", self.app_volumes_input, 2)
        return panel

    def set_launch_preflight_service(self, launch_preflight_service) -> None:
        self.launch_preflight_service = launch_preflight_service

    def set_event_logger(self, event_logger) -> None:
        self.event_logger = event_logger

    def set_target_node_address(self, node_address: str) -> None:
        self.set_target_node(node_address=node_address)

    def set_target_node(self, *, node_address: str = "", container_name: str | None = None) -> None:
        if container_name is not None:
            self.target_container_name = container_name
        if node_address and not self.node_address_input.text().strip():
            self.node_address_input.setText(node_address)

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

    def _launch_with_preflight(self, launch_operation, target_container_name: str):
        if self.launch_preflight_service is not None:
            self.launch_preflight_service.prepare(target_container_name)
        return launch_operation()

    def refresh_app_statuses(self) -> None:
        if self.deployment_client is None:
            self.refresh_apps()
            self._show_message("Refreshed", error=False)
            self._log_event("SDK Apps refresh used local registry because deployment client is not configured", color="blue")
            return
        node_address = self.node_address_input.text().strip()
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
        resources, resource_issues = self._parse_resources()
        common_issues = [*env_issues, *volume_issues, *resource_issues]
        try:
            if self.runner_type_combo.currentData() == APP_TYPE_CONTAINER:
                spec = ContainerAppSpec(
                    app_name=self.app_name_input.text().strip(),
                    node_address=self.node_address_input.text().strip(),
                    image=self.car_image_input.text().strip(),
                    port=_to_int(self.car_port_input.text()),
                    registry_server=self.car_registry_input.text().strip() or "docker.io",
                    registry_username=self.car_registry_user_input.text().strip(),
                    registry_password=self.car_registry_password_input.text(),
                    env=env,
                    volumes=volumes,
                    resources=resources,
                    restart_policy=self.app_restart_policy_combo.currentText(),
                    image_pull_policy=self.app_pull_policy_combo.currentText(),
                )
                return spec, [*common_issues, *validate_container_spec(spec)]

            spec = WorkerAppSpec(
                app_name=self.app_name_input.text().strip(),
                node_address=self.node_address_input.text().strip(),
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
                resources=resources,
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
        for line in self.app_volumes_input.toPlainText().splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if ":" not in normalized:
                issues.append(ValidationIssue("volumes", "Volume rows must use source:/container/path."))
                continue
            source, target = normalized.rsplit(":", 1)
            source = source.strip()
            target = target.strip()
            if not source or not target:
                issues.append(ValidationIssue("volumes", "Volume source and mount path are required."))
                continue
            volumes[source] = target
        return volumes, issues

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

    def _handle_refresh_success(self, statuses: list[SdkAppStatus]) -> None:
        selected = self._selected_record()
        selected_app_id = selected.app_id if selected is not None else None
        records = self.app_registry.list_apps()
        changed = 0
        for record in records:
            status = _matching_status(record, statuses)
            if status is None:
                continue
            record.status = status.status
            if status.url:
                record.app_url = status.url
            self.app_registry.upsert(record)
            changed += 1
        self.refresh_apps(selected_app_id=selected_app_id)
        self._show_message("Status updated" if changed else "No launcher-owned status changes", error=False)
        self._log_event(
            f"SDK Apps refresh complete: statuses={len(statuses or [])} updated={changed}",
            color="green" if changed else "blue",
        )

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
            self.launch_button,
            self.refresh_button,
            self.stop_button,
            self.copy_url_button,
            self.validate_button,
        ):
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
        self.runner_stack.setCurrentIndex(0 if self.runner_type_combo.currentData() == APP_TYPE_CONTAINER else 1)

    def _connect_form_message_reset(self) -> None:
        self.runner_type_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
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
        ):
            widget.textChanged.connect(lambda *_args: self._clear_message())
        self.env_input.textChanged.connect(self._clear_message)
        self.worker_commands_input.textChanged.connect(self._clear_message)
        self.app_volumes_input.textChanged.connect(self._clear_message)
        self.app_restart_policy_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())
        self.app_pull_policy_combo.currentIndexChanged.connect(lambda *_args: self._clear_message())

    def _clear_message(self) -> None:
        if self.validation_message.text() in {"Launching...", "Refreshing...", "Stopping..."}:
            return
        self._show_message("", error=False)

    def _show_message(self, text: str, *, error: bool) -> None:
        self.validation_message.setText(text)
        self.validation_message.setVisible(bool(text))
        self.validation_message.setProperty("state", "error" if error else "ok")
        self.validation_message.style().unpolish(self.validation_message)
        self.validation_message.style().polish(self.validation_message)

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
        ):
            if value is None:
                continue
            secret = value.text()
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
