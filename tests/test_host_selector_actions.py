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
    assert widget.refresh_button.objectName() == "hostSelectorRefreshButton"

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
