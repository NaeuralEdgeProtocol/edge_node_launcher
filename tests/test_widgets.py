from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QDialogButtonBox

from widgets.app_widgets.config_editor import ConfigEditorWidget
from widgets.app_widgets.container_list import ContainerListWidget
from widgets.app_widgets.log_console import LogConsoleWidget
from widgets.app_widgets.metrics_widget import MetricsWidget
from widgets.app_widgets.node_info import NodeInfoWidget


def test_container_list_updates_selection_and_emits_toggle(qtbot):
    widget = ContainerListWidget()
    qtbot.addWidget(widget)

    assert widget.btn_toggle.objectName() == "containerListToggleButton"
    assert widget.btn_add_node.objectName() == "containerListAddNodeButton"

    widget.update_containers(
        [
            {"name": "r1node", "running": False},
            {"name": "r1node2", "running": True},
        ],
        current_container="r1node2",
    )
    widget.update_toggle_button(is_running=True)

    assert widget.get_current_container() == "r1node2"
    assert widget.btn_toggle.text() == "Stop Container"

    with qtbot.waitSignal(widget.container_toggle_requested) as blocker:
        qtbot.mouseClick(widget.btn_toggle, Qt.LeftButton)

    assert blocker.args == ["r1node2"]


def test_container_list_emits_add_container(qtbot):
    widget = ContainerListWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.add_container_requested):
        qtbot.mouseClick(widget.btn_add_node, Qt.LeftButton)


def test_log_console_adds_and_clears_text(qtbot):
    widget = LogConsoleWidget()
    qtbot.addWidget(widget)

    assert widget.btn_clear.objectName() == "logConsoleClearButton"

    widget.add_log("hello", color="green")

    assert "hello" in widget.text_console.toPlainText()

    qtbot.mouseClick(widget.btn_clear, Qt.LeftButton)

    assert widget.text_console.toPlainText() == ""


def test_node_info_widget_baseline_clear_and_uptime_format(qtbot):
    widget = NodeInfoWidget()
    qtbot.addWidget(widget)

    assert widget._format_uptime(65) == "1m 5s"
    assert widget._format_uptime(3661) == "1h 1m 1s"
    assert widget._format_uptime(90061) == "1d 1h 1m"

    widget.clear_info()

    assert widget.lbl_node_address.text() == "N/A"
    assert widget.lbl_eth_address.text() == "N/A"
    assert widget.lbl_node_status.text() == "Unknown"


def test_node_info_widget_action_buttons_emit_signals(qtbot):
    widget = NodeInfoWidget()
    qtbot.addWidget(widget)

    assert widget.btn_copy_address.objectName() == "nodeInfoCopyAddressButton"
    assert widget.btn_copy_eth.objectName() == "nodeInfoCopyEthButton"
    assert widget.btn_refresh.objectName() == "nodeInfoRefreshButton"

    with qtbot.waitSignal(widget.copy_address_requested) as blocker:
        qtbot.mouseClick(widget.btn_copy_address, Qt.LeftButton)
    assert blocker.args == ["node"]

    with qtbot.waitSignal(widget.copy_address_requested) as blocker:
        qtbot.mouseClick(widget.btn_copy_eth, Qt.LeftButton)
    assert blocker.args == ["eth"]

    with qtbot.waitSignal(widget.refresh_requested):
        qtbot.mouseClick(widget.btn_refresh, Qt.LeftButton)


def test_metrics_widget_refresh_button_emits_signal(qtbot):
    widget = MetricsWidget()
    qtbot.addWidget(widget)

    assert widget.btn_refresh.objectName() == "metricsRefreshButton"

    with qtbot.waitSignal(widget.refresh_requested):
        qtbot.mouseClick(widget.btn_refresh, Qt.LeftButton)


def test_config_editor_button_opens_dialog_with_named_actions(qtbot, monkeypatch):
    widget = ConfigEditorWidget()
    qtbot.addWidget(widget)
    opened_dialogs = []

    def capture_exec(dialog):
        opened_dialogs.append(dialog)
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", capture_exec)

    assert widget.btn_edit_config.objectName() == "configEditorEditButton"

    qtbot.mouseClick(widget.btn_edit_config, Qt.LeftButton)

    assert len(opened_dialogs) == 1
    button_box = opened_dialogs[0].findChild(QDialogButtonBox, "configEditorDialogButtons")

    assert button_box is not None
    assert button_box.button(QDialogButtonBox.Ok).objectName() == "configEditorSaveButton"
    assert button_box.button(QDialogButtonBox.Cancel).objectName() == "configEditorCancelButton"
