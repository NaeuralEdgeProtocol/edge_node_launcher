import webbrowser
from pathlib import Path
from types import SimpleNamespace

from PyQt5 import sip
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QGroupBox, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget

import app_forms.frm_main as frm_main
from models.NodeHistory import NodeHistory
from models.NodeInfo import NodeInfo
from utils.config_manager import ContainerConfig
from widgets.DockerPullDialog import DockerPullDialog
from widgets.ToastWidget import NotificationType
import widgets.app_widgets.dashboard_panel as dashboard_panel_module
from widgets.app_widgets.activity_log import ActivityLogWidget
from widgets.app_widgets.lifecycle_dialog_presenter import LifecycleDialogPresenter
from widgets.app_widgets.sidebar_status_cards import NodeStatusPanel, ResourceStatusPanel


REAL_PLOT_DATA = frm_main.EdgeNodeLauncher.plot_data
REAL_PLOT_GRAPHS = frm_main.EdgeNodeLauncher.plot_graphs
REAL_REFRESH_NODE_INFO = frm_main.EdgeNodeLauncher.refresh_node_info
REAL_MAYBE_REFRESH_UPTIME = frm_main.EdgeNodeLauncher.maybe_refresh_uptime


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
        self.last_used_updates = []
        self.volume_updates = []
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
        self.last_used_updates.append((container_name, timestamp))
        container = self.get_container(container_name)
        if container:
            container.last_used = timestamp
        return True

    def update_volume(self, container_name, volume_name):
        self.volume_updates.append((container_name, volume_name))
        container = self.get_container(container_name)
        if container:
            container.volume = volume_name
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
    monkeypatch.setattr(frm_main.EdgeNodeLauncher, "plot_data", lambda self, *args, **kwargs: None)
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
    for plot_attr in ("cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"):
        getattr(launcher, plot_attr).disable_late_paints()

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


