from PyQt5.QtCore import Qt

from widgets.HostSelector import HostSelector


class FakeHostsManager:
    def __init__(self, host_names=None):
        self.host_names = host_names or []

    def get_host_names(self):
        return list(self.host_names)

    def get_ssh_command(self, host_name):
        return None

    def get_host(self, host_name):
        return None


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
    assert widget.mode_checkbox.accessibleName() == "Multi-host mode"
    assert widget.mode_checkbox.toolTip() == "Enable multi-host mode"
    assert widget.host_label.objectName() == "hostSelectorHostLabel"
    assert widget.host_label.accessibleName() == "Host selector label"
    assert widget.host_combo.objectName() == "hostSelectorCombo"
    assert widget.host_combo.accessibleName() == "Host selector"
    assert widget.host_combo.toolTip() == "Select a host"
    assert widget.current_status.objectName() == "hostSelectorStatusIndicator"
    assert widget.current_status.accessibleName() == "Host status offline"
    assert widget.current_status.toolTip() == "Host status offline"
    assert widget.refresh_button.objectName() == "hostSelectorRefreshButton"
    assert widget.refresh_button.accessibleName() == "Refresh hosts"
    assert widget.refresh_button.toolTip() == "Refresh hosts"
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
