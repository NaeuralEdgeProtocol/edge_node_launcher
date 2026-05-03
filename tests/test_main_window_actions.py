import webbrowser
from types import SimpleNamespace

from PyQt5 import sip
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QGroupBox, QLabel, QLineEdit, QPushButton, QScrollArea, QSplitter, QTextEdit, QVBoxLayout, QWidget

import app_forms.frm_main as frm_main
from models.NodeInfo import NodeInfo
from utils.config_manager import ContainerConfig
from widgets.ToastWidget import NotificationType


REAL_PLOT_DATA = frm_main.EdgeNodeLauncher.plot_data
REAL_REFRESH_NODE_INFO = frm_main.EdgeNodeLauncher.refresh_node_info


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
        self.dashboard_splitter_sizes = None
        self.main_window_geometry = None

    def get_force_debug(self):
        return False

    def set_force_debug(self, value):
        self.force_debug_values.append(value)
        return True

    def get_dashboard_splitter_sizes(self):
        return self.dashboard_splitter_sizes

    def set_dashboard_splitter_sizes(self, sizes):
        self.dashboard_splitter_sizes = list(sizes)
        return True

    def get_main_window_geometry(self):
        return self.main_window_geometry

    def set_main_window_geometry(self, geometry):
        self.main_window_geometry = dict(geometry)
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
        self.stopped_containers = []
        self.launched_containers = []
        self.pull_requests = 0
        self.history_container_requests = []
        self.history = SimpleNamespace(
            uptime="1s",
            current_epoch=1,
            current_epoch_avail=0.5,
            version="test-version",
        )

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
        on_success(
            NodeInfo(
                address="0xfreshnode",
                eth_address="0xfresheth",
                alias="fresh",
                version_long="",
                version_short="",
                whitelist=[],
            )
        )

    def update_node_name(self, new_name, on_success, on_error):
        self.node_name_updates.append(new_name)
        on_success({})

    def stop_container_threaded(self, container_name, callback, error_callback):
        self.stopped_containers.append(container_name)
        callback(("", "", 0))

    def launch_container_threaded(self, volume_name=None, callback=None, error_callback=None):
        self.launched_containers.append((self.container_name, volume_name))
        if callback:
            callback(("", "", 0))

    def pull_image(self, callback, error_callback, output_callback=None):
        self.pull_requests += 1

    def get_node_history(self, callback, error_callback):
        self.history_container_requests.append(self.container_name)
        callback(self.history)


def _build_launcher(monkeypatch, qtbot, running=False, config_setup=None):
    fake_config = FakeConfigManager()
    fake_handler = FakeDockerHandler(frm_main.DOCKER_CONTAINER_NAME, running=running)
    if config_setup is not None:
        config_setup(fake_config)

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
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda *args, **kwargs: None)

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


