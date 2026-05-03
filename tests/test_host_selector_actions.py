from PyQt5.QtCore import Qt

from widgets.HostSelector import HostSelector


def test_host_selector_mode_and_refresh_actions(qtbot):
    widget = HostSelector()
    qtbot.addWidget(widget)
    widget.show()
    widget.status_timer.stop()

    checked_hosts = []
    widget.hosts_manager.get_host_names = lambda: ["local"]
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
    assert widget.refresh_button.objectName() == "hostSelectorRefreshButton"
    assert widget.refresh_button.accessibleName() == "Refresh hosts"
    assert widget.refresh_button.toolTip() == "Refresh hosts"

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
