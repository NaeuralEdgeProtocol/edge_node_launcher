import time

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QShowEvent
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QWidget,
)

from models.NodeHistory import NodeHistory
from models.NodeInfo import NodeInfo
from services.app_deployment_models import DeploymentResult, ManagedAppRecord
from services.app_deployment_models import SdkAppStatus
from services.app_registry import AppRegistry
from widgets.DockerPullDialog import DOCKER_PULL_DIALOG_STYLE_COLORS, DockerPullDialog
from widgets.LoadingDialog import LoadingDialog
from widgets.CenteredComboBox import CenteredComboBox
from widgets.loading_indicator import LoadingIndicator
from app_forms.frm_utils import LoadingIndicator as LegacyLoadingIndicator
from widgets.app_widgets.activity_log import ACTIVITY_LOG_COLOR_MAP, ActivityLogWidget
from widgets.app_widgets.apps_page import AppsPage
from widgets.app_widgets.config_editor import ConfigEditorWidget
from widgets.app_widgets.container_list import CONTAINER_LIST_EMPTY_TEXT, ContainerListWidget
from widgets.app_widgets.dashboard_panel import DashboardPanel
from widgets.app_widgets.log_console import MAX_LOG_LINES, LogConsoleWidget
from widgets.app_widgets.metric_plot_grid import (
    METRIC_AXIS_COLOR,
    METRIC_EMPTY_STATE_TEXT,
    METRIC_EMPTY_STATE_MIN_HEIGHT,
    METRIC_GRID_ALPHA,
    MetricPlotWidget,
    create_metrics_graph_grid,
)
from widgets.app_widgets.metrics_widget import MetricsWidget
from widgets.app_widgets.node_info import NodeInfoWidget
from widgets.app_widgets.sidebar_controls import (
    SIDEBAR_ACTION_BUTTON_HEIGHTS,
    SIDEBAR_SECTION_LABEL_HEIGHT,
    create_sidebar_action_button,
    create_sidebar_section_label,
)
from widgets.app_widgets.sidebar_panel import SidebarPanel
from widgets.app_widgets.sidebar_status_cards import NodeStatusPanel, ResourceStatusPanel


APP_TEST_NODE = "0xai_A9OqTV_iFqmwj1SV7AKbdyr66NLkhSQHPpzp40c7jaLn"


class FakeAppDeploymentClient:
    def __init__(self, events=None):
        self.container_specs = []
        self.worker_specs = []
        self.stop_calls = []
        self.list_calls = []
        self.delay_seconds = 0
        self.events = events

    def launch_container_app(self, spec):
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.events is not None:
            self.events.append("launch_container")
        self.container_specs.append(spec)
        return DeploymentResult(
            app_id=f"{spec.node_address}:{spec.pipeline_name}:{spec.app_type}",
            app_name=spec.app_name,
            app_type=spec.app_type,
            node_address=spec.node_address,
            pipeline_name=spec.pipeline_name,
            plugin_signature=spec.plugin_signature,
            instance_id="instance-1",
            app_url="https://car.example",
            status="deployed",
        )

    def launch_worker_app(self, spec):
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.events is not None:
            self.events.append("launch_worker")
        self.worker_specs.append(spec)
        return DeploymentResult(
            app_id=f"{spec.node_address}:{spec.pipeline_name}:{spec.app_type}",
            app_name=spec.app_name,
            app_type=spec.app_type,
            node_address=spec.node_address,
            pipeline_name=spec.pipeline_name,
            plugin_signature=spec.plugin_signature,
            instance_id="instance-2",
            app_url="https://worker.example",
            status="deployed",
        )

    def stop_app(self, node_address, pipeline_name):
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        self.stop_calls.append((node_address, pipeline_name))

    def list_node_apps(self, node_address):
        self.list_calls.append(node_address)
        return [
            SdkAppStatus(
                node_address=node_address,
                app_name="known",
                plugin_signature="CONTAINER_APP_RUNNER",
                instance_id="instance-known",
                status="online",
                url="https://known-live.example",
            )
        ]


class FakeLaunchPreflight:
    def __init__(self, events=None):
        self.calls = []
        self.events = events

    def prepare(self, container_name):
        if self.events is not None:
            self.events.append("preflight")
        self.calls.append(container_name)
        if not container_name:
            raise ValueError("Target container is required for SDK allow-list setup.")


def test_apps_page_exposes_stable_fields_and_actions(qtbot, tmp_path):
    page = AppsPage(app_registry=AppRegistry(tmp_path / "apps.json"))
    qtbot.addWidget(page)

    assert page.objectName() == "appsPage"
    assert page.accessibleName() == "Apps page"
    assert page.property("role") == "navigationPage"
    apps_table = page.findChild(QTableWidget, "appsTable")
    assert apps_table.accessibleName() == "Launcher-owned apps"
    assert apps_table.columnCount() == 4
    assert apps_table.horizontalHeaderItem(3).text() == "Node"
    assert apps_table.horizontalHeader().sectionResizeMode(0) == QHeaderView.Stretch
    assert apps_table.horizontalHeader().sectionResizeMode(3) == QHeaderView.Stretch
    assert apps_table.minimumHeight() >= 136
    assert page.findChild(QWidget, "appManagementActionBar").property("role") == "appActionBar"
    assert page.findChild(QWidget, "appLaunchActionBar").property("role") == "appActionBar"
    assert page.findChild(QWidget, "appDeploymentPanel").property("role") == "appDeploymentPanel"
    assert page.findChild(QComboBox, "appRunnerTypeCombo").currentData() == "CAR"
    assert page.findChild(QLineEdit, "appNameInput").property("role") == "appTextInput"
    assert page.findChild(QLineEdit, "appNodeAddressInput").property("role") == "appTextInput"
    assert page.findChild(QLineEdit, "carImageInput").accessibleName() == "nginx:alpine"
    assert page.findChild(QLineEdit, "workerRepoInput").accessibleName() == "https://github.com/org/repo"
    assert page.findChild(QPlainTextEdit, "workerCommandsInput").property("role") == "appTextInput"
    assert page.findChild(QPushButton, "appValidateButton").property("actionRole") == "secondary"
    assert page.findChild(QPushButton, "appLaunchButton").property("actionRole") == "primary"
    assert page.findChild(QPushButton, "appRefreshButton").property("actionRole") == "secondary"
    assert page.findChild(QPushButton, "appStopButton").property("actionRole") == "utility"
    assert page.findChild(QPushButton, "appCopyUrlButton").property("actionRole") == "utility"


def test_apps_page_validates_and_launches_container_with_fake_sdk(qtbot, tmp_path):
    fake_client = FakeAppDeploymentClient()
    page = AppsPage(
        app_registry=AppRegistry(tmp_path / "apps.json"),
        deployment_client=fake_client,
    )
    qtbot.addWidget(page)

    page.app_name_input.setText("car_runner")
    page.node_address_input.setText(APP_TEST_NODE)
    page.car_image_input.setText("nginx:alpine")
    page.car_port_input.setText("8080")
    page.env_input.setPlainText("PUBLIC_VALUE=1")

    qtbot.mouseClick(page.findChild(QPushButton, "appValidateButton"), Qt.LeftButton)
    assert page.validation_message.text() == "Ready"

    qtbot.mouseClick(page.findChild(QPushButton, "appLaunchButton"), Qt.LeftButton)
    qtbot.waitUntil(lambda: len(fake_client.container_specs) == 1, timeout=1000)

    assert fake_client.container_specs[0].image == "nginx:alpine"
    assert page.apps_table.rowCount() == 1
    assert page.apps_table.item(0, 0).text() == "car_runner"
    assert page.apps_table.item(0, 2).text() == "deployed"

    page.apps_table.selectRow(0)
    qtbot.mouseClick(page.findChild(QPushButton, "appCopyUrlButton"), Qt.LeftButton)
    assert QApplication.clipboard().text() == "https://car.example"

    qtbot.mouseClick(page.findChild(QPushButton, "appStopButton"), Qt.LeftButton)
    qtbot.waitUntil(lambda: len(fake_client.stop_calls) == 1, timeout=1000)
    assert fake_client.stop_calls == [(APP_TEST_NODE, "car_runner")]
    assert page.apps_table.item(0, 2).text() == "stopped"


