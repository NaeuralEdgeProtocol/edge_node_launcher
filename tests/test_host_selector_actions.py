from pathlib import Path

from PyQt5.QtCore import Qt

import widgets.HostSelector as host_selector_module
from widgets.HostSelector import HostSelector, SSHCheckThread, SSH_STATUS_TIMEOUT_SECONDS


class FakeHostsManager:
    def __init__(self, host_names=None):
        self.host_names = host_names or []

    def get_host_names(self):
        return list(self.host_names)

    def get_ssh_command(self, host_name):
        return None

    def get_host(self, host_name):
        return None


class FakeConfiguredHostsManager(FakeHostsManager):
    def get_ssh_command(self, host_name):
        return f"ssh {host_name}"

    def get_host(self, host_name):
        return object()


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class FakeStatusThread:
    def __init__(self, host, ssh_command):
        self.host = host
        self.ssh_command = ssh_command
        self.status_updated = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.running = True
        self.interrupted = False
        self.terminated = False
        self.deleted = False

    def start(self):
        self.started = True

    def isRunning(self):
        return self.running

    def requestInterruption(self):
        self.interrupted = True

    def terminate(self):
        self.terminated = True

    def wait(self, _timeout):
        return True

    def deleteLater(self):
        self.deleted = True


def test_host_selector_mode_and_refresh_actions(qtbot):
    widget = HostSelector(
        hosts_manager=FakeHostsManager(["local"]),
        auto_refresh=False,
        status_interval_ms=0,
    )
    qtbot.addWidget(widget)
    widget.show()

    checked_hosts = []
    widget.check_host_status = checked_hosts.append

    assert widget.mode_checkbox.objectName() == "hostSelectorModeCheckbox"
    assert widget.objectName() == "hostSelectorWidget"
    assert widget.accessibleName() == "Host selector"
    assert widget.layout().contentsMargins().left() == 0
    assert widget.layout().spacing() == 8
    assert widget.mode_checkbox.text() == "Multi-host mode"
    assert widget.mode_checkbox.accessibleName() == "Multi-host mode"
    assert widget.mode_checkbox.toolTip() == "Enable multi-host mode"
    assert widget.mode_checkbox.font().family() != "Courier New"
    assert widget.host_label.objectName() == "hostSelectorHostLabel"
    assert widget.host_label.text() == "Host"
    assert widget.host_label.accessibleName() == "Host selector label"
    assert widget.host_label.font().family() != "Courier New"
    assert widget.host_combo.objectName() == "hostSelectorCombo"
    assert widget.host_combo.accessibleName() == "Host selector"
    assert widget.host_combo.toolTip() == "Select a host"
    assert widget.host_combo.minimumWidth() == 180
    assert widget.host_combo.font().family() != "Courier New"
    assert widget.current_status.objectName() == "hostSelectorStatusIndicator"
    assert widget.current_status.accessibleName() == "Host status offline"
    assert widget.current_status.toolTip() == "Host status offline"
    assert widget.current_status.width() == 10
    assert widget.current_status.height() == 10
    assert widget.refresh_button.objectName() == "hostSelectorRefreshButton"
    assert widget.refresh_button.accessibleName() == "Refresh hosts"
    assert widget.refresh_button.toolTip() == "Refresh hosts"
    assert widget.refresh_button.font().family() != "Courier New"
    assert not widget.status_timer.isActive()

    with qtbot.waitSignal(widget.mode_changed) as blocker:
        qtbot.mouseClick(widget.mode_checkbox, Qt.LeftButton)

    assert blocker.args == [True]
    assert widget.host_label.isVisible()
    assert widget.host_combo.isVisible()
    assert widget.refresh_button.isVisible()

    qtbot.mouseClick(widget.refresh_button, Qt.LeftButton)

    assert widget.host_combo.count() == 1
    assert widget.host_combo.currentText() == "local"
    assert "local" in checked_hosts


