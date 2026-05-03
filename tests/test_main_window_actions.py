import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QPushButton, QWidget

import app_forms.frm_main as frm_main
from models.NodeInfo import NodeInfo
from utils.config_manager import ContainerConfig
from widgets.ToastWidget import NotificationType


class FakeToast:
    def __init__(self):
        self.notifications = []

    def show_notification(self, notification_type, message):
        self.notifications.append((notification_type, message))


class FakeConfigManager:
    def __init__(self):
        self.containers = [
            ContainerConfig(
                name="r1node",
                volume="r1vol",
                node_address="0xnodeaddress",
                eth_address="0xethaddress",
                node_alias="alpha",
            )
        ]
        self.force_debug_values = []
        self.node_alias_updates = []

    def get_force_debug(self):
        return False

    def set_force_debug(self, value):
        self.force_debug_values.append(value)
        return True

    def get_all_containers(self):
        return self.containers

    def add_container(self, container):
        self.containers.append(container)
        return True

    def get_container(self, container_name):
        for container in self.containers:
            if container.name == container_name:
                return container
        return None

    def update_node_address(self, container_name, node_address):
        container = self.get_container(container_name)
        if container:
            container.node_address = node_address
        return True

    def update_eth_address(self, container_name, eth_address):
        container = self.get_container(container_name)
        if container:
            container.eth_address = eth_address
        return True

    def update_node_alias(self, container_name, node_alias):
        self.node_alias_updates.append((container_name, node_alias))
        container = self.get_container(container_name)
        if container:
            container.node_alias = node_alias
        return True

    def update_last_used(self, container_name, timestamp):
        return True

    def update_volume(self, container_name, volume_name):
        return True

    def volume_exists_in_docker(self, volume_name):
        return False


class FakeDockerHandler:
    def __init__(self, container_name, running=False):
        self.container_name = container_name
        self.running = running
        self.container_names = []
        self.debug_values = []
        self.node_name_updates = []
        self.node_info_requests = 0

    def set_container_name(self, container_name):
        self.container_name = container_name
        self.container_names.append(container_name)

    def is_container_running(self):
        return self.running

    def set_debug_mode(self, value):
        self.debug_values.append(value)

    def execute_command(self, command):
        return "", "", 0

    def get_node_info(self, on_success, on_error):
        self.node_info_requests += 1
        on_success(NodeInfo(address="0xfreshnode", eth_address="0xfresheth", alias="fresh"))

    def update_node_name(self, new_name, on_success, on_error):
        self.node_name_updates.append(new_name)
        on_success({})


def _build_launcher(monkeypatch, qtbot, running=False):
    fake_config = FakeConfigManager()
    fake_handler = FakeDockerHandler(frm_main.DOCKER_CONTAINER_NAME, running=running)

    monkeypatch.setattr(frm_main, "ConfigManager", lambda: fake_config)
    monkeypatch.setattr(frm_main, "DockerCommandHandler", lambda container_name: fake_handler)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "check_docker_with_ui", lambda self: True)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "docker_initialize", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "check_for_updates", lambda self, verbose=False: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "container_exists_in_docker", lambda self, name: False)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "update_resources_display", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "plot_graphs", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "plot_data", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "maybe_refresh_uptime", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "refresh_node_info", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "post_launch_setup", lambda self: None)
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "show_initial_window", lambda self: self.show())

    launcher = frm_main.EdgeNodeLauncher()
    qtbot.addWidget(launcher)
    launcher.show()
    launcher.timer.stop()
    launcher.toast = FakeToast()

    return launcher, fake_config, fake_handler