def test_apps_page_worker_mode_validates_payload(qtbot, tmp_path):
    fake_client = FakeAppDeploymentClient()
    page = AppsPage(
        app_registry=AppRegistry(tmp_path / "apps.json"),
        deployment_client=fake_client,
    )
    qtbot.addWidget(page)

    page.runner_type_combo.setCurrentIndex(1)
    page.app_name_input.setText("worker_runner")
    page.node_address_input.setText(APP_TEST_NODE)
    page.worker_repo_input.setText("https://github.com/Ratio1/example-app")
    page.worker_port_input.setText("4173")

    assert page.runner_stack.currentIndex() == 1

    qtbot.mouseClick(page.findChild(QPushButton, "appLaunchButton"), Qt.LeftButton)
    qtbot.waitUntil(lambda: len(fake_client.worker_specs) == 1, timeout=1000)

    assert fake_client.worker_specs[0].repo_url == "https://github.com/Ratio1/example-app"
    assert fake_client.worker_specs[0].commands == ["npm install", "npm run build", "npm run start"]
    assert page.apps_table.item(0, 1).text() == "WAR"


def test_apps_page_refreshes_registry_records_and_reports_missing_selection(qtbot, tmp_path):
    registry = AppRegistry(tmp_path / "apps.json")
    registry.upsert(
        ManagedAppRecord(
            app_id=f"{APP_TEST_NODE}:known:CAR",
            app_name="known",
            app_type="CAR",
            node_address=APP_TEST_NODE,
            pipeline_name="known",
            plugin_signature="CONTAINER_APP_RUNNER",
            app_url="https://known.example",
            status="deployed",
        )
    )
    page = AppsPage(app_registry=registry)
    qtbot.addWidget(page)

    qtbot.mouseClick(page.findChild(QPushButton, "appRefreshButton"), Qt.LeftButton)

    assert page.apps_table.rowCount() == 1
    assert page.apps_table.item(0, 0).text() == "known"

    page.apps_table.clearSelection()
    qtbot.mouseClick(page.findChild(QPushButton, "appStopButton"), Qt.LeftButton)
    assert page.validation_message.text() == "Select an app first"


def test_apps_page_preserves_selection_and_emits_updated_record_after_stop(qtbot, tmp_path):
    registry = AppRegistry(tmp_path / "apps.json")
    record = ManagedAppRecord(
        app_id=f"{APP_TEST_NODE}:known:CAR",
        app_name="known",
        app_type="CAR",
        node_address=APP_TEST_NODE,
        pipeline_name="known",
        plugin_signature="CONTAINER_APP_RUNNER",
        app_url="https://known.example",
        status="deployed",
        last_action="deployed",
    )
    registry.upsert(record)
    page = AppsPage(app_registry=registry)
    qtbot.addWidget(page)
    emitted = []
    page.selected_record_changed.connect(emitted.append)

    page.apps_table.selectRow(0)
    qtbot.mouseClick(page.findChild(QPushButton, "appStopButton"), Qt.LeftButton)

    assert page.apps_table.item(0, 2).text() == "stopped"
    assert page._selected_record().app_id == record.app_id
    assert page._selected_record().status == "stopped"
    assert emitted[-1].status == "stopped"


def test_apps_page_logs_sdk_events_without_secret_values(qtbot, tmp_path):
    fake_client = FakeAppDeploymentClient()
    events = []
    page = AppsPage(
        app_registry=AppRegistry(tmp_path / "apps.json"),
        deployment_client=fake_client,
        event_logger=lambda message, **kwargs: events.append((message, kwargs)),
    )
    qtbot.addWidget(page)

    page.app_name_input.setText("car_runner")
    page.node_address_input.setText(APP_TEST_NODE)
    page.car_image_input.setText("nginx:alpine")
    page.car_port_input.setText("8080")
    page.car_registry_password_input.setText("super-secret-registry-password")

    qtbot.mouseClick(page.findChild(QPushButton, "appLaunchButton"), Qt.LeftButton)
    qtbot.waitUntil(lambda: len(fake_client.container_specs) == 1, timeout=1000)

    messages = [message for message, _kwargs in events]
    assert any(message.startswith("SDK Apps validation ready:") for message in messages)
    assert any(message.startswith("SDK Apps launch requested:") for message in messages)
    assert any(message.startswith("SDK Apps launch complete:") for message in messages)
    assert all("super-secret-registry-password" not in message for message in messages)
    assert all("cr_password" not in message for message in messages)


def test_apps_page_sdk_operations_run_with_busy_state(qtbot, tmp_path):
    fake_client = FakeAppDeploymentClient()
    fake_client.delay_seconds = 0.05
    page = AppsPage(
        app_registry=AppRegistry(tmp_path / "apps.json"),
        deployment_client=fake_client,
    )
    qtbot.addWidget(page)
    page.app_name_input.setText("car_runner")
    page.node_address_input.setText(APP_TEST_NODE)
    page.car_image_input.setText("nginx:alpine")
    page.car_port_input.setText("8080")

    qtbot.mouseClick(page.findChild(QPushButton, "appLaunchButton"), Qt.LeftButton)

    assert page.launch_button.isEnabled() is False
    assert page.validation_message.text() == "Launching..."

    qtbot.waitUntil(lambda: page.launch_button.isEnabled(), timeout=1000)
    assert page.apps_table.rowCount() == 1


def test_apps_page_launch_runs_preflight_before_sdk_launch(qtbot, tmp_path):
    events = []
    fake_client = FakeAppDeploymentClient(events=events)
    fake_preflight = FakeLaunchPreflight(events=events)
    page = AppsPage(
        app_registry=AppRegistry(tmp_path / "apps.json"),
        deployment_client=fake_client,
        launch_preflight_service=fake_preflight,
    )
    qtbot.addWidget(page)
    page.set_target_node(node_address=APP_TEST_NODE, container_name="r1devnode")
    page.app_name_input.setText("car_runner")
    page.car_image_input.setText("nginx:alpine")
    page.car_port_input.setText("8080")

    qtbot.mouseClick(page.findChild(QPushButton, "appLaunchButton"), Qt.LeftButton)
    qtbot.waitUntil(lambda: len(fake_client.container_specs) == 1, timeout=1000)

    assert fake_preflight.calls == ["r1devnode"]
    assert events == ["preflight", "launch_container"]


def test_apps_page_launch_reports_missing_preflight_container(qtbot, tmp_path):
    fake_client = FakeAppDeploymentClient()
    page = AppsPage(
        app_registry=AppRegistry(tmp_path / "apps.json"),
        deployment_client=fake_client,
        launch_preflight_service=FakeLaunchPreflight(),
    )
    qtbot.addWidget(page)
    page.set_target_node(node_address=APP_TEST_NODE, container_name="old-node")
    page.set_target_node(node_address=APP_TEST_NODE, container_name="")
    page.app_name_input.setText("car_runner")
    page.car_image_input.setText("nginx:alpine")
    page.car_port_input.setText("8080")

    qtbot.mouseClick(page.findChild(QPushButton, "appLaunchButton"), Qt.LeftButton)
    qtbot.waitUntil(
        lambda: "Target container is required" in page.validation_message.text(),
        timeout=1000,
    )

    assert fake_client.container_specs == []


def test_apps_page_clears_stale_status_when_form_changes(qtbot, tmp_path):
    page = AppsPage(app_registry=AppRegistry(tmp_path / "apps.json"))
    qtbot.addWidget(page)
    page.show()
    qtbot.waitUntil(page.isVisible)

    page._show_message("Stopped", error=False)
    assert page.validation_message.isVisible()

    page.app_name_input.setText("next_app")

    assert page.validation_message.text() == ""
    assert not page.validation_message.isVisible()


def test_apps_page_refresh_status_uses_sdk_client_for_existing_records(qtbot, tmp_path):
    fake_client = FakeAppDeploymentClient()
    registry = AppRegistry(tmp_path / "apps.json")
    registry.upsert(
        ManagedAppRecord(
            app_id=f"{APP_TEST_NODE}:known:CAR",
            app_name="known",
            app_type="CAR",
            node_address=APP_TEST_NODE,
            pipeline_name="known",
            plugin_signature="CONTAINER_APP_RUNNER",
            status="deployed",
        )
    )
    page = AppsPage(app_registry=registry, deployment_client=fake_client)
    qtbot.addWidget(page)
    page.node_address_input.setText(APP_TEST_NODE)

    qtbot.mouseClick(page.findChild(QPushButton, "appRefreshButton"), Qt.LeftButton)
    qtbot.waitUntil(lambda: page.apps_table.item(0, 2).text() == "online", timeout=1000)

    assert fake_client.list_calls == [APP_TEST_NODE]
    assert page.apps_table.item(0, 2).text() == "online"
    assert registry.get(f"{APP_TEST_NODE}:known:CAR").app_url == "https://known-live.example"


