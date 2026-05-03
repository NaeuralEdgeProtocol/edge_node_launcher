from PyQt5.QtCore import Qt
from PyQt5.QtGui import QShowEvent
from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QProgressBar, QWidget

from models.NodeHistory import NodeHistory
from models.NodeInfo import NodeInfo
from widgets.DockerPullDialog import DockerPullDialog
from widgets.LoadingDialog import LoadingDialog
from widgets.app_widgets.config_editor import ConfigEditorWidget
from widgets.app_widgets.container_list import ContainerListWidget
from widgets.app_widgets.log_console import LogConsoleWidget
from widgets.app_widgets.metric_plot_grid import METRIC_EMPTY_STATE_TEXT, MetricPlotWidget, create_metrics_graph_grid
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
    assert dialog.title_label.objectName() == "loadingDialogTitleLabel"
    assert dialog.title_label.text() == "Launching Node"
    assert dialog.message_label.objectName() == "loadingDialogMessageLabel"
    assert dialog.loading_indicator.objectName() == "loadingDialogIndicator"


def test_docker_pull_dialog_exposes_stable_visual_targets(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "dockerPullDialog"
    assert dialog.findChild(QLabel, "dockerPullTitleLabel").text() == "Pulling Docker Image"
    assert dialog.findChild(QLabel, "dockerPullInfoLabel") is dialog.info_label
    assert dialog.findChild(QProgressBar, "dockerPullOverallProgress") is dialog.overall_progress
    assert dialog.findChild(QWidget, "dockerPullLayerFrame") is not None
    assert dialog.findChild(QWidget, "dockerPullLayerScrollArea") is not None
    assert dialog.findChild(QWidget, "dockerPullLayerScrollContent") is not None
    assert dialog.findChild(QLabel, "dockerPullLayerEmptyState").text() == "Waiting for Docker layer output..."


def test_docker_pull_dialog_updates_layer_progress_with_named_children(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)

    dialog.update_pull_progress("abcdef123456: Downloading 50%")

    assert not dialog.empty_layer_label.isVisible()
    assert dialog.overall_progress.value() == 50
    assert dialog.findChild(QLabel, "dockerPullLayerLabel_abcdef123456").text() == "abcdef12..."
    assert dialog.findChild(QLabel, "dockerPullLayerStatus_abcdef123456").text() == "Downloading 50%"
    assert dialog.findChild(QProgressBar, "dockerPullLayerProgress_abcdef123456").value() == 50


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
    assert widget.lbl_eth_address.text() == "0xeth"
    assert widget.lbl_node_name.text() == "edge-one"
    assert widget.lbl_node_status.text() == "Available"
    assert widget.lbl_uptime.text() == "N/A"


def test_metrics_widget_refresh_button_emits_signal(qtbot):
    widget = MetricsWidget()
    qtbot.addWidget(widget)

    assert widget.btn_refresh.objectName() == "metricsRefreshButton"

    with qtbot.waitSignal(widget.refresh_requested):
        qtbot.mouseClick(widget.btn_refresh, Qt.LeftButton)


def test_metric_plot_grid_builder_preserves_dashboard_contract(qtbot):
    graph_view, plots, axis_items = create_metrics_graph_grid()
    qtbot.addWidget(graph_view)
    layout = graph_view.layout()

    assert graph_view.objectName() == "metricsGraphGrid"
    assert layout.count() == 4
    assert layout.spacing() == 10
    assert set(plots) == {"cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"}
    assert set(axis_items) == set(plots)

    expected = {
        "cpuPlotContainer": ("cpu_plot", "cpuPlotTitle", "cpuPlotEmptyState", 0, 0),
        "memoryPlotContainer": ("memory_plot", "memoryPlotTitle", "memoryPlotEmptyState", 0, 1),
        "gpuPlotContainer": ("gpu_plot", "gpuPlotTitle", "gpuPlotEmptyState", 1, 0),
        "gpuMemoryPlotContainer": (
            "gpu_memory_plot",
            "gpuMemoryPlotTitle",
            "gpuMemoryPlotEmptyState",
            1,
            1,
        ),
    }
    for container_name, (plot_attr, title_name, empty_name, row, column) in expected.items():
        container = graph_view.findChild(QWidget, container_name)
        plot = plots[plot_attr]

        assert container is not None
        title_label = container.findChild(QWidget, title_name)
        empty_label = container.findChild(QWidget, empty_name)

        assert container.property("class") == "plot-container"
        assert isinstance(plot, MetricPlotWidget)
        assert plot.parent() is container
        assert plot._r1_bottom_axis is axis_items[plot_attr]
        assert plot.getAxis("bottom") is axis_items[plot_attr]
        assert title_label is not None
        assert title_label.property("role") == "metricPlotTitle"
        assert empty_label is plot._r1_empty_label
        assert empty_label.property("role") == "metricPlotEmptyState"
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

    qtbot.mouseClick(widget.btn_edit_config, Qt.LeftButton)

    assert len(opened_dialogs) == 1
    button_box = opened_dialogs[0].findChild(QDialogButtonBox, "configEditorDialogButtons")

    assert button_box is not None
    assert button_box.button(QDialogButtonBox.Ok).objectName() == "configEditorSaveButton"
    assert button_box.button(QDialogButtonBox.Cancel).objectName() == "configEditorCancelButton"