def test_add_log_does_not_process_events_synchronously(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    def fail_process_events(*args, **kwargs):
        raise AssertionError("add_log should not pump the Qt event loop synchronously")

    with monkeypatch.context() as process_events_patch:
        process_events_patch.setattr(frm_main.QApplication, "processEvents", fail_process_events)
        launcher.add_log("visible log entry")

    assert "visible log entry" in launcher.logView.toPlainText()


def test_main_window_does_not_process_events_synchronously():
    source = Path(frm_main.__file__).read_text(encoding="utf-8")

    assert "QApplication.processEvents" not in source


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


def test_status_card_address_rows_keep_text_visible_next_to_copy_buttons(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    launcher._update_node_identity_display(
        "0xnodeaddress",
        "0xethaddress",
        "alpha",
        show_copy_buttons=True,
    )
    qtbot.wait(50)

    assert launcher.addressDisplay.objectName() == "nodeAddressDisplay"
    assert launcher.ethAddressDisplay.objectName() == "nodeEthAddressDisplay"
    assert launcher.addressDisplay.property("statusField") == "address"
    assert launcher.ethAddressDisplay.property("statusField") == "address"
    assert launcher.copyAddrButton.accessibleName() == "Copy node address"
    assert launcher.copyEthButton.accessibleName() == "Copy ETH address"
    assert launcher.addressDisplay.text() == "Address: 0xnodeaddress"
    assert launcher.ethAddressDisplay.text() == "ETH Address: 0xethaddress"
    assert launcher.copyAddrButton.isVisible()
    assert launcher.copyEthButton.isVisible()
    assert launcher.addressDisplay.width() > launcher.copyAddrButton.width()
    assert launcher.ethAddressDisplay.width() > launcher.copyEthButton.width()


def test_status_card_uses_semantic_label_roles(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    metadata_labels = (
        launcher.nameDisplay,
        launcher.node_uptime,
        launcher.node_epoch,
        launcher.node_epoch_avail,
        launcher.node_version,
    )

    assert launcher.addressDisplay.property("statusField") == "address"
    assert launcher.ethAddressDisplay.property("statusField") == "address"
    assert launcher.addressDisplay.font().family() == "Courier New"
    assert launcher.ethAddressDisplay.font().family() == "Courier New"
    assert launcher.addressDisplay.font().pointSize() == 9
    assert not launcher.addressDisplay.wordWrap()
    assert launcher.addressDisplay.minimumHeight() == 20
    assert launcher.addressDisplay.sizePolicy().verticalPolicy() == QSizePolicy.Fixed

    for label in metadata_labels:
        assert label.property("statusField") == "metadata"
        assert label.font().family() == "Segoe UI"
        assert label.font().pointSize() == 9
        assert not label.wordWrap()
        assert label.minimumHeight() == 20
        assert label.sizePolicy().verticalPolicy() == QSizePolicy.Fixed

    assert 'QLabel[statusField="address"]' in frm_main.DARK_STYLESHEET
    assert 'QLabel[statusField="metadata"]' in frm_main.DARK_STYLESHEET


def test_resource_panel_uses_semantic_label_roles(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    resource_labels = (
        (launcher.memoryDisplay, "memoryResourceDisplay", "memory", "Memory usage"),
        (launcher.vcpusDisplay, "cpuResourceDisplay", "cpu", "CPU usage"),
        (launcher.storageDisplay, "storageResourceDisplay", "storage", "Storage usage"),
    )

    for label, object_name, field_role, accessible_name in resource_labels:
        assert label.objectName() == object_name
        assert label.property("resourceField") == field_role
        assert label.accessibleName() == accessible_name
        assert label.font().family() == "Segoe UI"
        assert label.font().pointSize() == 9
        assert not label.wordWrap()
        assert label.minimumHeight() == 20
        assert label.sizePolicy().verticalPolicy() == QSizePolicy.Fixed

    assert 'QLabel[resourceField="memory"]' in frm_main.DARK_STYLESHEET
    assert 'QLabel[resourceField="cpu"]' in frm_main.DARK_STYLESHEET
    assert 'QLabel[resourceField="storage"]' in frm_main.DARK_STYLESHEET


def test_sidebar_status_resource_labels_elide_without_losing_full_text(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    long_eth = "ETH Address: 0x" + ("a" * 48)
    launcher.ethAddressDisplay.resize(90, 20)
    launcher.ethAddressDisplay.setText(long_eth)

    assert launcher.ethAddressDisplay.text() == long_eth
    assert launcher.ethAddressDisplay.toolTip() == long_eth
    assert QLabel.text(launcher.ethAddressDisplay) != long_eth
    assert QLabel.text(launcher.ethAddressDisplay).startswith("ETH: ")

    long_memory = "Memory: 123.4 GB / 567.8 GB (91.2% used)"
    launcher.memoryDisplay.resize(120, 20)
    launcher.memoryDisplay.setText(long_memory)

    assert launcher.memoryDisplay.text() == long_memory
    assert launcher.memoryDisplay.toolTip() == long_memory
    assert QLabel.text(launcher.memoryDisplay) != long_memory
    assert QLabel.text(launcher.memoryDisplay).startswith("Mem: ")

    cpu_text = "vCPUs: 14 cores (38.4% used)"
    launcher.vcpusDisplay.resize(220, 20)
    launcher.vcpusDisplay.setText(cpu_text)

    assert launcher.vcpusDisplay.text() == cpu_text
    assert QLabel.text(launcher.vcpusDisplay).startswith("CPU: ")
    assert "used" not in QLabel.text(launcher.vcpusDisplay)


def test_stylesheets_do_not_reference_removed_status_selectors():
    source = Path(frm_main.__file__).read_text(encoding="utf-8")
    combined_stylesheets = frm_main.DARK_STYLESHEET + frm_main.LIGHT_STYLESHEET

    assert "infoBoxText" not in source
    assert "infoBoxText" not in combined_stylesheets
    assert "resourcesBoxText" not in source
    assert "resourcesBoxText" not in combined_stylesheets
    assert "myComboPopup" not in combined_stylesheets
    assert "No additional styles needed" not in combined_stylesheets


def test_status_card_runtime_labels_use_consistent_copy(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher.maybe_refresh_uptime = REAL_MAYBE_REFRESH_UPTIME.__get__(launcher, frm_main.EdgeNodeLauncher)

    launcher._EdgeNodeLauncher__current_node_uptime = "1h 2m"
    launcher._EdgeNodeLauncher__current_node_epoch = 42
    launcher._EdgeNodeLauncher__current_node_epoch_avail = 0.25
    launcher._EdgeNodeLauncher__current_node_ver = "1.2.3"

    launcher.maybe_refresh_uptime(assume_running=True)

    assert launcher.node_uptime.text() == "Uptime: 1h 2m"
    assert launcher.node_epoch.text() == "Epoch: 42"
    assert launcher.node_epoch_avail.text() == "Epoch availability: 25.0%"
    assert launcher.node_version.text() == "Version: 1.2.3"


def test_status_card_initial_metadata_uses_placeholders(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    assert launcher.node_uptime.text() == "Uptime: -"
    assert launcher.node_epoch.text() == "Epoch: -"
    assert launcher.node_epoch_avail.text() == "Epoch availability: -"
    assert launcher.node_version.text() == "Version: -"


def test_status_card_refreshes_when_epoch_changes_without_uptime_change(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher.maybe_refresh_uptime = REAL_MAYBE_REFRESH_UPTIME.__get__(launcher, frm_main.EdgeNodeLauncher)

    launcher._EdgeNodeLauncher__current_node_uptime = "1h"
    launcher._EdgeNodeLauncher__current_node_epoch = 1
    launcher._EdgeNodeLauncher__current_node_epoch_avail = 0.1
    launcher._EdgeNodeLauncher__current_node_ver = "1.0.0"
    launcher.maybe_refresh_uptime(assume_running=True)

    launcher._EdgeNodeLauncher__current_node_epoch = 2
    launcher._EdgeNodeLauncher__current_node_epoch_avail = 0.2
    launcher._EdgeNodeLauncher__current_node_ver = "1.0.1"
    launcher.maybe_refresh_uptime(assume_running=True)

    assert launcher.node_uptime.text() == "Uptime: 1h"
    assert launcher.node_epoch.text() == "Epoch: 2"
    assert launcher.node_epoch_avail.text() == "Epoch availability: 20.0%"
    assert launcher.node_version.text() == "Version: 1.0.1"


def test_status_card_stopped_labels_use_consistent_copy(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.maybe_refresh_uptime = REAL_MAYBE_REFRESH_UPTIME.__get__(launcher, frm_main.EdgeNodeLauncher)

    launcher.maybe_refresh_uptime(assume_running=False)

    assert launcher.node_uptime.text() == "Uptime: STOPPED"
    assert launcher.node_epoch.text() == "Epoch: N/A"
    assert launcher.node_epoch_avail.text() == "Epoch availability: 0%"
    assert launcher.node_version.text() == "Version: N/A"


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


def test_start_button_double_click_does_not_start_second_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launch_requests = []
    launcher._perform_container_launch = lambda container_name, volume_name: launch_requests.append((container_name, volume_name))

    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)
    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)

    assert launch_requests == [("r1node", "r1vol")]
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") == {
        "operation": "start",
        "container_name": "r1node",
    }


def test_stop_button_double_click_does_not_start_second_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    stop_requests = []

    def defer_stop(container_name, callback, error_callback):
        stop_requests.append(container_name)

    fake_handler.stop_container_threaded = defer_stop

    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)
    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)

    assert stop_requests == ["r1node"]
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") == {
        "operation": "stop",
        "container_name": "r1node",
    }


def test_scheduled_dialog_close_does_not_clear_replaced_dialog(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    first_dialog = frm_main.LoadingDialog(launcher, title="Launching Node", message="First")
    replacement_dialog = frm_main.LoadingDialog(launcher, title="Launching Node", message="Replacement")
    launcher.launcher_dialog = first_dialog
    callbacks = []

    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda delay, callback: callbacks.append((delay, callback)))

    assert launcher._schedule_safe_close_dialog_reference(
        "launcher_dialog",
        close_delay_ms=500,
        clear_delay_ms=1000,
    )

    launcher.launcher_dialog = replacement_dialog
    for _delay, callback in callbacks:
        callback()

    assert launcher.launcher_dialog is replacement_dialog


def test_immediate_dialog_close_does_not_clear_replaced_dialog(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    first_dialog = frm_main.LoadingDialog(launcher, title="Launching Node", message="First")
    replacement_dialog = frm_main.LoadingDialog(launcher, title="Launching Node", message="Replacement")
    launcher.launcher_dialog = first_dialog

    def replace_during_close():
        launcher.launcher_dialog = replacement_dialog

    first_dialog.safe_close = replace_during_close

    assert launcher._close_dialog_reference("launcher_dialog") is True
    assert launcher.launcher_dialog is replacement_dialog


def test_launch_loading_dialog_helper_sets_progress_message(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    dialog = launcher._lifecycle_dialogs.show_launch_loading("alpha")

    assert launcher.launcher_dialog is dialog
    assert dialog.windowTitle() == "Launching Node"
    assert dialog.message_label.text() == "Preparing to launch Docker container..."


def test_new_node_loading_dialog_helper_preserves_initial_copy(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    dialog = launcher._lifecycle_dialogs.show_new_node_loading("beta")

    assert launcher.startup_dialog is dialog
    assert dialog.windowTitle() == "Starting Node"
    assert dialog.message_label.text() == "Please wait while node 'beta' is being launched..."


def test_lifecycle_dialog_presenter_backs_launch_progress_helpers(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    assert isinstance(launcher._lifecycle_dialogs, LifecycleDialogPresenter)

    dialog = launcher._lifecycle_dialogs.show_launch_loading("alpha")

    assert launcher._dialog_reference("launcher_dialog") is dialog
    assert launcher._lifecycle_dialogs.reference("launcher_dialog") is dialog
    assert launcher._update_launch_dialog_progress("Launching Docker container...")
    assert dialog.message_label.text() == "Launching Docker container..."


def test_stop_loading_dialog_helper_sets_progress_message(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)

    dialog = launcher._lifecycle_dialogs.show_stop_loading("alpha")

    assert launcher.toggle_dialog is dialog
    assert launcher._lifecycle_dialogs.reference("toggle_dialog") is dialog
    assert dialog.windowTitle() == "Stopping Node"
    assert dialog.message_label.text() == "Preparing to stop Docker container..."


def test_stop_success_callback_updates_ui_and_clears_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    ui_calls = []
    progress_messages = []
    real_update_progress = launcher._lifecycle_dialogs.update_progress

    launcher._lifecycle_dialogs.show_stop_loading("alpha")
    launcher._begin_lifecycle_operation("stop", "r1node")
    launcher.loading_indicator.start()
    launcher.update_toggle_button_text = lambda: ui_calls.append("toggle")
    launcher.refresh_node_info = lambda: ui_calls.append("node_info")
    launcher.maybe_refresh_uptime = lambda: ui_calls.append("uptime")
    launcher.plot_data = lambda: ui_calls.append("plot")
    launcher._queue_ui_refresh = lambda *args, **_kwargs: ui_calls.append("queue")
    launcher._lifecycle_dialogs.update_progress = (
        lambda dialog_attr, message, **kwargs: progress_messages.append(message)
        or real_update_progress(dialog_attr, message, **kwargs)
    )
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())

    on_success, _on_error = launcher._create_stop_container_callbacks("r1node")

    on_success(("", "", 0))

    assert progress_messages == [
        "Container stopped, updating UI...",
        "Container stopped successfully!",
    ]
    assert ui_calls == ["toggle", "node_info", "uptime", "plot", "queue"]
    assert launcher.user_stopped_container is True
    assert launcher.toggle_dialog is None
    assert not launcher.loading_indicator.timer.isActive()
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.SUCCESS, "Node 'alpha' stopped successfully")
    ]


def test_stop_return_code_failure_closes_dialog_and_clears_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)

    def fail_stop(container_name, callback, error_callback):
        fake_handler.stopped_containers.append(container_name)
        callback(("", "permission denied", 1))

    fake_handler.stop_container_threaded = fail_stop
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())

    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)

    assert fake_handler.stopped_containers == ["r1node"]
    assert launcher.toggle_dialog is None
    assert not launcher.loading_indicator.timer.isActive()
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.ERROR, "Failed to stop container: permission denied")
    ]