def test_container_list_updates_selection_and_emits_toggle(qtbot):
    widget = ContainerListWidget()
    qtbot.addWidget(widget)

    assert widget.btn_toggle.objectName() == "containerListToggleButton"
    assert widget.objectName() == "containerListWidget"
    assert widget.accessibleName() == "Container list"
    assert widget.containers_combo.objectName() == "containerListCombo"
    assert isinstance(widget.containers_combo, QComboBox)
    assert not widget.containers_combo.isEditable()
    assert widget.containers_combo.accessibleName() == "Container selector"
    assert widget.containers_combo.toolTip() == "No node containers are available"
    assert widget.containers_combo.minimumHeight() == 36
    assert widget.containers_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert widget.btn_toggle.accessibleName() == "Start selected container"
    assert widget.btn_toggle.toolTip() == "Add a node before starting or stopping a container"
    assert widget.btn_toggle.property("actionRole") == "primary"
    assert widget.btn_toggle.property("state") == "stopped"
    assert widget.btn_add_node.objectName() == "containerListAddNodeButton"
    assert widget.btn_add_node.accessibleName() == "Add node"
    assert widget.btn_add_node.toolTip() == "Add a node container"
    assert widget.btn_add_node.property("actionRole") == "secondary"
    assert widget.containers_combo.currentText() == CONTAINER_LIST_EMPTY_TEXT
    assert not widget.containers_combo.isEnabled()
    assert not widget.btn_toggle.isEnabled()
    assert "QComboBox#containerListCombo" in widget.styleSheet()
    assert 'QPushButton#containerListToggleButton[state="running"]' in widget.styleSheet()

    widget.update_containers(
        [
            {"name": "r1node", "running": False},
            {"name": "r1node2", "running": True},
        ],
        current_container="r1node2",
    )
    widget.update_toggle_button(is_running=True)

    assert widget.get_current_container() == "r1node2"
    assert widget.containers_combo.toolTip() == "Select a node container"
    assert widget.containers_combo.isEnabled()
    assert widget.btn_toggle.isEnabled()
    assert widget.btn_toggle.text() == "Stop Container"
    assert widget.btn_toggle.accessibleName() == "Stop selected container"
    assert widget.btn_toggle.property("state") == "running"
    assert widget.btn_toggle.toolTip() == "Stop selected container"

    with qtbot.waitSignal(widget.container_toggle_requested) as blocker:
        qtbot.mouseClick(widget.btn_toggle, Qt.LeftButton)

    assert blocker.args == ["r1node2"]


def test_container_list_emits_add_container(qtbot):
    widget = ContainerListWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.add_container_requested):
        qtbot.mouseClick(widget.btn_add_node, Qt.LeftButton)


def test_container_list_empty_state_disables_toggle(qtbot):
    widget = ContainerListWidget()
    qtbot.addWidget(widget)
    emitted = []
    widget.container_toggle_requested.connect(emitted.append)

    widget.update_containers([])

    assert widget.get_current_container() is None
    assert widget.containers_combo.currentText() == CONTAINER_LIST_EMPTY_TEXT
    assert not widget.containers_combo.isEnabled()
    assert not widget.btn_toggle.isEnabled()
    assert widget.btn_add_node.isEnabled()

    qtbot.mouseClick(widget.btn_toggle, Qt.LeftButton)

    assert emitted == []


def test_container_list_theme_styles_are_switchable(qtbot):
    widget = ContainerListWidget()
    qtbot.addWidget(widget)

    widget.apply_theme(True)
    assert "#122033" in widget.styleSheet()
    assert "#E8EEF8" in widget.styleSheet()

    widget.apply_theme(False)
    assert "#FFFFFF" in widget.styleSheet()
    assert "#1F2937" in widget.styleSheet()


def test_log_console_adds_and_clears_text(qtbot):
    widget = LogConsoleWidget()
    qtbot.addWidget(widget)

    assert widget.btn_clear.objectName() == "logConsoleClearButton"
    assert widget.objectName() == "logConsoleWidget"
    assert widget.accessibleName() == "Log console"
    assert widget.log_group.objectName() == "logConsoleGroup"
    assert widget.log_group.accessibleName() == "Console log"
    assert widget.log_group.property("role") == "logConsolePanel"
    assert widget.text_console.objectName() == "logConsoleText"
    assert widget.text_console.accessibleName() == "Console log output"
    assert widget.text_console.property("role") == "logConsoleOutput"
    assert not widget.text_console.acceptRichText()
    assert widget.text_console.document().maximumBlockCount() == MAX_LOG_LINES
    assert widget.text_console.placeholderText() == "No log entries yet"
    assert widget.btn_clear.accessibleName() == "Clear console log"
    assert widget.btn_clear.property("actionRole") == "secondary"
    assert widget.btn_clear.toolTip() == "Clear console log"
    assert not widget.btn_clear.isEnabled()
    assert "QGroupBox#logConsoleGroup" in widget.styleSheet()

    widget.add_log("hello", color="green")

    assert "hello" in widget.text_console.toPlainText()
    assert widget.btn_clear.isEnabled()

    qtbot.mouseClick(widget.btn_clear, Qt.LeftButton)

    assert widget.text_console.toPlainText() == ""
    assert not widget.btn_clear.isEnabled()


def test_log_console_theme_styles_are_switchable(qtbot):
    widget = LogConsoleWidget()
    qtbot.addWidget(widget)

    widget.apply_theme(True)
    assert "#122033" in widget.styleSheet()
    assert "#E8EEF8" in widget.styleSheet()

    widget.apply_theme(False)
    assert "#FFFFFF" in widget.styleSheet()
    assert "#1F2937" in widget.styleSheet()


def test_activity_log_widget_appends_copies_and_clears(qtbot):
    widget = ActivityLogWidget(max_blocks=42)
    qtbot.addWidget(widget)

    assert widget.objectName() == "activityLogPanel"
    assert widget.property("role") == "activityLogPanel"
    assert widget.accessibleName() == "Activity log"
    assert widget.header.objectName() == "activityLogHeader"
    assert widget.header.property("role") == "activityLogHeader"
    assert widget.title_label.objectName() == "activityLogTitle"
    assert widget.title_label.text() == "Activity Log"
    assert widget.title_label.property("role") == "dashboardSectionTitle"
    assert widget.title_label.accessibleName() == "Activity log section"
    assert widget.copy_button.objectName() == "activityLogCopyButton"
    assert widget.copy_button.property("role") == "activityLogToolButton"
    assert widget.copy_button.accessibleName() == "Copy activity log"
    assert widget.copy_button.toolTip() == "Copy activity log to clipboard"
    assert widget.clear_button.objectName() == "activityLogClearButton"
    assert widget.clear_button.property("role") == "activityLogToolButton"
    assert widget.clear_button.accessibleName() == "Clear activity log"
    assert widget.clear_button.toolTip() == "Clear activity log"
    assert widget.log_view.objectName() == "logView"
    assert widget.log_view.accessibleName() == "Activity log output"
    assert widget.log_view.isReadOnly()
    assert not widget.log_view.acceptRichText()
    assert widget.log_view.placeholderText() == "No activity yet"
    assert widget.log_view.lineWrapMode() == QTextEdit.WidgetWidth
    assert widget.log_view.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert widget.log_view.document().maximumBlockCount() == 42
    assert not widget.copy_button.isEnabled()
    assert not widget.clear_button.isEnabled()

    widget.append_log_line("first")
    widget.append_log_line("long operational line " + ("x" * 500))
    qtbot.wait(20)

    assert "first" in widget.text()
    assert widget.copy_button.isEnabled()
    assert widget.clear_button.isEnabled()
    assert widget.log_view.horizontalScrollBar().maximum() == widget.log_view.horizontalScrollBar().minimum()

    QApplication.clipboard().clear()
    qtbot.mouseClick(widget.copy_button, Qt.LeftButton)

    assert "long operational line" in QApplication.clipboard().text()
    assert "x" * 500 in QApplication.clipboard().text()

    qtbot.mouseClick(widget.clear_button, Qt.LeftButton)

    assert widget.text() == ""
    assert not widget.copy_button.isEnabled()
    assert not widget.clear_button.isEnabled()