def test_main_window_primary_sidebar_actions_have_tooltips(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    expected_tooltips = {
        launcher.add_node_button: frm_main.ADD_NODE_TOOLTIP,
        launcher.toggleButton: frm_main.TOGGLE_NODE_TOOLTIP,
        launcher.dapp_button: frm_main.DAPP_TOOLTIP,
        launcher.explorer_button: frm_main.EXPLORER_TOOLTIP,
        launcher.refreshButton: frm_main.REFRESH_NODE_INFO_TOOLTIP,
        launcher.renameNodeButton: frm_main.RENAME_NODE_TOOLTIP,
        launcher.themeToggleButton: frm_main.THEME_TOGGLE_TOOLTIP,
        launcher.force_debug_checkbox: frm_main.FORCE_DEBUG_TOOLTIP,
    }

    for widget, tooltip in expected_tooltips.items():
        assert widget.toolTip() == tooltip


def test_main_window_rename_guard_reports_stopped_container(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    assert launcher.renameNodeButton.objectName() == "renameNodeButton"

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert launcher.toast.notifications[-1] == (
        NotificationType.ERROR,
        "Container not running. Could not change node name.",
    )


def test_main_window_rename_save_restarts_without_legacy_stop_modal(qtbot, monkeypatch):
    launcher, fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launch_calls = []

    def fail_legacy_stop(*args, **kwargs):
        raise AssertionError("rename flow should not use blocking legacy stop_container")

    launcher.stop_container = fail_legacy_stop
    launcher.launch_container = lambda volume_name=None: launch_calls.append(volume_name)

    def save_rename(dialog):
        name_input = dialog.findChild(QLineEdit, "renameNodeNameInput")
        save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
        assert name_input is not None
        assert save_button is not None
        name_input.setText("renamed")
        save_button.click()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", save_rename)

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert fake_handler.node_name_updates == ["renamed"]
    assert fake_handler.stopped_containers == ["r1node"]
    assert launch_calls == ["r1vol"]
    assert fake_config.get_container("r1node").node_alias == "renamed"


def test_rename_dialog_copy_and_input_constraints(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    observed = {}

    def inspect_dialog(dialog):
        observed["title"] = dialog.windowTitle()
        observed["labels"] = [label.text() for label in dialog.findChildren(QLabel)]
        name_input = dialog.findChild(QLineEdit, "renameNodeNameInput")
        assert name_input is not None
        observed["input_text"] = name_input.text()
        observed["placeholder"] = name_input.placeholderText()
        observed["max_length"] = name_input.maxLength()
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", inspect_dialog)

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert observed["title"] == "Rename Node"
    assert observed["input_text"] == "alpha"
    assert observed["placeholder"] == "Node display name"
    assert observed["max_length"] == 15
    label_text = "\n".join(observed["labels"])
    assert "Name this node for display in the launcher." in label_text
    assert "- Maximum 15 characters" in label_text
    assert "- Letters, numbers, hyphens, and underscores only" in label_text
    assert "â" not in label_text


def test_docker_pull_completion_uses_captured_launch_target(qtbot, monkeypatch):
    launcher, fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    fake_config.add_container(
        ContainerConfig(
            name="r1node2",
            volume="r1vol2",
            node_alias="beta",
        )
    )
    launcher.refresh_container_list()
    assert launcher._select_container_by_name("r1node2")

    launcher._start_docker_pull("r1node", "r1vol")
    launcher._begin_lifecycle_operation("launch", "r1node")
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())

    launcher._on_docker_pull_complete(True, "pulled")

    assert fake_handler.launched_containers == [("r1node", "r1vol")]
    assert launcher._selected_container_name() == "r1node"
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None


def test_docker_pull_completion_without_launch_target_clears_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._on_docker_pull_complete(True, "pulled")

    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress") is False


def test_plot_data_targets_selected_container_id_not_display_alias(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.plot_data = REAL_PLOT_DATA.__get__(launcher, frm_main.EdgeNodeLauncher)
    launcher.plot_graphs = lambda: None
    launcher.maybe_refresh_uptime = lambda assume_running=None: None

    assert launcher.container_combo.currentText() == "alpha"
    assert launcher._selected_container_name() == "r1node"

    launcher.plot_data(assume_running=True)

    assert fake_handler.history_container_requests == ["r1node"]
    assert fake_handler.container_names[-1] == "r1node"


def test_refresh_node_info_targets_selected_container_id_not_display_alias(qtbot, monkeypatch):
    launcher, fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher.refresh_node_info = REAL_REFRESH_NODE_INFO.__get__(launcher, frm_main.EdgeNodeLauncher)

    assert launcher.container_combo.currentText() == "alpha"

    launcher.refresh_node_info()

    assert "alpha" not in fake_handler.container_names
    assert fake_handler.container_names[-1] == "r1node"
    assert fake_handler.node_info_requests == 1
    assert fake_config.get_container("r1node").node_address == "0xfreshnode"


def test_force_refresh_empty_addresses_clear_stale_display(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)

    def return_empty_node_info(on_success, _on_error):
        on_success(
            NodeInfo(
                address="",
                eth_address="",
                alias="fresh",
                version_long="",
                version_short="",
                whitelist=[],
            )
        )

    fake_handler.get_node_info = return_empty_node_info
    launcher.addressDisplay.setText("Address: stale")
    launcher.ethAddressDisplay.setText("ETH Address: stale")
    launcher.copyAddrButton.show()
    launcher.copyEthButton.show()

    launcher.force_refresh_all()

    assert launcher.addressDisplay.text() == "Address: -"
    assert launcher.ethAddressDisplay.text() == "ETH Address: -"
    assert launcher.nameDisplay.text() == "Name: fresh"
    assert not launcher.copyAddrButton.isVisible()
    assert not launcher.copyEthButton.isVisible()


def test_toggle_state_targets_selected_container_id_not_display_alias(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)

    assert launcher.container_combo.currentText() == "alpha"

    launcher.update_toggle_button_text()

    assert "alpha" not in fake_handler.container_names
    assert fake_handler.container_names[-1] == "r1node"


def test_container_selection_checks_docker_with_container_id_not_display_alias(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    checked_containers = []
    launcher.container_exists_in_docker = lambda name: checked_containers.append(name) or False

    launcher._on_container_selected("alpha")

    assert checked_containers == ["r1node"]
    assert fake_handler.container_name == "r1node"


def test_container_selection_cached_data_clears_missing_eth_address(qtbot, monkeypatch):
    launcher, fake_config, _fake_handler = _build_launcher(
        monkeypatch,
        qtbot,
        running=False,
        config_setup=lambda config: setattr(config.containers[0], "eth_address", None),
    )
    launcher.ethAddressDisplay.setText("ETH Address: stale")
    launcher.copyEthButton.show()

    launcher._on_container_selected("alpha")

    assert launcher.addressDisplay.text() == "Address: 0xnodeaddress"
    assert launcher.copyAddrButton.isVisible()
    assert launcher.ethAddressDisplay.text() == "ETH Address: -"
    assert not launcher.copyEthButton.isVisible()
    assert fake_config.get_container("r1node").eth_address is None


def test_copy_address_fallback_uses_container_id_not_display_alias(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.node_addr = None
    launcher.node_eth_address = None

    launcher.copy_address()
    assert QApplication.clipboard().text() == "0xnodeaddress"

    launcher.copy_eth_address()
    assert QApplication.clipboard().text() == "0xethaddress"

    assert launcher.toast.notifications[-2:] == [
        (NotificationType.SUCCESS, frm_main.NOTIFICATION_ADDRESS_COPIED.format(address="0xnodeaddress")),
        (NotificationType.SUCCESS, frm_main.NOTIFICATION_ADDRESS_COPIED.format(address="0xethaddress")),
    ]


def test_stale_node_info_failures_do_not_restart_other_nodes(qtbot, monkeypatch):
    launcher, fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    fake_config.add_container(
        ContainerConfig(
            name="r1node2",
            volume="r1vol2",
            node_alias="beta",
        )
    )
    launcher.refresh_container_list()
    assert launcher._select_container_by_name("r1node2")

    assert not launcher._should_restart_after_node_info_failure("r1node")

    assert launcher._select_container_by_name("r1node")
    launcher._begin_lifecycle_operation("add_node", "r1node2")
    assert not launcher._should_restart_after_node_info_failure("r1node")
    launcher._end_lifecycle_operation("r1node2")

    launcher._start_docker_pull("r1node2", "r1vol2")
    assert not launcher._should_restart_after_node_info_failure("r1node")

    launcher._finish_docker_pull()
    launcher.user_stopped_container = True
    assert not launcher._should_restart_after_node_info_failure("r1node")

    launcher.user_stopped_container = False
    assert launcher._should_restart_after_node_info_failure("r1node")


def test_close_event_clears_deleted_dialog_reference(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    dialog = frm_main.LoadingDialog(launcher, title="Launching Node", message="Please wait")
    launcher.launcher_dialog = dialog
    sip.delete(dialog)

    class FakeCloseEvent:
        def __init__(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    event = FakeCloseEvent()
    launcher.closeEvent(event)

    assert event.accepted
    assert launcher.launcher_dialog is None
    assert not any("Error closing launcher_dialog" in line for line in launcher.log_buffer)


def test_late_launch_success_does_not_update_ui_during_shutdown(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    callbacks = {}
    ui_updates = []

    def defer_launch(volume_name=None, callback=None, error_callback=None):
        fake_handler.launched_containers.append((fake_handler.container_name, volume_name))
        callbacks["success"] = callback

    fake_handler.launch_container_threaded = defer_launch
    launcher.post_launch_setup = lambda: ui_updates.append("post_launch_setup")
    launcher.refresh_node_info = lambda: ui_updates.append("refresh_node_info")
    launcher.plot_data = lambda: ui_updates.append("plot_data")
    launcher.update_toggle_button_text = lambda: ui_updates.append("update_toggle_button_text")
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._perform_container_launch_after_pull("r1node", "r1vol")
    setattr(launcher, "_EdgeNodeLauncher__shutting_down", True)
    callbacks["success"](("", "", 0))

    assert fake_handler.launched_containers == [("r1node", "r1vol")]
    assert ui_updates == []
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    log_text = "\n".join(launcher.log_buffer)
    if launcher.logView is not None:
        log_text += launcher.logView.toPlainText()
    assert "Ignoring launch success for r1node" in log_text


def test_launch_preparation_does_not_run_blocking_docker_checks_on_ui_thread(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    fake_handler.get_launch_command = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("launch command should be built in Docker worker thread")
    )
    launcher.container_exists_in_docker = lambda _name: (_ for _ in ()).throw(
        AssertionError("container existence should be handled in Docker worker thread")
    )
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._perform_container_launch("r1node", "r1vol")

    assert fake_handler.pull_requests == 1
    assert fake_handler.launched_containers == []
    assert getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress") is True


def test_refresh_all_auto_start_does_not_sleep_on_ui_thread(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    calls = []

    launcher._start_container = lambda: calls.append("start")
    launcher.update_resources_display = lambda: calls.append("resources")
    launcher._refresh_local_containers = lambda: calls.append("containers")

    launcher.refresh_all()

    assert calls == ["start"]


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
    layout = launcher.graphView.layout()

    assert launcher.graphView.objectName() == "metricsGraphGrid"
    assert layout.count() == 4
    assert layout.spacing() == 10

    expected = {
        "cpuPlotContainer": (launcher.cpu_plot, 0, 0),
        "memoryPlotContainer": (launcher.memory_plot, 0, 1),
        "gpuPlotContainer": (launcher.gpu_plot, 1, 0),
        "gpuMemoryPlotContainer": (launcher.gpu_memory_plot, 1, 1),
    }

    for container_name, (plot, row, column) in expected.items():
        container = launcher.findChild(QWidget, container_name)

        assert container is not None
        assert container.property("class") == "plot-container"
        assert plot.parent() is container
        assert container.layout().count() == 1
        assert container.layout().contentsMargins().left() == 0
        assert layout.itemAtPosition(row, column).widget() is container


def test_main_window_log_view_has_stable_identity_and_dimensions(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    dashboard_panel = launcher.findChild(QWidget, "dashboardPanel")
    dashboard_splitter = launcher.findChild(QSplitter, "dashboardSplitter")

    assert dashboard_panel is not None
    assert dashboard_splitter is not None
    assert dashboard_splitter.orientation() == Qt.Vertical
    assert dashboard_splitter.count() == 2
    assert dashboard_panel.layout().indexOf(dashboard_splitter) >= 0
    assert dashboard_splitter.widget(0) is launcher.graphView
    assert dashboard_splitter.widget(1) is launcher.logView
    assert not dashboard_splitter.childrenCollapsible()
    assert launcher.logView.objectName() == "logView"
    assert launcher.findChild(QTextEdit, "logView") is launcher.logView
    assert launcher.logView.isReadOnly()
    assert launcher.logView.minimumHeight() == 120
    assert launcher.logView.maximumHeight() > 150
    assert launcher.logView.font().family() == "Courier New"

    launcher.add_log("log view identity smoke", debug=True)

    assert "log view identity smoke" in launcher.logView.toPlainText()


def test_dashboard_splitter_restores_saved_sizes(qtbot, monkeypatch):
    set_sizes_calls = []
    original_set_sizes = frm_main.QSplitter.setSizes

    def record_set_sizes(splitter, sizes):
        if splitter.objectName() == "dashboardSplitter":
            set_sizes_calls.append(list(sizes))
        return original_set_sizes(splitter, sizes)

    monkeypatch.setattr(frm_main.QSplitter, "setSizes", record_set_sizes)

    _launcher, _fake_config, _fake_handler = _build_launcher(
        monkeypatch,
        qtbot,
        config_setup=lambda config: setattr(config, "dashboard_splitter_sizes", [420, 160]),
    )

    assert [420, 160] in set_sizes_calls


def test_dashboard_splitter_saves_current_sizes(qtbot, monkeypatch):
    launcher, fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    splitter = launcher.findChild(QSplitter, "dashboardSplitter")

    splitter.setSizes([480, 180])
    launcher._save_dashboard_splitter_sizes()

    assert fake_config.dashboard_splitter_sizes == splitter.sizes()


def test_main_window_restores_saved_geometry_inside_available_screen(qtbot, monkeypatch):
    available = QRect(0, 40, 1366, 728)
    monkeypatch.setattr(
        frm_main.EdgeNodeLauncher,
        "_available_screen_geometry",
        lambda self: QRect(available),
    )

    launcher, _fake_config, _fake_handler = _build_launcher(
        monkeypatch,
        qtbot,
        config_setup=lambda config: setattr(
            config,
            "main_window_geometry",
            {"x": -2000, "y": -1000, "width": 1600, "height": 900},
        ),
    )

    geometry = launcher.geometry()

    assert geometry.x() >= available.x()
    assert geometry.y() >= available.y()
    assert geometry.width() <= available.width()
    assert geometry.height() <= available.height()


def test_main_window_geometry_flush_persists_current_size_and_position(qtbot, monkeypatch):
    launcher, fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    launcher.setGeometry(40, 50, 1200, 800)
    launcher._flush_window_geometry_log()

    assert fake_config.main_window_geometry == {
        "x": 40,
        "y": 50,
        "width": 1200,
        "height": 800,
    }


def test_main_window_sidebar_sections_group_controls(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    expected_sections = {
        "nodeControlsSectionLabel": "Node",
        "networkActionsSectionLabel": "Network",
        "statusSectionLabel": "Status",
        "settingsSectionLabel": "Settings",
    }

    for object_name, text in expected_sections.items():
        label = launcher.findChild(QLabel, object_name)

        assert label is not None
        assert label.text() == text
        assert label.property("role") == "sidebarSection"


def test_rename_action_lives_with_node_controls(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    top_button_area = launcher.findChild(QVBoxLayout, "topButtonArea")
    bottom_button_area = launcher.findChild(QVBoxLayout, "bottomButtonArea")

    assert top_button_area is not None
    assert bottom_button_area is not None
    assert top_button_area.indexOf(launcher.renameNodeButton) >= 0
    assert bottom_button_area.indexOf(launcher.renameNodeButton) == -1


def test_refresh_action_lives_with_status_section(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    top_button_area = launcher.findChild(QVBoxLayout, "topButtonArea")
    status_label = launcher.findChild(QLabel, "statusSectionLabel")

    assert top_button_area is not None
    assert status_label is not None
    assert top_button_area.indexOf(status_label) < top_button_area.indexOf(launcher.refreshButton)


def test_docker_download_action_lives_with_network_actions(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    top_button_area = launcher.findChild(QVBoxLayout, "topButtonArea")
    network_label = launcher.findChild(QLabel, "networkActionsSectionLabel")

    assert top_button_area is not None
    assert network_label is not None
    assert top_button_area.indexOf(network_label) < top_button_area.indexOf(
        launcher.docker_download_button
    )
    assert top_button_area.indexOf(launcher.docker_download_button) < top_button_area.indexOf(
        launcher.dapp_button
    )


def test_status_panels_have_semantic_roles(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    info_box = launcher.findChild(QGroupBox, "infoBox")
    resources_box = launcher.findChild(QGroupBox, "resourcesBox")

    assert info_box is not None
    assert resources_box is not None
    assert info_box.property("role") == "statusPanel"
    assert resources_box.property("role") == "resourcePanel"
    assert info_box.findChild(QPushButton, "copyAddrButton") is launcher.copyAddrButton
    assert info_box.findChild(QPushButton, "copyEthButton") is launcher.copyEthButton
    assert resources_box.findChild(QLabel, "resourcesBoxText") is not None


def test_main_window_sidebar_controls_are_scrollable(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    sidebar_scroll = launcher.findChild(QScrollArea, "sidebarScrollArea")

    assert sidebar_scroll is not None
    assert sidebar_scroll.widgetResizable()
    assert sidebar_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert sidebar_scroll.widget().objectName() == "sidebarPanel"
    assert sidebar_scroll.widget().property("role") == "navigationSidebar"
    assert sidebar_scroll.widget().findChild(QPushButton, "addNodeButton") is launcher.add_node_button
    assert sidebar_scroll.widget().findChild(QPushButton, "renameNodeButton") is launcher.renameNodeButton