def test_stop_error_callback_reports_and_clears_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher._lifecycle_dialogs.show_stop_loading("alpha")
    launcher._begin_lifecycle_operation("stop", "r1node")
    launcher.loading_indicator.start()
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())

    _on_success, on_error = launcher._create_stop_container_callbacks("r1node")

    on_error("daemon unavailable")

    assert launcher.toggle_dialog is None
    assert not launcher.loading_indicator.timer.isActive()
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.ERROR, "Error stopping container: daemon unavailable")
    ]


def test_start_after_container_exited_can_supersede_stop_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launch_requests = []
    launcher._perform_container_launch = lambda container_name, volume_name: launch_requests.append((container_name, volume_name))
    launcher._begin_lifecycle_operation("stop", "r1node")

    qtbot.mouseClick(launcher.toggleButton, Qt.LeftButton)

    assert fake_handler.container_names[-1] == "r1node"
    assert launch_requests == [("r1node", "r1vol")]
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") == {
        "operation": "start",
        "container_name": "r1node",
    }


def test_main_window_theme_and_force_debug_buttons(qtbot, monkeypatch):
    launcher, fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.plot_graphs = lambda: None
    launcher.update_resources_display = lambda: None
    launcher.update_toggle_button_text = lambda: None

    assert launcher.themeToggleButton.objectName() == "themeToggleButton"
    assert launcher.force_debug_checkbox.objectName() == "forceDebugCheckbox"
    assert launcher.force_debug_checkbox.property("role") == "settingsToggle"
    assert launcher.force_debug_checkbox.accessibleName() == "Force Debug Mode"
    assert launcher.force_debug_checkbox.font().family() != "Courier New"
    assert launcher.force_debug_checkbox.minimumHeight() >= 32
    assert launcher.force_debug_checkbox.styleSheet() == ""

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