def test_activity_log_widget_applies_semantic_log_colors(qtbot):
    widget = ActivityLogWidget()
    qtbot.addWidget(widget)

    widget.append_log_line("container stopped", color="green")

    first_block = widget.log_view.document().firstBlock()
    first_fragment = first_block.begin().fragment()

    assert first_fragment.text() == "container stopped"
    assert first_fragment.charFormat().foreground().color().name() == QColor(
        ACTIVITY_LOG_COLOR_MAP["green"]
    ).name()


def test_dashboard_panel_owns_splitter_layout(qtbot):
    graph = QWidget()
    graph.setObjectName("graphView")
    activity = ActivityLogWidget()
    moves = []
    panel = DashboardPanel(
        graph,
        activity,
        [600, 180],
        lambda pos, index: moves.append((pos, index)),
    )
    qtbot.addWidget(panel)

    assert panel.objectName() == "dashboardPanel"
    assert panel.graph_view is graph
    assert panel.activity_log_panel is activity
    assert panel.splitter.objectName() == "dashboardSplitter"
    assert panel.splitter.orientation() == Qt.Vertical
    assert not panel.splitter.childrenCollapsible()
    assert panel.splitter.handleWidth() == 8
    assert panel.splitter.widget(0) is graph
    assert panel.splitter.widget(1) is activity
    assert panel.layout().indexOf(panel.splitter) >= 0

    panel.splitter.splitterMoved.emit(100, 1)

    assert moves == [(100, 1)]


def test_sidebar_status_card_panels_expose_stable_controls(qtbot):
    calls = []
    node_panel = NodeStatusPanel(
        lambda: calls.append("node"),
        lambda: calls.append("eth"),
    )
    resource_panel = ResourceStatusPanel()
    qtbot.addWidget(node_panel)
    qtbot.addWidget(resource_panel)

    assert node_panel.objectName() == "infoBox"
    assert node_panel.property("role") == "statusPanel"
    assert node_panel.node_status_title.objectName() == "nodeStatusCardTitle"
    assert node_panel.node_status_title.text() == "Node Details"
    assert node_panel.node_status_title.property("role") == "sidebarCardTitle"
    assert node_panel.edgeImageBadge.objectName() == "edgeImageBadge"
    assert node_panel.edgeImageBadge.property("role") == "edgeImageBadge"
    assert node_panel.edgeImageBadge.accessibleName() == "Edge Node Docker image"
    assert not node_panel.edgeImageBadge.isVisible()
    assert node_panel.node_lifecycle_state.objectName() == "nodeLifecycleStatus"
    assert node_panel.node_lifecycle_state.accessibleName() == "Node lifecycle status"
    assert node_panel.node_lifecycle_state.property("role") == "nodeLifecycleState"
    assert node_panel.node_lifecycle_state.text() == "Status: Stopped"
    assert node_panel.node_runtime_policy.objectName() == "nodeRuntimePolicy"
    assert node_panel.node_runtime_policy.accessibleName() == "Node runtime policy"
    assert node_panel.node_runtime_policy.property("role") == "nodeRuntimePolicy"
    assert node_panel.node_runtime_policy.text() == "Runtime: GPU eligible"
    assert node_panel.addressDisplay.objectName() == "nodeAddressDisplay"
    assert node_panel.addressDisplay.property("statusField") == "address"
    assert node_panel.addressDisplay.font().family() == "Courier New"
    assert node_panel.ethAddressDisplay.objectName() == "nodeEthAddressDisplay"
    assert node_panel.ethAddressDisplay.property("statusField") == "address"
    assert node_panel.copyAddrButton.objectName() == "copyAddrButton"
    assert node_panel.copyAddrButton.accessibleName() == "Copy node address"
    assert node_panel.copyAddrButton.toolTip() == "Copy address"
    assert node_panel.copyEthButton.objectName() == "copyEthButton"
    assert node_panel.copyEthButton.accessibleName() == "Copy ETH address"
    assert node_panel.copyEthButton.toolTip() == "Copy Ethereum address"
    assert not node_panel.copyAddrButton.isVisible()
    assert not node_panel.copyEthButton.isVisible()
    assert node_panel.findChild(QGridLayout, "nodeMetadataGrid") is not None

    for label in (
        node_panel.nameDisplay,
        node_panel.node_lifecycle_state,
        node_panel.node_runtime_policy,
        node_panel.node_uptime,
        node_panel.node_epoch,
        node_panel.node_epoch_avail,
        node_panel.node_version,
    ):
        assert label.property("statusField") == "metadata"
        assert label.font().family() == "Segoe UI"
        assert label.minimumHeight() == 20
        assert label.sizePolicy().verticalPolicy() == QSizePolicy.Fixed

    node_panel.copyAddrButton.click()
    node_panel.copyEthButton.click()
    node_panel.set_edge_image_badge("Devnet", "Using devnet image")

    assert calls == ["node", "eth"]
    assert not node_panel.edgeImageBadge.isHidden()
    assert node_panel.edgeImageBadge.text() == "Devnet"
    assert node_panel.edgeImageBadge.toolTip() == "Using devnet image"

    assert resource_panel.objectName() == "resourcesBox"
    assert resource_panel.property("role") == "resourcePanel"
    assert resource_panel.resource_status_title.objectName() == "resourceStatusCardTitle"
    assert resource_panel.resource_status_title.text() == "Host Resources"
    assert resource_panel.resource_status_title.property("role") == "sidebarCardTitle"
    assert resource_panel.memoryDisplay.objectName() == "memoryResourceDisplay"
    assert resource_panel.memoryDisplay.property("resourceField") == "memory"
    assert resource_panel.vcpusDisplay.objectName() == "cpuResourceDisplay"
    assert resource_panel.vcpusDisplay.property("resourceField") == "cpu"
    assert resource_panel.storageDisplay.objectName() == "storageResourceDisplay"
    assert resource_panel.storageDisplay.property("resourceField") == "storage"


def test_sidebar_control_factories_expose_stable_metadata(qtbot):
    calls = []
    label = create_sidebar_section_label("Network", "networkActionsSectionLabel")
    button = create_sidebar_action_button(
        "Launch dApp",
        "openDappButton",
        "secondary",
        "Open Ratio1 dApp",
        lambda: calls.append("clicked"),
    )
    qtbot.addWidget(label)
    qtbot.addWidget(button)

    assert label.objectName() == "networkActionsSectionLabel"
    assert label.accessibleName() == "Network section"
    assert label.property("role") == "sidebarSection"
    assert label.font().family() == "Segoe UI"
    assert label.minimumHeight() == SIDEBAR_SECTION_LABEL_HEIGHT

    assert button.objectName() == "openDappButton"
    assert button.property("actionRole") == "secondary"
    assert button.toolTip() == "Open Ratio1 dApp"
    assert button.accessibleName() == "Launch dApp"
    assert button.minimumWidth() == 0
    assert button.minimumHeight() == SIDEBAR_ACTION_BUTTON_HEIGHTS["secondary"]
    assert button.maximumHeight() == SIDEBAR_ACTION_BUTTON_HEIGHTS["secondary"]
    assert button.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored

    qtbot.mouseClick(button, Qt.LeftButton)

    assert calls == ["clicked"]