def test_main_window_navigation_buttons_use_mocked_side_effects(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    opened_urls = []
    monkeypatch.setattr(webbrowser, "open", opened_urls.append)

    assert launcher.dapp_button.objectName() == "openDappButton"
    assert launcher.explorer_button.objectName() == "openExplorerButton"
    assert launcher.docker_download_button.objectName() == "downloadDockerButton"

    qtbot.mouseClick(launcher.dapp_button, Qt.LeftButton)
    qtbot.mouseClick(launcher.explorer_button, Qt.LeftButton)
    launcher.docker_download_button.click()

    assert opened_urls == [
        frm_main.DAPP_URLS[frm_main.DEFAULT_ENVIRONMENT],
        "https://docs.docker.com/get-docker/",
    ]
    assert launcher.toast.notifications == [
        (NotificationType.INFO, "Ratio1 Explorer is not yet implemented")
    ]


def test_main_window_copy_buttons_copy_current_addresses(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    launcher.node_addr = "0xnodeaddress"
    launcher.node_eth_address = "0xethaddress"
    launcher.copyAddrButton.show()
    launcher.copyEthButton.show()

    assert launcher.copyAddrButton.objectName() == "copyAddrButton"
    assert launcher.copyEthButton.objectName() == "copyEthButton"

    qtbot.mouseClick(launcher.copyAddrButton, Qt.LeftButton)
    assert QApplication.clipboard().text() == "0xnodeaddress"

    qtbot.mouseClick(launcher.copyEthButton, Qt.LeftButton)
    assert QApplication.clipboard().text() == "0xethaddress"

    assert launcher.toast.notifications[-2:] == [
        (NotificationType.SUCCESS, frm_main.NOTIFICATION_ADDRESS_COPIED.format(address="0xnodeaddress")),
        (NotificationType.SUCCESS, frm_main.NOTIFICATION_ADDRESS_COPIED.format(address="0xethaddress")),
    ]


def test_main_window_refresh_button_uses_limited_refresh_when_container_stopped(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    calls = []
    launcher.update_toggle_button_text = lambda: calls.append("toggle")
    launcher.maybe_refresh_uptime = lambda: calls.append("uptime")
    launcher.update_resources_display = lambda: calls.append("resources")

    assert launcher.refreshButton.objectName() == "refreshNodeInfoButton"

    qtbot.mouseClick(launcher.refreshButton, Qt.LeftButton)

    assert fake_handler.container_names[-1] == "r1node"
    assert calls == ["toggle", "uptime", "resources"]
    assert launcher.toast.notifications[-2:] == [
        (NotificationType.INFO, "Refreshing node information..."),
        (NotificationType.WARNING, "Container is not running. Only cached data available."),
    ]


def test_main_window_start_button_dispatches_to_start_when_stopped(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    calls = []
    launcher._start_container = lambda: calls.append("start")
    launcher._stop_container = lambda: calls.append("stop")

    assert launcher.toggleButton.objectName() == "startNodeButton"

    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)

    assert calls == ["start"]


def test_main_window_start_button_dispatches_to_stop_when_running(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    calls = []
    launcher._start_container = lambda: calls.append("start")
    launcher._stop_container = lambda: calls.append("stop")

    assert launcher.toggleButton.objectName() == "startNodeButton"

    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)

    assert calls == ["stop"]


def test_main_window_theme_and_force_debug_buttons(qtbot, monkeypatch):
    launcher, fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.plot_graphs = lambda: None
    launcher.update_resources_display = lambda: None
    launcher.update_toggle_button_text = lambda: None

    assert launcher.themeToggleButton.objectName() == "themeToggleButton"
    assert launcher.force_debug_checkbox.objectName() == "forceDebugCheckbox"

    initial_theme = launcher._current_stylesheet
    qtbot.mouseClick(launcher.themeToggleButton, Qt.LeftButton)

    assert launcher._current_stylesheet != initial_theme
    assert launcher.themeToggleButton.text() == frm_main.DARK_DASHBOARD_BUTTON_TEXT

    qtbot.mouseClick(launcher.force_debug_checkbox, Qt.LeftButton)

    assert fake_config.force_debug_values == [True]
    assert fake_handler.debug_values == [True]


def test_main_window_rename_guard_reports_stopped_container(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    assert launcher.renameNodeButton.objectName() == "renameNodeButton"

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert launcher.toast.notifications[-1] == (
        NotificationType.ERROR,
        "Container not running. Could not change node name.",
    )


def test_main_window_add_node_dialog_create_action_is_clickable(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    created_nodes = []

    monkeypatch.setattr(
        launcher,
        "check_ram_for_new_node",
        lambda existing_node_count: {
            "can_add_node": True,
            "total_ram_gb": 32.0,
            "max_nodes_supported": 4,
            "current_node_count": existing_node_count,
            "min_required_gb": frm_main.MIN_NODE_RAM_GB,
        },
    )

    def record_create(container_name, volume_name, display_name, dialog):
        created_nodes.append((container_name, volume_name, display_name))
        dialog.accept()

    monkeypatch.setattr(launcher, "_create_node_with_name", record_create)

    def click_create(dialog):
        create_button = dialog.findChild(QPushButton, "createNodeConfirmButton")
        cancel_button = dialog.findChild(QPushButton, "createNodeCancelButton")
        assert create_button is not None
        assert cancel_button is not None
        create_button.click()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", click_create)

    assert launcher.add_node_button.objectName() == "addNodeButton"

    qtbot.mouseClick(launcher.add_node_button, Qt.LeftButton)

    assert len(created_nodes) == 1
    container_name, volume_name, display_name = created_nodes[0]
    assert container_name.startswith("r1node")
    assert volume_name.startswith("r1vol")
    assert display_name is None


def test_main_window_graph_plots_stay_inside_styled_containers(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    assert launcher.graphView.objectName() == "metricsGraphGrid"
    assert launcher.graphView.layout().count() == 4

    expected = {
        "cpuPlotContainer": launcher.cpu_plot,
        "memoryPlotContainer": launcher.memory_plot,
        "gpuPlotContainer": launcher.gpu_plot,
        "gpuMemoryPlotContainer": launcher.gpu_memory_plot,
    }

    for container_name, plot in expected.items():
        container = launcher.findChild(QWidget, container_name)

        assert container is not None
        assert plot.parent() is container
        assert container.layout().count() == 1