def test_rename_dialog_double_click_saves_once(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    updates = []

    def defer_update_node_name(new_name, on_success, on_error):
        updates.append(new_name)

    fake_handler.update_node_name = defer_update_node_name

    def click_save_twice(dialog):
        name_input = dialog.findChild(QLineEdit, "renameNodeNameInput")
        save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
        cancel_button = dialog.findChild(QPushButton, "renameNodeCancelButton")
        assert name_input is not None
        assert save_button is not None
        assert cancel_button is not None

        name_input.setText("renamed")
        save_button.click()
        assert not save_button.isEnabled()
        assert not cancel_button.isEnabled()
        assert save_button.text() == "Saving..."
        save_button.click()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", click_save_twice)

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert updates == ["renamed"]


def test_rename_dialog_invalid_name_keeps_save_enabled(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    observed = {}

    def fail_update_node_name(*args, **kwargs):
        raise AssertionError("invalid rename input should not submit an update request")

    fake_handler.update_node_name = fail_update_node_name

    def click_invalid_save(dialog):
        name_input = dialog.findChild(QLineEdit, "renameNodeNameInput")
        save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
        cancel_button = dialog.findChild(QPushButton, "renameNodeCancelButton")
        assert name_input is not None
        assert save_button is not None
        assert cancel_button is not None

        name_input.setText("bad name!")
        save_button.click()
        observed["save_enabled"] = save_button.isEnabled()
        observed["cancel_enabled"] = cancel_button.isEnabled()
        observed["save_text"] = save_button.text()
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", click_invalid_save)

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert observed == {
        "save_enabled": True,
        "cancel_enabled": True,
        "save_text": "Save",
    }
    assert launcher.toast.notifications[-1] == (
        NotificationType.ERROR,
        "Node name can only contain letters (a-z, A-Z), numbers (0-9), hyphens (-), and underscores (_)",
    )


def test_rename_dialog_error_reenables_save(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    observed = {}

    def fail_update_node_name(new_name, on_success, on_error):
        on_error("Error: timeout")

    fake_handler.update_node_name = fail_update_node_name

    def click_save(dialog):
        name_input = dialog.findChild(QLineEdit, "renameNodeNameInput")
        save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
        cancel_button = dialog.findChild(QPushButton, "renameNodeCancelButton")
        assert name_input is not None
        assert save_button is not None
        assert cancel_button is not None

        name_input.setText("renamed")
        save_button.click()
        observed["save_enabled"] = save_button.isEnabled()
        observed["cancel_enabled"] = cancel_button.isEnabled()
        observed["save_text"] = save_button.text()
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", click_save)

    qtbot.mouseClick(launcher.renameNodeButton, Qt.LeftButton)

    assert observed == {
        "save_enabled": True,
        "cancel_enabled": True,
        "save_text": "Save",
    }
    assert launcher.toast.notifications[-1] == (
        NotificationType.ERROR,
        "Failed to rename node: Operation timed out. Please check your connection and try again.",
    )


def test_rename_restart_does_not_override_active_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher._begin_lifecycle_operation("start", "r1node")

    launcher._restart_container_after_rename("r1node")

    assert fake_handler.stopped_containers == []
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") == {
        "operation": "start",
        "container_name": "r1node",
    }


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


def test_docker_pull_completion_closes_dialog_reference(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.docker_pull_dialog = DockerPullDialog(launcher)
    launcher._start_docker_pull("r1node", "r1vol")
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._on_docker_pull_complete(False, "network error")

    assert launcher.docker_pull_dialog is None
    assert getattr(launcher, "_EdgeNodeLauncher__docker_pull_in_progress") is False
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.ERROR, "Failed to pull Docker image: network error")
    ]


def test_docker_pull_close_does_not_clear_replaced_dialog(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    original_dialog = DockerPullDialog(launcher)
    replacement_dialog = DockerPullDialog(launcher)
    launcher.docker_pull_dialog = original_dialog

    def replace_during_close():
        launcher.docker_pull_dialog = replacement_dialog

    original_dialog.safe_close = replace_during_close

    assert launcher._close_docker_pull_dialog_reference() is True
    assert launcher.docker_pull_dialog is replacement_dialog


def test_docker_pull_output_clears_deleted_dialog_reference(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    callbacks = {}

    def defer_pull(callback, error_callback, output_callback=None):
        callbacks["output"] = output_callback

    fake_handler.pull_image = defer_pull
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._perform_container_launch("r1node", "r1vol")
    assert launcher.docker_pull_dialog is not None
    sip.delete(launcher.docker_pull_dialog)

    callbacks["output"]("abcdef123456: Downloading 50%")

    assert launcher.docker_pull_dialog is None


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


def _history_with_optional_gpu(gpu_load=None, gpu_occupied_memory=None):
    return NodeHistory(
        address="0xnode",
        alias="alpha",
        cpu_load=[10.0, 20.0],
        cpu_temp=[40.0, 41.0],
        current_epoch=1,
        current_epoch_avail=0.5,
        eth_address="0xeth",
        gpu_load=gpu_load,
        gpu_occupied_memory=gpu_occupied_memory,
        gpu_temp=None,
        gpu_total_memory=None,
        last_epochs=[1, 2],
        last_save_time="2026-05-03T01:00:10",
        occupied_memory=[512.0, 768.0],
        timestamps=["2026-05-03T01:00:00", "2026-05-03T01:00:10"],
        total_memory=[1024.0, 1024.0],
        uptime="1m",
        version="test-version",
    )


def test_plot_graphs_uses_selected_container_id_not_display_alias(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher.plot_graphs = REAL_PLOT_GRAPHS.__get__(launcher, frm_main.EdgeNodeLauncher)
    log_messages = []
    launcher.add_log = lambda message, **kwargs: log_messages.append(message)

    assert launcher.container_combo.currentText() == "alpha"
    assert launcher._selected_container_name() == "r1node"

    launcher.plot_graphs(_history_with_optional_gpu())

    assert any("Updated graphs for container r1node" in message for message in log_messages)
    assert not any("Updated graphs for container alpha" in message for message in log_messages)


def test_plot_graphs_clears_stale_gpu_plots_when_history_has_no_gpu(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher.plot_graphs = REAL_PLOT_GRAPHS.__get__(launcher, frm_main.EdgeNodeLauncher)
    launcher.add_log = lambda *args, **kwargs: None

    launcher.plot_graphs(_history_with_optional_gpu(gpu_load=[30.0, 40.0], gpu_occupied_memory=[1024.0, 2048.0]))
    assert len(launcher.gpu_plot.listDataItems()) == 1
    assert len(launcher.gpu_memory_plot.listDataItems()) == 1
    assert launcher.cpu_plot.getPlotItem().titleLabel.text == ""
    assert launcher.memory_plot.getPlotItem().titleLabel.text == ""
    assert launcher.gpu_plot.getPlotItem().titleLabel.text == ""
    assert launcher.gpu_memory_plot.getPlotItem().titleLabel.text == ""
    assert not launcher.cpu_plot._r1_empty_label.isVisible()
    assert not launcher.memory_plot._r1_empty_label.isVisible()
    assert not launcher.gpu_plot._r1_empty_label.isVisible()
    assert not launcher.gpu_memory_plot._r1_empty_label.isVisible()

    launcher.plot_graphs(_history_with_optional_gpu())

    assert len(launcher.cpu_plot.listDataItems()) == 1
    assert len(launcher.memory_plot.listDataItems()) == 1
    assert len(launcher.gpu_plot.listDataItems()) == 0
    assert len(launcher.gpu_memory_plot.listDataItems()) == 0
    assert not launcher.cpu_plot._r1_empty_label.isVisible()
    assert not launcher.memory_plot._r1_empty_label.isVisible()
    assert launcher.gpu_plot._r1_empty_label.isVisible()
    assert launcher.gpu_memory_plot._r1_empty_label.isVisible()


def test_plot_graphs_reuses_existing_axis_items(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=True)
    launcher.plot_graphs = REAL_PLOT_GRAPHS.__get__(launcher, frm_main.EdgeNodeLauncher)
    launcher.add_log = lambda *args, **kwargs: None
    axes_before = {
        plot_attr: getattr(launcher, plot_attr).getAxis("bottom")
        for plot_attr in ("cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot")
    }

    launcher.plot_graphs(
        _history_with_optional_gpu(
            gpu_load=[30.0, 40.0],
            gpu_occupied_memory=[1024.0, 2048.0],
        )
    )
    launcher.plot_graphs(
        _history_with_optional_gpu(
            gpu_load=[35.0, 45.0],
            gpu_occupied_memory=[1536.0, 2560.0],
        )
    )

    assert {
        plot_attr: getattr(launcher, plot_attr).getAxis("bottom")
        for plot_attr in axes_before
    } == axes_before


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


def test_close_event_does_not_process_events_synchronously(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    process_event_calls = []

    class FakeCloseEvent:
        def __init__(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    with monkeypatch.context() as process_events_patch:
        process_events_patch.setattr(
            frm_main.QApplication,
            "processEvents",
            lambda *args, **kwargs: process_event_calls.append("processEvents"),
        )
        event = FakeCloseEvent()
        launcher.closeEvent(event)

    assert event.accepted
    assert process_event_calls == []


def test_close_event_disables_metric_plot_updates(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    class FakeCloseEvent:
        def __init__(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    event = FakeCloseEvent()
    launcher.closeEvent(event)

    assert event.accepted
    for plot_attr in ("cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"):
        plot = getattr(launcher, plot_attr)
        assert not plot.updatesEnabled()
        assert not plot.isVisible()
        assert plot._ignore_late_paints


def test_metric_plot_widget_ignores_paint_after_shutdown(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    class FakePaintEvent:
        def __init__(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    event = FakePaintEvent()
    launcher.cpu_plot.disable_late_paints()
    launcher.cpu_plot.paintEvent(event)

    assert event.accepted


def test_metric_plot_widget_ignores_paint_when_hidden(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    class FakePaintEvent:
        def __init__(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    event = FakePaintEvent()
    launcher.cpu_plot.hide()
    launcher.cpu_plot.paintEvent(event)

    assert event.accepted


def test_metric_plot_widgets_keep_strong_axis_references(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    assert set(launcher._metric_axis_items) == {
        "cpu_plot",
        "memory_plot",
        "gpu_plot",
        "gpu_memory_plot",
    }
    for plot_attr, axis in launcher._metric_axis_items.items():
        plot = getattr(launcher, plot_attr)
        assert plot._r1_bottom_axis is axis
        assert plot.getAxis("bottom") is axis


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


def test_launch_conflict_remove_failure_clears_lifecycle_and_reports_error(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    removed_containers = []

    def fail_with_conflict(volume_name=None, callback=None, error_callback=None):
        fake_handler.launched_containers.append((fake_handler.container_name, volume_name))
        error_callback(
            'Conflict. The container name "/r1node" is already in use by container "abc123".'
        )

    def fail_remove(container_name, callback, error_callback, force=True):
        removed_containers.append((container_name, force))
        callback(("", "permission denied", 1))

    fake_handler.launch_container_threaded = fail_with_conflict
    fake_handler.remove_container_threaded = fail_remove
    launcher.launcher_dialog = frm_main.LoadingDialog(
        launcher,
        title="Launching Node",
        message="Please wait",
    )
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._perform_container_launch_after_pull("r1node", "r1vol")

    assert fake_handler.launched_containers == [("r1node", "r1vol")]
    assert removed_containers == [("abc123", True)]
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.launcher_dialog is None
    assert launcher.toast.notifications == [
        (
            NotificationType.ERROR,
            "Failed to remove conflicting container: permission denied",
        )
    ]
    log_text = "\n".join(launcher.log_buffer)
    if launcher.logView is not None:
        log_text += launcher.logView.toPlainText()
    assert "Failed to remove conflicting container: permission denied" in log_text


def test_launch_conflict_remove_success_retries_and_finalizes(qtbot, monkeypatch):
    launcher, fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launch_attempts = []
    removed_containers = []
    progress_messages = []
    ui_updates = []

    def conflict_then_success(volume_name=None, callback=None, error_callback=None):
        launch_attempts.append((fake_handler.container_name, volume_name))
        if len(launch_attempts) == 1:
            error_callback(
                'Conflict. The container name "/r1node" is already in use by container "abc123".'
            )
            return
        callback(("", "", 0))

    def remove_success(container_name, callback, error_callback, force=True):
        removed_containers.append((container_name, force))
        callback(("", "", 0))

    fake_handler.launch_container_threaded = conflict_then_success
    fake_handler.remove_container_threaded = remove_success
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())
    launcher._update_launch_dialog_progress = (
        lambda message, **_kwargs: progress_messages.append(message) or True
    )
    launcher.post_launch_setup = lambda: ui_updates.append("post_launch_setup")
    launcher.refresh_node_info = lambda: ui_updates.append("refresh_node_info")
    launcher.plot_data = lambda assume_running=False: ui_updates.append(
        ("plot_data", assume_running)
    )
    launcher.update_toggle_button_text = lambda assume_running=False: ui_updates.append(
        ("update_toggle_button_text", assume_running)
    )
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._perform_container_launch_after_pull("r1node", "r1vol")

    assert launch_attempts == [("r1node", "r1vol"), ("r1node", "r1vol")]
    assert removed_containers == [("abc123", True)]
    assert progress_messages == [
        "Launching Docker container...",
        "Container name conflict detected. Trying again with container removal...",
        "Container launched, updating configuration...",
        "Updating user interface...",
        "Container launched successfully!",
    ]
    assert fake_config.last_used_updates
    assert fake_config.volume_updates == []
    assert ui_updates == [
        "post_launch_setup",
        "refresh_node_info",
        ("plot_data", True),
        ("update_toggle_button_text", True),
    ]
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.SUCCESS, "Node 'alpha' launched successfully")
    ]


def test_post_pull_launch_success_callback_routes_return_code_failure(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    failures = []
    successes = []

    launcher._finalize_launch_failure = (
        lambda container_name, error_msg: failures.append((container_name, error_msg))
    )
    launcher._finalize_launch_success = (
        lambda container_name, volume_name: successes.append((container_name, volume_name))
    )

    on_launch_success, _on_launch_error = launcher._create_post_pull_launch_callbacks(
        "r1node",
        "r1vol",
    )

    on_launch_success(("stdout", "permission denied", 1))

    assert failures == [("r1node", "Failed to launch container: permission denied")]
    assert successes == []


def test_launch_progress_updates_visible_startup_dialog_without_launcher(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launch_requests = []

    def defer_launch(volume_name=None, callback=None, error_callback=None):
        launch_requests.append((fake_handler.container_name, volume_name))

    fake_handler.launch_container_threaded = defer_launch
    launcher.startup_dialog = frm_main.LoadingDialog(
        launcher,
        title="Starting Node",
        message="Please wait",
    )
    qtbot.addWidget(launcher.startup_dialog)
    launcher.startup_dialog.show()
    launcher._begin_lifecycle_operation("start", "r1node")

    launcher._perform_container_launch_after_pull("r1node", "r1vol")

    assert launch_requests == [("r1node", "r1vol")]
    assert launcher.startup_dialog.message_label.text() == "Launching Docker container..."


def test_finalize_launch_failure_clears_deleted_launch_dialogs(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.launcher_dialog = frm_main.LoadingDialog(
        launcher,
        title="Launching Node",
        message="Please wait",
    )
    launcher.startup_dialog = frm_main.LoadingDialog(
        launcher,
        title="Starting Node",
        message="Please wait",
    )
    sip.delete(launcher.launcher_dialog)
    sip.delete(launcher.startup_dialog)
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._finalize_launch_failure("r1node", "network down")

    assert launcher.launcher_dialog is None
    assert launcher.startup_dialog is None
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.ERROR, "network down")
    ]


def test_finalize_launch_success_updates_config_ui_and_dialogs(qtbot, monkeypatch):
    launcher, fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    fake_config.containers[0].volume = None
    progress_messages = []
    ui_updates = []

    launcher.launcher_dialog = frm_main.LoadingDialog(
        launcher,
        title="Launching Node",
        message="Please wait",
    )
    launcher._update_launch_dialog_progress = (
        lambda message, **_kwargs: progress_messages.append(message) or True
    )
    launcher.post_launch_setup = lambda: ui_updates.append("post_launch_setup")
    launcher.refresh_node_info = lambda: ui_updates.append("refresh_node_info")
    launcher.plot_data = lambda assume_running=False: ui_updates.append(("plot_data", assume_running))
    launcher.update_toggle_button_text = lambda assume_running=False: ui_updates.append(
        ("update_toggle_button_text", assume_running)
    )
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._finalize_launch_success("r1node", "r1vol-new")

    assert progress_messages == [
        "Container launched, updating configuration...",
        "Updating user interface...",
        "Container launched successfully!",
    ]
    assert fake_config.last_used_updates
    assert fake_config.last_used_updates[0][0] == "r1node"
    assert "T" in fake_config.last_used_updates[0][1]
    assert fake_config.volume_updates == [("r1node", "r1vol-new")]
    assert fake_config.containers[0].volume == "r1vol-new"
    assert ui_updates == [
        "post_launch_setup",
        "refresh_node_info",
        ("plot_data", True),
        ("update_toggle_button_text", True),
    ]
    assert launcher.launcher_dialog is None
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.SUCCESS, "Node 'alpha' launched successfully")
    ]


def test_launch_success_clears_dialog_reference_immediately(qtbot, monkeypatch):
    launcher, _fake_config, fake_handler = _build_launcher(monkeypatch, qtbot, running=False)

    def succeed_launch(volume_name=None, callback=None, error_callback=None):
        fake_handler.launched_containers.append((fake_handler.container_name, volume_name))
        callback(("", "", 0))

    fake_handler.launch_container_threaded = succeed_launch
    launcher.launcher_dialog = frm_main.LoadingDialog(
        launcher,
        title="Launching Node",
        message="Please wait",
    )
    launcher._begin_lifecycle_operation("launch", "r1node")

    launcher._perform_container_launch_after_pull("r1node", "r1vol")

    assert fake_handler.launched_containers == [("r1node", "r1vol")]
    assert launcher.launcher_dialog is None
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None
    assert launcher.toast.notifications == [
        (NotificationType.SUCCESS, "Node 'alpha' launched successfully")
    ]


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


def test_launch_skipped_during_existing_pull_closes_launch_dialogs(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.launcher_dialog = frm_main.LoadingDialog(
        launcher,
        title="Launching Node",
        message="Please wait",
    )
    launcher.startup_dialog = frm_main.LoadingDialog(
        launcher,
        title="Starting Node",
        message="Please wait",
    )
    launcher._begin_lifecycle_operation("launch", "r1node")
    launcher._start_docker_pull("r1node2", "r1vol2")
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())

    launcher._perform_container_launch("r1node", "r1vol")

    assert launcher.launcher_dialog is None
    assert launcher.startup_dialog is None
    assert not launcher.loading_indicator.timer.isActive()
    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") is None


def test_launch_container_exception_closes_existing_launch_dialogs(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher.launcher_dialog = frm_main.LoadingDialog(
        launcher,
        title="Launching Node",
        message="Please wait",
    )
    launcher.startup_dialog = frm_main.LoadingDialog(
        launcher,
        title="Starting Node",
        message="Please wait",
    )
    launcher._perform_container_launch = lambda container_name, volume_name: (_ for _ in ()).throw(
        RuntimeError("boom")
    )
    monkeypatch.setattr(frm_main.QTimer, "singleShot", lambda _delay, callback: callback())

    launcher.launch_container("r1vol")

    assert launcher.launcher_dialog is None
    assert launcher.startup_dialog is None
    assert not launcher.loading_indicator.timer.isActive()
    assert launcher.toast.notifications == [
        (NotificationType.ERROR, "Failed to launch container: boom")
    ]


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


def test_add_node_dialog_capacity_copy_is_readable(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    observed = {}

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

    def inspect_dialog(dialog):
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        observed["copy"] = "\n".join(labels)
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", inspect_dialog)

    qtbot.mouseClick(launcher.add_node_button, Qt.LeftButton)

    assert "System Capacity:" in observed["copy"]
    assert "- Total RAM: 32.0 GB" in observed["copy"]
    assert f"- RAM per node: {frm_main.MIN_NODE_RAM_GB} GB" in observed["copy"]
    assert "- Max nodes supported: 4" in observed["copy"]
    assert "- Current nodes: 1" in observed["copy"]
    assert "â" not in observed["copy"]
    assert "Ã" not in observed["copy"]


def test_add_node_dialog_double_click_creates_once(qtbot, monkeypatch):
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

    monkeypatch.setattr(launcher, "_create_node_with_name", record_create)

    def click_create_twice(dialog):
        create_button = dialog.findChild(QPushButton, "createNodeConfirmButton")
        assert create_button is not None
        create_button.click()
        assert not create_button.isEnabled()
        create_button.click()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", click_create_twice)

    qtbot.mouseClick(launcher.add_node_button, Qt.LeftButton)

    assert len(created_nodes) == 1


def test_add_new_node_does_not_override_active_lifecycle(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot, running=False)
    launcher._begin_lifecycle_operation("start", "r1node")

    launcher.add_new_node("r1node2", "r1vol2", "beta")

    assert getattr(launcher, "_EdgeNodeLauncher__active_lifecycle_operation") == {
        "operation": "start",
        "container_name": "r1node",
    }
    assert getattr(launcher, "startup_dialog", None) is None


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
        title_label = container.findChild(QWidget, container_name.replace("Container", "Title"))
        empty_label = plot._r1_empty_label

        assert container.property("class") == "plot-container"
        assert plot.parent() is container
        assert container.layout().count() == 3
        assert container.layout().contentsMargins().left() == 10
        assert title_label is not None
        assert title_label.property("role") == "metricPlotTitle"
        assert empty_label is not None
        assert empty_label.text() == frm_main.METRIC_EMPTY_STATE_TEXT
        assert layout.itemAtPosition(row, column).widget() is container


def test_node_selector_exposes_stable_visual_identity(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    assert launcher.container_combo.objectName() == "nodeSelectorCombo"
    assert launcher.container_combo.accessibleName() == "Node selector"
    assert launcher.container_combo.toolTip() == "Select active node"
    assert launcher.container_combo.minimumHeight() == 36
    assert launcher.container_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert "width: 30px" in launcher.container_combo.styleSheet()


def test_main_window_metric_empty_states_remain_visible_without_history(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    launcher.plot_graphs = REAL_PLOT_GRAPHS.__get__(launcher, frm_main.EdgeNodeLauncher)

    launcher.plot_graphs(history=None)

    for plot_attr in ("cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"):
        plot = getattr(launcher, plot_attr)

        assert plot._r1_empty_label.isVisible()
        assert plot._r1_empty_label.text() == frm_main.METRIC_EMPTY_STATE_TEXT


def test_main_window_log_view_has_stable_identity_and_dimensions(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    dashboard_panel = launcher.findChild(QWidget, "dashboardPanel")
    dashboard_splitter = launcher.findChild(QSplitter, "dashboardSplitter")
    activity_log_panel = launcher.findChild(QWidget, "activityLogPanel")

    assert dashboard_panel is not None
    assert dashboard_splitter is not None
    assert isinstance(activity_log_panel, ActivityLogWidget)
    assert activity_log_panel is launcher.activityLogPanel
    assert launcher.activity_log_header.objectName() == "activityLogHeader"
    assert launcher.activity_log_header.property("role") == "activityLogHeader"
    assert launcher.activity_log_title.objectName() == "activityLogTitle"
    assert launcher.activity_log_title.text() == "Activity Log"
    assert launcher.activity_log_title.property("role") == "dashboardSectionTitle"
    assert launcher.activity_log_title.accessibleName() == "Activity log section"
    assert launcher.activity_log_title.font().family() != "Courier New"
    assert launcher.activity_log_copy_button.objectName() == "activityLogCopyButton"
    assert launcher.activity_log_copy_button.property("role") == "activityLogToolButton"
    assert launcher.activity_log_copy_button.accessibleName() == "Copy activity log"
    assert launcher.activity_log_copy_button.toolTip() == "Copy activity log to clipboard"
    assert launcher.activity_log_clear_button.objectName() == "activityLogClearButton"
    assert launcher.activity_log_clear_button.property("role") == "activityLogToolButton"
    assert launcher.activity_log_clear_button.accessibleName() == "Clear activity log"
    assert launcher.activity_log_clear_button.toolTip() == "Clear activity log"
    assert dashboard_splitter.orientation() == Qt.Vertical
    assert dashboard_splitter.count() == 2
    assert dashboard_panel.layout().indexOf(dashboard_splitter) >= 0
    assert dashboard_splitter.widget(0) is launcher.graphView
    assert dashboard_splitter.widget(1) is launcher.activityLogPanel
    assert not dashboard_splitter.childrenCollapsible()
    assert launcher.logView.objectName() == "logView"
    assert launcher.logView.accessibleName() == "Activity log output"
    assert launcher.findChild(QTextEdit, "logView") is launcher.logView
    assert activity_log_panel.findChild(QTextEdit, "logView") is launcher.logView
    assert activity_log_panel.findChild(QToolButton, "activityLogCopyButton") is launcher.activity_log_copy_button
    assert activity_log_panel.findChild(QToolButton, "activityLogClearButton") is launcher.activity_log_clear_button
    assert activity_log_panel.layout().indexOf(launcher.activity_log_header) >= 0
    assert activity_log_panel.layout().indexOf(launcher.logView) >= 0
    assert activity_log_panel.layout().indexOf(launcher.activity_log_header) < activity_log_panel.layout().indexOf(launcher.logView)
    assert launcher.logView.isReadOnly()
    assert launcher.logView.minimumHeight() == 120
    assert launcher.logView.maximumHeight() > 150
    assert launcher.logView.lineWrapMode() == QTextEdit.NoWrap
    assert launcher.logView.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert launcher.logView.document().maximumBlockCount() == frm_main.MAIN_ACTIVITY_LOG_MAX_BLOCKS
    assert launcher.logView.font().family() == "Courier New"

    launcher.add_log("log view identity smoke", debug=True)

    assert "log view identity smoke" in launcher.logView.toPlainText()

    launcher.add_log("long operational line " + ("x" * 500), debug=True)
    qtbot.wait(20)

    assert launcher.logView.horizontalScrollBar().value() == launcher.logView.horizontalScrollBar().minimum()

    QApplication.clipboard().clear()
    qtbot.mouseClick(launcher.activity_log_copy_button, Qt.LeftButton)

    assert "long operational line" in QApplication.clipboard().text()

    qtbot.mouseClick(launcher.activity_log_clear_button, Qt.LeftButton)

    assert launcher.logView.toPlainText() == ""
    assert not launcher.activity_log_copy_button.isEnabled()
    assert not launcher.activity_log_clear_button.isEnabled()


def test_dashboard_splitter_restores_saved_sizes(qtbot, monkeypatch):
    set_sizes_calls = []
    original_set_sizes = dashboard_panel_module.QSplitter.setSizes

    def record_set_sizes(splitter, sizes):
        if splitter.objectName() == "dashboardSplitter":
            set_sizes_calls.append(list(sizes))
        return original_set_sizes(splitter, sizes)

    monkeypatch.setattr(dashboard_panel_module.QSplitter, "setSizes", record_set_sizes)

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
        assert label.accessibleName() == f"{text} section"
        assert label.property("role") == "sidebarSection"
        assert label.font().family() != "Courier New"
        assert label.minimumHeight() == 30


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


def test_main_window_sidebar_actions_have_hierarchy_roles(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    assert launcher.toggleButton.property("actionRole") == "primary"

    for button in (
        launcher.add_node_button,
        launcher.renameNodeButton,
        launcher.docker_download_button,
        launcher.dapp_button,
        launcher.explorer_button,
        launcher.refreshButton,
    ):
        assert button.property("actionRole") == "secondary"

    assert launcher.themeToggleButton.property("actionRole") == "utility"
    assert "border-radius: 8px;" in launcher.toggleButton.styleSheet()


def test_main_window_sidebar_actions_have_accessible_names(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)

    for button in (
        launcher.add_node_button,
        launcher.renameNodeButton,
        launcher.toggleButton,
        launcher.docker_download_button,
        launcher.dapp_button,
        launcher.explorer_button,
        launcher.refreshButton,
        launcher.themeToggleButton,
    ):
        assert button.accessibleName() == button.text()

    launcher.update_toggle_button_text(assume_running=True)

    assert launcher.toggleButton.accessibleName() == launcher.toggleButton.text()


def test_status_panels_have_semantic_roles(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    info_box = launcher.findChild(QGroupBox, "infoBox")
    resources_box = launcher.findChild(QGroupBox, "resourcesBox")

    assert info_box is not None
    assert resources_box is not None
    assert isinstance(info_box, NodeStatusPanel)
    assert isinstance(resources_box, ResourceStatusPanel)
    assert info_box.property("role") == "statusPanel"
    assert resources_box.property("role") == "resourcePanel"
    assert launcher.node_status_title.objectName() == "nodeStatusCardTitle"
    assert launcher.node_status_title.text() == "Node Details"
    assert launcher.node_status_title.property("role") == "sidebarCardTitle"
    assert launcher.node_status_title.accessibleName() == "Node details card"
    assert launcher.node_status_title.font().family() != "Courier New"
    assert launcher.resource_status_title.objectName() == "resourceStatusCardTitle"
    assert launcher.resource_status_title.text() == "Host Resources"
    assert launcher.resource_status_title.property("role") == "sidebarCardTitle"
    assert launcher.resource_status_title.accessibleName() == "Host resources card"
    assert launcher.resource_status_title.font().family() != "Courier New"
    assert info_box.findChild(QPushButton, "copyAddrButton") is launcher.copyAddrButton
    assert info_box.findChild(QPushButton, "copyEthButton") is launcher.copyEthButton
    assert info_box.findChild(QLabel, "nodeStatusCardTitle") is launcher.node_status_title
    assert resources_box.findChild(QLabel, "resourceStatusCardTitle") is launcher.resource_status_title
    assert resources_box.findChild(QLabel, "memoryResourceDisplay") is launcher.memoryDisplay
    assert resources_box.findChild(QLabel, "cpuResourceDisplay") is launcher.vcpusDisplay
    assert resources_box.findChild(QLabel, "storageResourceDisplay") is launcher.storageDisplay
    assert info_box.layout().spacing() == 3
    assert resources_box.layout().spacing() == 3


def test_main_window_sidebar_settings_follow_resource_panel_without_large_gap(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    launcher.resize(1600, 900)
    qtbot.wait(50)

    resources_box = launcher.findChild(QGroupBox, "resourcesBox")
    settings_label = launcher.findChild(QLabel, "settingsSectionLabel")

    assert resources_box is not None
    assert settings_label is not None

    gap = settings_label.y() - (resources_box.y() + resources_box.height())

    assert 0 <= gap <= 80


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


def test_main_window_sidebar_controls_do_not_overlap_scrollbar(qtbot, monkeypatch):
    launcher, _fake_config, _fake_handler = _build_launcher(monkeypatch, qtbot)
    launcher.setMinimumSize(800, 520)
    launcher.resize(900, 560)
    qtbot.wait(50)

    sidebar_scroll = launcher.findChild(QScrollArea, "sidebarScrollArea")
    assert sidebar_scroll is not None

    viewport = sidebar_scroll.viewport()
    scrollbar = sidebar_scroll.verticalScrollBar()
    viewport_right = viewport.mapToGlobal(viewport.rect().topRight()).x()
    safe_right = viewport_right - 2
    if scrollbar.isVisible():
        safe_right = scrollbar.mapToGlobal(scrollbar.rect().topLeft()).x() - 2

    assert sidebar_scroll.widget().width() <= viewport.width()

    controls = (
        launcher.add_node_button,
        launcher.renameNodeButton,
        launcher.toggleButton,
        launcher.docker_download_button,
        launcher.dapp_button,
        launcher.explorer_button,
        launcher.refreshButton,
        launcher.themeToggleButton,
        launcher.force_debug_checkbox,
    )
    for control in controls:
        if not control.isVisible():
            continue
        control_right = control.mapToGlobal(control.rect().topRight()).x()
        assert control_right <= safe_right, control.objectName()