def test_sidebar_panel_exposes_stable_launcher_controls(qtbot):
    calls = []

    def record(name):
        return lambda *args: calls.append(name)

    panel = SidebarPanel(
        is_dark=True,
        force_debug=True,
        add_node_handler=record("add"),
        container_selected_handler=record("select"),
        rename_handler=record("rename"),
        toggle_handler=record("toggle"),
        docker_download_handler=record("docker"),
        dapp_handler=record("dapp"),
        explorer_handler=record("explorer"),
        refresh_handler=record("refresh"),
        copy_address_handler=record("copy_address"),
        copy_eth_handler=record("copy_eth"),
        theme_toggle_handler=record("theme"),
        force_debug_handler=record("debug"),
    )
    qtbot.addWidget(panel)

    assert panel.objectName() == "sidebarPanel"
    assert panel.property("role") == "navigationSidebar"
    assert panel.findChild(QWidget, "sidebarPanel") is None
    assert panel.page_stack.objectName() == "launcherPageStack"
    assert panel.current_page_name() == "nodes"
    assert panel.page_stack.sizeHint().height() == panel.findChild(QWidget, "nodesPage").sizeHint().height()
    assert panel.findChild(QToolButton, "navNodesButton").isChecked()
    assert panel.findChild(QToolButton, "navAppsButton") is not None
    assert panel.findChild(QToolButton, "navLogsButton") is not None
    assert panel.findChild(QToolButton, "navDockerButton") is not None
    assert panel.findChild(QToolButton, "navSettingsButton") is not None
    assert panel.findChild(QToolButton, "navNetworkButton") is not None
    assert panel.add_node_button.objectName() == "addNodeButton"
    assert panel.container_combo.objectName() == "nodeSelectorCombo"
    assert panel.container_combo.accessibleName() == "Node selector"
    assert panel.renameNodeButton.objectName() == "renameNodeButton"
    assert panel.toggleButton.objectName() == "startNodeButton"
    assert panel.docker_download_button.objectName() == "downloadDockerButton"
    assert panel.dapp_button.objectName() == "openDappButton"
    assert panel.explorer_button.objectName() == "openExplorerButton"
    assert panel.refreshButton.objectName() == "refreshNodeInfoButton"
    assert panel.node_status_panel.objectName() == "infoBox"
    assert panel.resource_status_panel.objectName() == "resourcesBox"
    assert panel.themeToggleButton.objectName() == "themeToggleButton"
    assert panel.force_debug_checkbox.objectName() == "forceDebugCheckbox"
    assert panel.force_debug_checkbox.isChecked()

    qtbot.mouseClick(panel.add_node_button, Qt.LeftButton)
    qtbot.mouseClick(panel.renameNodeButton, Qt.LeftButton)
    qtbot.mouseClick(panel.toggleButton, Qt.LeftButton)
    panel.show_page("docker")
    qtbot.mouseClick(panel.docker_download_button, Qt.LeftButton)
    panel.show_page("apps")
    apps_sidebar_page = panel.findChild(QWidget, "appsSidebarPage")
    assert panel.page_stack.sizeHint().height() == apps_sidebar_page.sizeHint().height()
    assert panel.findChild(QLabel, "appsWorkspaceSidebarLabel").text() == "Deployment workspace"
    panel.show_page("network")
    qtbot.mouseClick(panel.dapp_button, Qt.LeftButton)
    qtbot.mouseClick(panel.explorer_button, Qt.LeftButton)
    panel.show_page("nodes")
    qtbot.mouseClick(panel.refreshButton, Qt.LeftButton)
    panel.show_page("settings")
    qtbot.mouseClick(panel.themeToggleButton, Qt.LeftButton)
    panel.force_debug_checkbox.setChecked(False)

    assert calls == [
        "add",
        "rename",
        "toggle",
        "docker",
        "dapp",
        "explorer",
        "refresh",
        "theme",
        "debug",
    ]


def test_centered_combo_light_popup_uses_supported_qt_stylesheet(qtbot):
    combo = CenteredComboBox()
    qtbot.addWidget(combo)
    combo.set_theme(False)
    combo.addItem("alpha", "r1node")

    assert combo.minimumHeight() == 36
    assert combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert "background-color: #F8FAFC" in combo.styleSheet()
    assert "width: 30px" in combo.styleSheet()
    assert "color: transparent" in combo.lineEdit().styleSheet()
    assert "selection-color: transparent" in combo.lineEdit().styleSheet()
    assert combo.lineEdit().textMargins().right() == 28
    assert combo.lineEdit().isHidden()
    assert combo.currentText() == "alpha"

    combo.showPopup()
    qtbot.wait(50)
    try:
        stylesheet = combo.view().styleSheet()
        assert "QListView" in stylesheet
        assert "box-shadow" not in stylesheet
        assert "border-radius: 8px" in stylesheet
    finally:
        combo.hidePopup()

    combo.set_theme(True)
    assert "background-color: #151A23" in combo.styleSheet()
    assert "border: 1px solid #445164" in combo.styleSheet()
    assert "color: transparent" in combo.lineEdit().styleSheet()


def test_centered_combo_popup_uses_widget_screen_geometry(qtbot, monkeypatch):
    combo = CenteredComboBox()
    qtbot.addWidget(combo)
    expected_geometry = QRect(10, 20, 300, 240)

    class FakeScreen:
        def geometry(self):
            return expected_geometry

    class FailingDesktop:
        def screenGeometry(self, *_args):
            raise AssertionError("deprecated desktop geometry fallback should not be used")

    monkeypatch.setattr(combo, "screen", lambda: FakeScreen())
    monkeypatch.setattr(QApplication, "desktop", lambda: FailingDesktop())

    assert combo._popup_screen_geometry() == expected_geometry


def test_loading_dialog_progress_does_not_process_events_synchronously(qtbot, monkeypatch):
    dialog = LoadingDialog(title="Launching Node", message="Please wait")
    qtbot.addWidget(dialog)
    process_event_calls = []

    with monkeypatch.context() as process_events_patch:
        process_events_patch.setattr(
            QApplication,
            "processEvents",
            lambda *args, **kwargs: process_event_calls.append("processEvents"),
        )

        dialog.update_progress("Working")
        dialog.keep_alive()
        dialog.showEvent(QShowEvent())

    assert dialog.message_label.text() == "Working"
    assert process_event_calls == []


def test_loading_dialog_exposes_visual_snapshot_targets(qtbot):
    dialog = LoadingDialog(title="Launching Node", message="Please wait")
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "loadingDialog"
    assert dialog.accessibleName() == "Launching Node"
    assert dialog.title_label.objectName() == "loadingDialogTitleLabel"
    assert dialog.title_label.accessibleName() == "Loading dialog title"
    assert dialog.title_label.text() == "Launching Node"
    assert dialog.message_label.objectName() == "loadingDialogMessageLabel"
    assert dialog.message_label.accessibleName() == "Loading dialog message"
    assert dialog.loading_indicator.objectName() == "loadingDialogIndicator"
    assert dialog.loading_indicator.accessibleName() == "Loading indicator"
    assert dialog.minimumWidth() == 340
    assert dialog.minimumHeight() == 190
    assert dialog.maximumWidth() > dialog.minimumWidth()
    assert dialog.message_label.minimumWidth() == 280
    assert dialog.message_label.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding


def test_loading_dialog_accepts_long_progress_copy_without_fixed_size(qtbot):
    dialog = LoadingDialog(
        title="Launching Node",
        message="Preparing Docker command with a detailed status message",
    )
    qtbot.addWidget(dialog)

    dialog.update_progress(
        "Error: Docker reported a long startup failure message that should wrap instead of being clipped"
    )
    dialog.adjustSize()

    assert dialog.message_label.wordWrap()
    assert dialog.message_label.text().startswith("Error: Docker reported")
    assert dialog.size().width() >= dialog.minimumWidth()
    assert dialog.size().height() >= dialog.minimumHeight()


def test_loading_indicator_lives_in_widgets_with_legacy_alias(qtbot):
    indicator = LoadingIndicator(size=32)
    qtbot.addWidget(indicator)

    assert LegacyLoadingIndicator is LoadingIndicator
    assert indicator.size().width() == 32
    assert indicator.size().height() == 32

    indicator.start()
    assert indicator.timer.isActive()

    indicator.rotate()
    assert indicator.angle == 30

    indicator.stop()
    assert not indicator.timer.isActive()