def test_host_selector_can_defer_initial_refresh_without_constructor_io(qtbot, capsys):
    widget = HostSelector(
        hosts_manager=FakeHostsManager(["local", "devnet"]),
        auto_refresh=False,
        status_interval_ms=0,
    )
    qtbot.addWidget(widget)

    assert widget.host_combo.count() == 0
    assert not widget.status_timer.isActive()
    assert capsys.readouterr().out == ""

    widget.refresh_hosts()

    assert widget.host_combo.count() == 2
    assert widget.host_combo.itemText(0) == "local"
    assert widget.host_combo.itemText(1) == "devnet"
    assert capsys.readouterr().out == ""


def test_host_selector_requests_interruption_instead_of_terminating_status_thread(qtbot, monkeypatch):
    created_threads = []

    def create_status_thread(host_name, ssh_command):
        thread = FakeStatusThread(host_name, ssh_command)
        created_threads.append(thread)
        return thread

    monkeypatch.setattr(host_selector_module, "SSHCheckThread", create_status_thread)
    widget = HostSelector(
        hosts_manager=FakeConfiguredHostsManager(["local", "devnet"]),
        auto_refresh=False,
        status_interval_ms=0,
    )
    qtbot.addWidget(widget)
    widget._is_pro_mode = True
    previous_thread = FakeStatusThread("local", ["ssh", "local"])
    widget.status_thread = previous_thread

    widget.check_host_status("devnet")

    assert previous_thread.interrupted
    assert not previous_thread.terminated
    assert len(created_threads) == 1
    assert created_threads[0].host == "devnet"
    assert created_threads[0].ssh_command == ["ssh", "devnet"]
    assert created_threads[0].started
    assert widget.status_threads["devnet"] is created_threads[0]

    created_threads[0].running = False
    created_threads[0].finished.emit()

    assert "devnet" not in widget.status_threads
    assert widget.status_thread is None
    assert created_threads[0].deleted


def test_host_selector_does_not_start_duplicate_status_thread(qtbot, monkeypatch):
    def fail_create_status_thread(*_args):
        raise AssertionError("duplicate status check should reuse the running thread")

    monkeypatch.setattr(host_selector_module, "SSHCheckThread", fail_create_status_thread)
    widget = HostSelector(
        hosts_manager=FakeConfiguredHostsManager(["local"]),
        auto_refresh=False,
        status_interval_ms=0,
    )
    qtbot.addWidget(widget)
    widget._is_pro_mode = True
    running_thread = FakeStatusThread("local", ["ssh", "local"])
    widget.status_thread = running_thread
    widget.status_threads["local"] = running_thread

    widget.check_host_status("local")

    assert not running_thread.interrupted
    assert widget.status_thread is running_thread
    assert widget.status_threads["local"] is running_thread


def test_host_selector_close_requests_status_thread_interruption(qtbot):
    widget = HostSelector(
        hosts_manager=FakeConfiguredHostsManager(["local"]),
        auto_refresh=False,
        status_interval_ms=1000,
    )
    qtbot.addWidget(widget)
    running_thread = FakeStatusThread("local", ["ssh", "local"])
    widget.status_thread = running_thread
    widget.status_threads["local"] = running_thread
    assert widget.status_timer.isActive()

    widget.close()

    assert running_thread.interrupted
    assert not running_thread.terminated
    assert not widget.status_timer.isActive()


def test_ssh_check_thread_uses_timeout_and_emits_success(qtbot, monkeypatch):
    calls = []

    class SuccessfulResult:
        returncode = 0
        stdout = "Connection successful\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SuccessfulResult()

    monkeypatch.setattr(host_selector_module.subprocess, "run", fake_run)
    thread = SSHCheckThread("local", ["ssh", "local"])
    results = []
    thread.status_updated.connect(lambda host, online: results.append((host, online)))

    thread.run()

    assert calls
    assert calls[0][1]["timeout"] == SSH_STATUS_TIMEOUT_SECONDS
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True
    assert results == [("local", True)]


def test_host_selector_source_does_not_terminate_threads():
    assert ".terminate(" not in Path(host_selector_module.__file__).read_text(encoding="utf-8")
