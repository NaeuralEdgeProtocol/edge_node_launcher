from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHeaderView,
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
    ContainerAppSpec,
    DeploymentResult,
    ManagedAppRecord,
    WorkerAppSpec,
)
from services.app_deployment_validation import (
    ValidationIssue,
    validate_container_spec,
    validate_worker_spec,
)
from services.app_registry import AppRegistry
from widgets.app_widgets.sidebar_controls import (
    create_sidebar_action_button,
    create_sidebar_section_label,
)


class AppsPage(QWidget):
    """Compact CAR/WAR app deployment and launcher-owned app registry page."""

    def __init__(self, *, app_registry=None, deployment_client=None, parent=None):
        super().__init__(parent)
        self.app_registry = app_registry or AppRegistry()
        self.deployment_client = deployment_client
        self._records_by_row: dict[int, ManagedAppRecord] = {}

        self._init_layout()
        self.refresh_apps()

    def _init_layout(self) -> None:
        self.setObjectName("appsPage")
        self.setAccessibleName("Apps page")
        self.setProperty("role", "navigationPage")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(create_sidebar_section_label("Apps", "appsPageSectionLabel"))

        self.apps_table = QTableWidget(0, 3)
        self.apps_table.setObjectName("appsTable")
        self.apps_table.setAccessibleName("Launcher-owned apps")
        self.apps_table.setHorizontalHeaderLabels(["Name", "Type", "Status"])
        self.apps_table.verticalHeader().hide()
        self.apps_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.apps_table.setSelectionMode(QTableWidget.SingleSelection)
        self.apps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.apps_table.setAlternatingRowColors(False)
        self.apps_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.apps_table.setMinimumHeight(104)
        self.apps_table.setMaximumHeight(122)
        self.apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.apps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.apps_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.apps_table)

        self.refresh_button = create_sidebar_action_button(
            "Refresh Apps",
            "appRefreshButton",
            "secondary",
            "Refresh launcher-owned app list",
            self.refresh_apps,
        )
        layout.addWidget(self.refresh_button)

        self.stop_button = create_sidebar_action_button(
            "Stop Selected",
            "appStopButton",
            "utility",
            "Stop selected launcher-owned app",
            self.stop_selected_app,
        )
        layout.addWidget(self.stop_button)

        self.copy_url_button = create_sidebar_action_button(
            "Copy URL",
            "appCopyUrlButton",
            "utility",
            "Copy selected app URL",
            self.copy_selected_url,
        )
        layout.addWidget(self.copy_url_button)

        self.runner_type_combo = self._create_combo("appRunnerTypeCombo", "App runner type")
        self.runner_type_combo.addItem("Container", APP_TYPE_CONTAINER)
        self.runner_type_combo.addItem("Worker", APP_TYPE_WORKER)
        layout.addWidget(self._label("Runner", "appRunnerTypeLabel"))
        layout.addWidget(self.runner_type_combo)

        self.app_name_input = self._create_line_edit("appNameInput", "App name")
        layout.addWidget(self._label("App name", "appNameLabel"))
        layout.addWidget(self.app_name_input)

        self.node_address_input = self._create_line_edit("appNodeAddressInput", "0xai_...")
        layout.addWidget(self._label("Target node", "appNodeAddressLabel"))
        layout.addWidget(self.node_address_input)

        self.validation_message = QLabel("")
        self.validation_message.setObjectName("appValidationMessageLabel")
        self.validation_message.setAccessibleName("App validation message")
        self.validation_message.setProperty("role", "appValidationMessage")
        self.validation_message.setWordWrap(True)
        self.validation_message.hide()
        layout.addWidget(self.validation_message)

        self.validate_button = create_sidebar_action_button(
            "Validate",
            "appValidateButton",
            "secondary",
            "Validate app deployment fields",
            self.validate_current_form,
        )
        layout.addWidget(self.validate_button)

        self.launch_button = create_sidebar_action_button(
            "Launch App",
            "appLaunchButton",
            "primary",
            "Launch selected app through the Ratio1 SDK",
            self.launch_current_app,
        )
        layout.addWidget(self.launch_button)

        self.runner_stack = QStackedWidget()
        self.runner_stack.setObjectName("appRunnerStack")
        self.runner_stack.setAccessibleName("App runner form fields")
        self.runner_stack.addWidget(self._create_container_fields())
        self.runner_stack.addWidget(self._create_worker_fields())
        layout.addWidget(self.runner_stack)
        self.runner_type_combo.currentIndexChanged.connect(self._sync_runner_stack)

        self.env_input = self._create_plain_text("appEnvInput", "KEY=value")
        self.env_input.setMaximumHeight(72)
        layout.addWidget(self._label("Environment", "appEnvLabel"))
        layout.addWidget(self.env_input)
        layout.addStretch(1)
        self._sync_runner_stack()

    def _create_container_fields(self) -> QWidget:
        page = QWidget()
        page.setObjectName("containerAppFields")
        page.setAccessibleName("Container app fields")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

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

        for text, name, widget in (
            ("Image", "carImageLabel", self.car_image_input),
            ("Port", "carPortLabel", self.car_port_input),
            ("Registry", "carRegistryLabel", self.car_registry_input),
            ("Registry user", "carRegistryUserLabel", self.car_registry_user_input),
            ("Registry password", "carRegistryPasswordLabel", self.car_registry_password_input),
        ):
            layout.addWidget(self._label(text, name))
            layout.addWidget(widget)

        return page

    def _create_worker_fields(self) -> QWidget:
        page = QWidget()
        page.setObjectName("workerAppFields")
        page.setAccessibleName("Worker app fields")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

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

        for text, name, widget in (
            ("GitHub repo", "workerRepoLabel", self.worker_repo_input),
            ("Branch", "workerBranchLabel", self.worker_branch_input),
            ("Base image", "workerImageLabel", self.worker_image_input),
            ("Port", "workerPortLabel", self.worker_port_input),
            ("GitHub user", "workerGithubUserLabel", self.worker_github_user_input),
            ("GitHub token", "workerGithubTokenLabel", self.worker_github_token_input),
            ("Commands", "workerCommandsLabel", self.worker_commands_input),
        ):
            layout.addWidget(self._label(text, name))
            layout.addWidget(widget)

        return page

    def set_target_node_address(self, node_address: str) -> None:
        if node_address and not self.node_address_input.text().strip():
            self.node_address_input.setText(node_address)

    def validate_current_form(self):
        spec, issues = self._build_current_spec()
        if issues:
            self._show_message(_format_issue(issues[0]), error=True)
            return None
        self._show_message("Ready", error=False)
        return spec

    def launch_current_app(self) -> None:
        spec = self.validate_current_form()
        if spec is None:
            return
        if self.deployment_client is None:
            self._show_message("SDK launch worker pending", error=True)
            return
        try:
            if spec.app_type == APP_TYPE_CONTAINER:
                result = self.deployment_client.launch_container_app(spec)
            else:
                result = self.deployment_client.launch_worker_app(spec)
            self._persist_result_if_needed(result, spec)
            self.refresh_apps()
            self._show_message("Launched", error=False)
        except Exception as exc:
            self._show_message(str(exc), error=True)

    def refresh_apps(self) -> None:
        records = self.app_registry.list_apps()
        self._records_by_row = {}
        self.apps_table.setRowCount(len(records))
        for row, record in enumerate(records):
            self._records_by_row[row] = record
            details = (
                f"Node: {record.node_address}\n"
                f"Pipeline: {record.pipeline_name}\n"
                f"URL: {record.app_url or '-'}"
            )
            self._set_table_item(row, 0, record.app_name, details)
            self._set_table_item(row, 1, record.app_type)
            self._set_table_item(row, 2, record.status)
        self.apps_table.resizeColumnsToContents()

    def stop_selected_app(self) -> None:
        record = self._selected_record()
        if record is None:
            self._show_message("Select an app first", error=True)
            return
        if self.deployment_client is not None:
            try:
                self.deployment_client.stop_app(record.node_address, record.pipeline_name)
            except Exception as exc:
                self._show_message(str(exc), error=True)
                return
        record.status = "stopped"
        record.last_action = "stopped"
        self.app_registry.upsert(record)
        self.refresh_apps()
        self._show_message("Stopped", error=False)

    def copy_selected_url(self) -> None:
        record = self._selected_record()
        if record is None or not record.app_url:
            self._show_message("No URL selected", error=True)
            return
        QApplication.clipboard().setText(record.app_url)
        self._show_message("URL copied", error=False)

    def _build_current_spec(self):
        env, env_issues = self._parse_env()
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
                )
                return spec, [*env_issues, *validate_container_spec(spec)]

            spec = WorkerAppSpec(
                app_name=self.app_name_input.text().strip(),
                node_address=self.node_address_input.text().strip(),
                repo_url=self.worker_repo_input.text().strip(),
                branch=self.worker_branch_input.text().strip() or "main",
                image=self.worker_image_input.text().strip() or "node:22",
                port=_to_int(self.worker_port_input.text()),
                github_username=self.worker_github_user_input.text().strip(),
                github_token=self.worker_github_token_input.text(),
                commands=[
                    line.strip()
                    for line in self.worker_commands_input.toPlainText().splitlines()
                    if line.strip()
                ],
                env=env,
            )
            return spec, [*env_issues, *validate_worker_spec(spec)]
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

    def _persist_result_if_needed(self, result: DeploymentResult, spec) -> None:
        if self.app_registry.get(result.app_id) is not None:
            return
        self.app_registry.upsert(result.to_record(metadata=spec.to_record_metadata()))

    def _selected_record(self) -> ManagedAppRecord | None:
        selected = self.apps_table.selectionModel().selectedRows()
        if not selected:
            return None
        return self._records_by_row.get(selected[0].row())

    def _set_table_item(self, row: int, column: int, value: str, tooltip: str = "") -> None:
        item = QTableWidgetItem(value or "-")
        item.setToolTip(tooltip or value or "")
        self.apps_table.setItem(row, column, item)

    def _sync_runner_stack(self) -> None:
        self.runner_stack.setCurrentIndex(0 if self.runner_type_combo.currentData() == APP_TYPE_CONTAINER else 1)

    def _show_message(self, text: str, *, error: bool) -> None:
        self.validation_message.setText(text)
        self.validation_message.setVisible(bool(text))
        self.validation_message.setProperty("state", "error" if error else "ok")
        self.validation_message.style().unpolish(self.validation_message)
        self.validation_message.style().polish(self.validation_message)

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

    def _label(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(text)
        label.setProperty("role", "appFormLabel")
        return label


def _to_int(value: str) -> int:
    return int((value or "").strip())


def _format_issue(issue: ValidationIssue) -> str:
    return f"{issue.field}: {issue.message}"