def test_docker_pull_dialog_exposes_stable_visual_targets(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "dockerPullDialog"
    assert dialog.accessibleName() == "Pulling Docker Image"
    assert dialog.findChild(QLabel, "dockerPullTitleLabel") is dialog.title_label
    assert dialog.title_label.text() == "Pulling Docker Image"
    assert dialog.title_label.accessibleName() == "Docker pull title"
    assert dialog.findChild(QLabel, "dockerPullInfoLabel") is dialog.info_label
    assert dialog.info_label.accessibleName() == "Docker pull status"
    assert dialog.findChild(QProgressBar, "dockerPullOverallProgress") is dialog.overall_progress
    assert dialog.overall_progress.accessibleName() == "Docker pull overall progress"
    assert dialog.findChild(QWidget, "dockerPullLayerFrame") is dialog.layer_frame
    assert dialog.findChild(QWidget, "dockerPullLayerScrollArea") is dialog.scroll_area
    assert dialog.findChild(QWidget, "dockerPullLayerScrollContent") is dialog.scroll_content
    assert dialog.layer_frame.accessibleName() == "Docker pull layer progress"
    assert dialog.scroll_area.accessibleName() == "Docker pull layer list"
    assert dialog.findChild(QScrollArea, "dockerPullLayerScrollArea").horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert dialog.scroll_content.accessibleName() == "Docker pull layer list content"
    assert dialog.findChild(QLabel, "dockerPullLayerHeaderLabel") is dialog.layer_header_label
    assert dialog.layer_header_label.accessibleName() == "Layer progress heading"
    assert dialog.findChild(QLabel, "dockerPullLayerEmptyState").text() == "Waiting for Docker layer output..."
    assert dialog.findChild(QLabel, "dockerPullLayerEmptyState").accessibleName() == "Docker pull waiting state"
    assert DOCKER_PULL_DIALOG_STYLE_COLORS[True]["dialog_bg"] in dialog.styleSheet()


def test_docker_pull_dialog_theme_styles_are_switchable(qtbot):
    dialog = DockerPullDialog(is_dark=False)
    qtbot.addWidget(dialog)

    dialog.update_pull_progress("abcdef123456: Downloading 50%")

    light_colors = DOCKER_PULL_DIALOG_STYLE_COLORS[False]
    assert light_colors["dialog_bg"] in dialog.styleSheet()
    assert light_colors["title_text"] in dialog.title_label.styleSheet()
    assert light_colors["layer_accent"] in dialog.layer_widgets["abcdef123456"]["label"].styleSheet()

    dialog.apply_theme(True)

    dark_colors = DOCKER_PULL_DIALOG_STYLE_COLORS[True]
    assert dark_colors["dialog_bg"] in dialog.styleSheet()
    assert dark_colors["title_text"] in dialog.title_label.styleSheet()
    assert dark_colors["layer_accent"] in dialog.layer_widgets["abcdef123456"]["label"].styleSheet()


def test_docker_pull_dialog_updates_layer_progress_with_named_children(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)

    dialog.update_pull_progress("abcdef123456: Downloading 50%")

    assert not dialog.empty_layer_label.isVisible()
    assert dialog.overall_progress.value() == 50
    layer_label = dialog.findChild(QLabel, "dockerPullLayerLabel_abcdef123456")
    status_label = dialog.findChild(QLabel, "dockerPullLayerStatus_abcdef123456")
    layer_progress = dialog.findChild(QProgressBar, "dockerPullLayerProgress_abcdef123456")
    assert layer_label.text() == "abcdef12..."
    assert layer_label.accessibleName() == "Docker layer abcdef12"
    assert layer_label.toolTip() == "abcdef123456"
    assert layer_label.minimumWidth() == 76
    assert layer_label.maximumWidth() == 112
    assert status_label.text() == "Downloading 50%"
    assert status_label.accessibleName() == "Docker layer abcdef12 status"
    assert status_label.toolTip() == "Downloading 50%"
    assert status_label.maximumWidth() >= 16777215
    assert status_label.alignment() & Qt.AlignRight
    assert layer_progress.value() == 50
    assert layer_progress.accessibleName() == "Docker layer abcdef12 progress"
    assert layer_progress.minimumWidth() == 140
    row_layout = dialog.layer_widgets["abcdef123456"]["layout"]
    assert row_layout.stretch(1) == 1
    assert row_layout.stretch(2) == 1


def test_docker_pull_dialog_uses_stable_synthetic_layer_ids(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)
    line = "Downloading 2.0MB/4.0MB"
    updated_line = "Downloading 3.0MB/4.0MB"
    object_suffix = dialog._synthetic_layer_id(line)

    dialog.update_pull_progress(line)
    dialog.update_pull_progress(updated_line)

    assert len(object_suffix) == 12
    assert object_suffix == DockerPullDialog._synthetic_layer_id(line)
    assert object_suffix == DockerPullDialog._synthetic_layer_id(updated_line)
    assert len(dialog.layers) == 1
    assert dialog.findChild(QLabel, f"dockerPullLayerLabel_{object_suffix}").text() == "Layer"
    assert dialog.findChild(QLabel, f"dockerPullLayerStatus_{object_suffix}").text() == updated_line
    assert dialog.findChild(QLabel, f"dockerPullLayerStatus_{object_suffix}").toolTip() == updated_line
    assert dialog.findChild(QProgressBar, f"dockerPullLayerProgress_{object_suffix}").value() == 75


def test_docker_pull_dialog_parses_size_progress_units(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)
    line = "Extracting 512KB/1MB"
    object_suffix = dialog._synthetic_layer_id(line)

    dialog.update_pull_progress(line)

    assert dialog.findChild(QProgressBar, f"dockerPullLayerProgress_{object_suffix}").value() == 50


def test_docker_pull_dialog_keeps_long_layer_status_available(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)
    long_status = "Downloading 12.5MB/240.0MB retrying after temporary registry throttling"

    dialog.update_pull_progress(f"abcdef123456: {long_status}")

    status_label = dialog.findChild(QLabel, "dockerPullLayerStatus_abcdef123456")
    assert status_label.text() == long_status
    assert status_label.toolTip() == long_status
    assert status_label.wordWrap()
    assert status_label.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert status_label.maximumWidth() >= 16777215


def test_node_info_widget_baseline_clear_and_uptime_format(qtbot):
    widget = NodeInfoWidget()
    qtbot.addWidget(widget)

    assert widget.objectName() == "nodeInfoWidget"
    assert widget.accessibleName() == "Node information"
    assert widget.info_group.objectName() == "nodeInfoGroup"
    assert widget.info_group.accessibleName() == "Node information"
    assert widget.info_group.property("role") == "nodeInfoPanel"
    assert widget.findChild(QLabel, "nodeInfoStatusLabel").accessibleName() == "Status label"
    assert widget.findChild(QLabel, "nodeInfoStatusLabel").property("role") == "nodeInfoFieldLabel"
    assert widget.findChild(QLabel, "nodeInfoNameLabel").accessibleName() == "Node name label"
    assert widget.findChild(QLabel, "nodeInfoUptimeLabel").accessibleName() == "Uptime label"
    assert widget.findChild(QLabel, "nodeInfoAddressLabel").accessibleName() == "Node address label"
    assert widget.findChild(QLabel, "nodeInfoEthAddressLabel").accessibleName() == "ETH address label"
    assert widget.lbl_node_address.objectName() == "nodeInfoAddressValue"
    assert widget.lbl_node_address.accessibleName() == "Node address"
    assert widget.lbl_node_address.property("role") == "nodeInfoAddress"
    assert not widget.lbl_node_address.wordWrap()
    assert widget.lbl_node_address.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
    assert widget.lbl_node_address.toolTip() == "N/A"
    assert widget.lbl_eth_address.objectName() == "nodeInfoEthAddressValue"
    assert widget.lbl_eth_address.accessibleName() == "ETH address"
    assert widget.lbl_eth_address.property("role") == "nodeInfoAddress"
    assert not widget.lbl_eth_address.wordWrap()
    assert widget.lbl_eth_address.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
    assert widget.lbl_node_status.objectName() == "nodeInfoStatusValue"
    assert widget.lbl_node_status.accessibleName() == "Node status"
    assert widget.lbl_node_status.property("role") == "nodeInfoValue"
    assert widget.lbl_node_status.property("status") == "unknown"
    assert widget.lbl_uptime.objectName() == "nodeInfoUptimeValue"
    assert widget.lbl_uptime.accessibleName() == "Node uptime"
    assert widget.lbl_uptime.property("role") == "nodeInfoValue"
    assert widget.lbl_node_name.objectName() == "nodeInfoNameValue"
    assert widget.lbl_node_name.accessibleName() == "Node name"
    assert widget.lbl_node_name.property("role") == "nodeInfoValue"
    assert "QGroupBox#nodeInfoGroup" in widget.styleSheet()
    assert widget._format_uptime(65) == "1m 5s"
    assert widget._format_uptime(3661) == "1h 1m 1s"
    assert widget._format_uptime(90061) == "1d 1h 1m"

    widget.clear_info()

    assert widget.lbl_node_address.text() == "N/A"
    assert widget.lbl_eth_address.text() == "N/A"
    assert widget.lbl_node_status.text() == "Unknown"
    assert widget.lbl_node_status.property("status") == "unknown"


def test_node_info_widget_action_buttons_emit_signals(qtbot):
    widget = NodeInfoWidget()
    qtbot.addWidget(widget)

    assert widget.btn_copy_address.objectName() == "nodeInfoCopyAddressButton"
    assert widget.btn_copy_address.accessibleName() == "Copy node address"
    assert widget.btn_copy_address.toolTip() == "Copy node address"
    assert widget.btn_copy_address.property("actionRole") == "utility"
    assert widget.btn_copy_eth.objectName() == "nodeInfoCopyEthButton"
    assert widget.btn_copy_eth.accessibleName() == "Copy ETH address"
    assert widget.btn_copy_eth.toolTip() == "Copy ETH address"
    assert widget.btn_copy_eth.property("actionRole") == "utility"
    assert widget.btn_refresh.objectName() == "nodeInfoRefreshButton"
    assert widget.btn_refresh.accessibleName() == "Refresh node information"
    assert widget.btn_refresh.toolTip() == "Refresh node information"
    assert widget.btn_refresh.property("actionRole") == "primary"

    with qtbot.waitSignal(widget.copy_address_requested) as blocker:
        qtbot.mouseClick(widget.btn_copy_address, Qt.LeftButton)
    assert blocker.args == ["node"]

    with qtbot.waitSignal(widget.copy_address_requested) as blocker:
        qtbot.mouseClick(widget.btn_copy_eth, Qt.LeftButton)
    assert blocker.args == ["eth"]

    with qtbot.waitSignal(widget.refresh_requested):
        qtbot.mouseClick(widget.btn_refresh, Qt.LeftButton)


def test_node_info_widget_updates_from_current_model_contract(qtbot):
    widget = NodeInfoWidget()
    qtbot.addWidget(widget)

    widget.update_node_info(
        NodeInfo(
            address="0xnode",
            alias="edge-one",
            eth_address="0xeth",
            version_long="1.2.3-long",
            version_short="1.2.3",
            whitelist=[],
        )
    )

    assert widget.lbl_node_address.text() == "0xnode"
    assert widget.lbl_node_address.toolTip() == "0xnode"
    assert widget.lbl_eth_address.text() == "0xeth"
    assert widget.lbl_eth_address.toolTip() == "0xeth"
    assert widget.lbl_node_name.text() == "edge-one"
    assert widget.lbl_node_status.text() == "Available"
    assert widget.lbl_node_status.property("status") == "available"
    assert widget.lbl_uptime.text() == "N/A"


def test_node_info_widget_theme_styles_are_switchable(qtbot):
    widget = NodeInfoWidget()
    qtbot.addWidget(widget)

    widget.apply_theme(True)
    assert "#122033" in widget.styleSheet()
    assert "#E8EEF8" in widget.styleSheet()

    widget.apply_theme(False)
    assert "#FFFFFF" in widget.styleSheet()
    assert "#1F2937" in widget.styleSheet()


def test_metrics_widget_refresh_button_emits_signal(qtbot):
    widget = MetricsWidget()
    qtbot.addWidget(widget)

    assert widget.btn_refresh.objectName() == "metricsRefreshButton"
    assert widget.objectName() == "metricsWidget"
    assert widget.accessibleName() == "Node metrics"
    assert widget.metrics_group.objectName() == "metricsGroup"
    assert widget.metrics_group.accessibleName() == "Node metrics"
    assert widget.metrics_group.property("role") == "metricsPanel"
    assert widget.btn_refresh.accessibleName() == "Refresh metrics"
    assert widget.btn_refresh.toolTip() == "Refresh metrics"
    assert widget.btn_refresh.property("actionRole") == "primary"
    assert widget.plot_cpu.objectName() == "metricsCpuPlot"
    assert widget.plot_cpu.accessibleName() == "CPU usage plot"
    assert widget.plot_memory.objectName() == "metricsMemoryPlot"
    assert widget.plot_memory.accessibleName() == "Memory usage plot"
    assert widget.plot_gpu.objectName() == "metricsGpuPlot"
    assert widget.plot_gpu.accessibleName() == "GPU usage plot"
    assert widget.plot_gpu_memory.objectName() == "metricsGpuMemoryPlot"
    assert widget.plot_gpu_memory.accessibleName() == "GPU memory usage plot"
    assert "QGroupBox#metricsGroup" in widget.styleSheet()

    for plot in (widget.plot_cpu, widget.plot_memory, widget.plot_gpu, widget.plot_gpu_memory):
        assert plot.backgroundBrush().style() == Qt.NoBrush
        assert plot.getAxis("left").pen().color().name() == METRIC_AXIS_COLOR
        assert plot.getAxis("bottom").pen().color().name() == METRIC_AXIS_COLOR
        assert not plot.getPlotItem().menuEnabled()
        assert plot.getPlotItem().ctrl.xGridCheck.isChecked()
        assert plot.getPlotItem().ctrl.yGridCheck.isChecked()
        assert plot.getPlotItem().ctrl.gridAlphaSlider.value() == int(METRIC_GRID_ALPHA * 255)

    with qtbot.waitSignal(widget.refresh_requested):
        qtbot.mouseClick(widget.btn_refresh, Qt.LeftButton)


def test_metrics_widget_theme_styles_are_switchable(qtbot):
    widget = MetricsWidget()
    qtbot.addWidget(widget)

    widget.apply_theme(True)
    assert "#122033" in widget.styleSheet()
    assert "#E8EEF8" in widget.styleSheet()

    widget.apply_theme(False)
    assert "#FFFFFF" in widget.styleSheet()
    assert "#1F2937" in widget.styleSheet()


def test_metric_plot_grid_builder_preserves_dashboard_contract(qtbot):
    graph_view, plots, axis_items = create_metrics_graph_grid()
    qtbot.addWidget(graph_view)
    layout = graph_view.layout()

    assert graph_view.objectName() == "metricsGraphGrid"
    assert graph_view.accessibleName() == "Metrics graph grid"
    assert layout.count() == 4
    assert layout.spacing() == 10
    assert set(plots) == {"cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"}
    assert set(axis_items) == set(plots)

    expected = {
        "cpuPlotContainer": ("cpu_plot", "cpuPlotTitle", "cpuPlotEmptyState", "cpuMetricPlot", 0, 0),
        "memoryPlotContainer": ("memory_plot", "memoryPlotTitle", "memoryPlotEmptyState", "memoryMetricPlot", 0, 1),
        "gpuPlotContainer": ("gpu_plot", "gpuPlotTitle", "gpuPlotEmptyState", "gpuMetricPlot", 1, 0),
        "gpuMemoryPlotContainer": (
            "gpu_memory_plot",
            "gpuMemoryPlotTitle",
            "gpuMemoryPlotEmptyState",
            "gpuMemoryMetricPlot",
            1,
            1,
        ),
    }
    for container_name, (plot_attr, title_name, empty_name, plot_name, row, column) in expected.items():
        container = graph_view.findChild(QWidget, container_name)
        plot = plots[plot_attr]

        assert container is not None
        title_label = container.findChild(QWidget, title_name)
        empty_label = container.findChild(QWidget, empty_name)

        assert container.accessibleName() == title_label.text()
        assert container.property("class") == "plot-container"
        assert isinstance(plot, MetricPlotWidget)
        assert plot.objectName() == plot_name
        assert plot.accessibleName() == f"{title_label.text()} plot"
        assert plot.backgroundBrush().style() == Qt.NoBrush
        assert plot.getAxis("left").pen().color().name() == METRIC_AXIS_COLOR
        assert plot.getAxis("bottom").pen().color().name() == METRIC_AXIS_COLOR
        assert not plot.getPlotItem().menuEnabled()
        assert plot.getPlotItem().ctrl.xGridCheck.isChecked()
        assert plot.getPlotItem().ctrl.yGridCheck.isChecked()
        assert plot.getPlotItem().ctrl.gridAlphaSlider.value() == int(METRIC_GRID_ALPHA * 255)
        assert plot.parent() is container
        assert plot._r1_plot_container is container
        assert plot._r1_title_label is title_label
        assert plot._r1_bottom_axis is axis_items[plot_attr]
        assert plot.getAxis("bottom") is axis_items[plot_attr]
        assert title_label is not None
        assert title_label.accessibleName() == f"{title_label.text()} title"
        assert title_label.property("role") == "metricPlotTitle"
        assert empty_label is plot._r1_empty_label
        assert empty_label.accessibleName() == f"{title_label.text()} empty state"
        assert empty_label.property("role") == "metricPlotEmptyState"
        assert empty_label.alignment() == Qt.AlignCenter
        assert empty_label.minimumHeight() == METRIC_EMPTY_STATE_MIN_HEIGHT
        assert empty_label.text() == METRIC_EMPTY_STATE_TEXT
        assert layout.itemAtPosition(row, column).widget() is container


def test_metrics_widget_updates_from_current_history_model_contract(qtbot):
    widget = MetricsWidget()
    qtbot.addWidget(widget)

    widget.update_metrics(
        NodeHistory(
            address="0xnode",
            alias="edge-one",
            cpu_load=[12.0, 24.0],
            cpu_temp=[40.0, 41.0],
            current_epoch=8,
            current_epoch_avail=0.5,
            eth_address="0xeth",
            gpu_load=[30.0, 45.0],
            gpu_occupied_memory=[1024.0, 2048.0],
            gpu_temp=[60.0, 61.0],
            gpu_total_memory=[4096.0, 4096.0],
            last_epochs=[6, 7, 8],
            last_save_time="2026-05-03T01:00:10",
            occupied_memory=[512.0, 768.0],
            timestamps=["2026-05-03T01:00:00", "2026-05-03T01:00:10"],
            total_memory=[1024.0, 1024.0],
            uptime="1h",
            version="1.2.3",
        )
    )

    assert len(widget.plot_cpu.listDataItems()) == 1
    assert len(widget.plot_memory.listDataItems()) == 1
    assert len(widget.plot_gpu.listDataItems()) == 1
    assert len(widget.plot_gpu_memory.listDataItems()) == 1


def test_config_editor_button_opens_dialog_with_named_actions(qtbot, monkeypatch):
    widget = ConfigEditorWidget()
    qtbot.addWidget(widget)
    opened_dialogs = []

    def capture_exec(dialog):
        opened_dialogs.append(dialog)
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", capture_exec)

    assert widget.btn_edit_config.objectName() == "configEditorEditButton"
    assert widget.objectName() == "configEditorWidget"
    assert widget.accessibleName() == "Configuration editor"
    assert widget.config_group.objectName() == "configEditorGroup"
    assert widget.config_group.accessibleName() == "Configuration files"
    assert widget.config_group.property("role") == "configEditorPanel"
    assert widget.btn_edit_config.accessibleName() == "Edit configuration"
    assert widget.btn_edit_config.property("actionRole") == "primary"
    assert widget.btn_edit_config.toolTip() == "Edit configuration"
    assert widget.btn_edit_config.minimumHeight() == 36
    assert "QGroupBox#configEditorGroup" in widget.config_group.styleSheet()

    qtbot.mouseClick(widget.btn_edit_config, Qt.LeftButton)

    assert len(opened_dialogs) == 1
    dialog = opened_dialogs[0]
    button_box = dialog.findChild(QDialogButtonBox, "configEditorDialogButtons")
    tabs = dialog.findChild(QTabWidget, "configEditorTabs")
    startup_label = dialog.findChild(QLabel, "startupConfigLabel")
    app_label = dialog.findChild(QLabel, "appConfigLabel")
    startup_text = dialog.findChild(QTextEdit, "startupConfigText")
    app_text = dialog.findChild(QTextEdit, "appConfigText")

    assert dialog.objectName() == "configEditorDialog"
    assert dialog.accessibleName() == "Edit Configuration Files"
    assert dialog.minimumWidth() == 720
    assert dialog.minimumHeight() == 520
    assert "QDialog#configEditorDialog" in dialog.styleSheet()
    assert tabs.accessibleName() == "Configuration tabs"
    assert tabs.documentMode()
    assert dialog.findChild(QWidget, "startupConfigTab").accessibleName() == "Startup configuration tab"
    assert dialog.findChild(QWidget, "appConfigTab").accessibleName() == "App configuration tab"
    assert startup_label.accessibleName() == "Startup configuration label"
    assert startup_label.property("role") == "configEditorLabel"
    assert app_label.accessibleName() == "App configuration label"
    assert app_label.property("role") == "configEditorLabel"
    assert startup_text.accessibleName() == "Startup configuration text"
    assert startup_text.property("role") == "configEditorText"
    assert not startup_text.acceptRichText()
    assert startup_text.lineWrapMode() == QTextEdit.NoWrap
    assert startup_text.placeholderText() == "Startup configuration is empty"
    assert app_text.accessibleName() == "App configuration text"
    assert app_text.property("role") == "configEditorText"
    assert not app_text.acceptRichText()
    assert app_text.lineWrapMode() == QTextEdit.NoWrap
    assert app_text.placeholderText() == "App configuration is empty"
    assert button_box is not None
    assert button_box.accessibleName() == "Configuration editor actions"
    assert button_box.button(QDialogButtonBox.Ok).objectName() == "configEditorSaveButton"
    assert button_box.button(QDialogButtonBox.Ok).text() == "Save"
    assert button_box.button(QDialogButtonBox.Ok).accessibleName() == "Save configuration"
    assert button_box.button(QDialogButtonBox.Ok).property("actionRole") == "primary"
    assert button_box.button(QDialogButtonBox.Ok).toolTip() == "Save configuration"
    assert button_box.button(QDialogButtonBox.Cancel).objectName() == "configEditorCancelButton"
    assert button_box.button(QDialogButtonBox.Cancel).accessibleName() == "Cancel configuration editing"
    assert button_box.button(QDialogButtonBox.Cancel).property("actionRole") == "secondary"
    assert button_box.button(QDialogButtonBox.Cancel).toolTip() == "Cancel configuration editing"


def test_config_editor_save_emits_current_plain_text(qtbot, monkeypatch):
    widget = ConfigEditorWidget()
    qtbot.addWidget(widget)

    def capture_exec(dialog):
        dialog.findChild(QTextEdit, "startupConfigText").setPlainText("startup=true")
        dialog.findChild(QTextEdit, "appConfigText").setPlainText("log_level=debug")
        dialog.findChild(QDialogButtonBox, "configEditorDialogButtons").button(QDialogButtonBox.Ok).click()
        return dialog.result()

    monkeypatch.setattr(QDialog, "exec_", capture_exec)

    with qtbot.waitSignal(widget.config_saved) as blocker:
        result = widget.open_config_editor("startup=false", "log_level=info")

    assert result == QDialog.Accepted
    assert blocker.args == [{"startup_config": "startup=true", "app_config": "log_level=debug"}]


def test_config_editor_cancel_does_not_emit(qtbot, monkeypatch):
    widget = ConfigEditorWidget()
    qtbot.addWidget(widget)
    emitted = []
    widget.config_saved.connect(emitted.append)

    def capture_exec(dialog):
        dialog.findChild(QDialogButtonBox, "configEditorDialogButtons").button(QDialogButtonBox.Cancel).click()
        return dialog.result()

    monkeypatch.setattr(QDialog, "exec_", capture_exec)

    result = widget.open_config_editor("startup=false", "log_level=info")

    assert result == QDialog.Rejected
    assert emitted == []


def test_config_editor_theme_styles_are_switchable(qtbot, monkeypatch):
    widget = ConfigEditorWidget()
    qtbot.addWidget(widget)
    opened_dialogs = []

    def capture_exec(dialog):
        opened_dialogs.append(dialog)
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", capture_exec)

    widget.apply_theme(True)
    assert "#E8EEF8" in widget.styleSheet()
    assert "#122033" in widget.config_group.styleSheet()
    widget.open_config_editor()
    assert "#0B1626" in opened_dialogs[-1].styleSheet()
    assert "#122033" in opened_dialogs[-1].findChild(QTabWidget, "configEditorTabs").styleSheet()
    assert "#0F1B2B" in opened_dialogs[-1].findChild(QTextEdit, "startupConfigText").styleSheet()
    assert "#1B47F7" in opened_dialogs[-1].findChild(QDialogButtonBox, "configEditorDialogButtons").button(
        QDialogButtonBox.Ok
    ).styleSheet()
    assert "#E8EEF8" in opened_dialogs[-1].styleSheet()

    widget.apply_theme(False)
    assert "#1F2937" in widget.styleSheet()
    assert "#FFFFFF" in widget.config_group.styleSheet()
    widget.open_config_editor()
    assert "#F8FAFC" in opened_dialogs[-1].styleSheet()
    assert "#FFFFFF" in opened_dialogs[-1].findChild(QTabWidget, "configEditorTabs").styleSheet()
    assert "#FFFFFF" in opened_dialogs[-1].findChild(QTextEdit, "startupConfigText").styleSheet()
    assert "#1F2937" in opened_dialogs[-1].styleSheet()
