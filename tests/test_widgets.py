from PyQt5.QtCore import Qt
from PyQt5.QtGui import QShowEvent
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from models.NodeHistory import NodeHistory
from models.NodeInfo import NodeInfo
from widgets.DockerPullDialog import DockerPullDialog
from widgets.LoadingDialog import LoadingDialog
from widgets.CenteredComboBox import CenteredComboBox
from widgets.app_widgets.config_editor import ConfigEditorWidget
from widgets.app_widgets.container_list import CONTAINER_LIST_EMPTY_TEXT, ContainerListWidget
from widgets.app_widgets.log_console import MAX_LOG_LINES, LogConsoleWidget
from widgets.app_widgets.metric_plot_grid import (
    METRIC_AXIS_COLOR,
    METRIC_EMPTY_STATE_TEXT,
    METRIC_GRID_ALPHA,
    MetricPlotWidget,
    create_metrics_graph_grid,
)
from widgets.app_widgets.metrics_widget import MetricsWidget
from widgets.app_widgets.node_info import NodeInfoWidget


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


def test_centered_combo_light_popup_uses_supported_qt_stylesheet(qtbot):
    combo = CenteredComboBox()
    qtbot.addWidget(combo)
    combo.set_theme(False)
    combo.addItem("alpha", "r1node")

    combo.showPopup()
    qtbot.wait(50)
    try:
        stylesheet = combo.view().styleSheet()
        assert "QListView" in stylesheet
        assert "box-shadow" not in stylesheet
    finally:
        combo.hidePopup()


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


def test_docker_pull_dialog_exposes_stable_visual_targets(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "dockerPullDialog"
    assert dialog.accessibleName() == "Pulling Docker Image"
    assert dialog.findChild(QLabel, "dockerPullTitleLabel").text() == "Pulling Docker Image"
    assert dialog.findChild(QLabel, "dockerPullTitleLabel").accessibleName() == "Docker pull title"
    assert dialog.findChild(QLabel, "dockerPullInfoLabel") is dialog.info_label
    assert dialog.info_label.accessibleName() == "Docker pull status"
    assert dialog.findChild(QProgressBar, "dockerPullOverallProgress") is dialog.overall_progress
    assert dialog.overall_progress.accessibleName() == "Docker pull overall progress"
    assert dialog.findChild(QWidget, "dockerPullLayerFrame") is not None
    assert dialog.findChild(QWidget, "dockerPullLayerScrollArea") is not None
    assert dialog.findChild(QWidget, "dockerPullLayerScrollContent") is not None
    assert dialog.findChild(QWidget, "dockerPullLayerFrame").accessibleName() == "Docker pull layer progress"
    assert dialog.findChild(QWidget, "dockerPullLayerScrollArea").accessibleName() == "Docker pull layer list"
    assert dialog.findChild(QWidget, "dockerPullLayerScrollContent").accessibleName() == "Docker pull layer list content"
    assert dialog.findChild(QLabel, "dockerPullLayerHeaderLabel").accessibleName() == "Layer progress heading"
    assert dialog.findChild(QLabel, "dockerPullLayerEmptyState").text() == "Waiting for Docker layer output..."
    assert dialog.findChild(QLabel, "dockerPullLayerEmptyState").accessibleName() == "Docker pull waiting state"


def test_docker_pull_dialog_updates_layer_progress_with_named_children(qtbot):
    dialog = DockerPullDialog()
    qtbot.addWidget(dialog)

    dialog.update_pull_progress("abcdef123456: Downloading 50%")

    assert not dialog.empty_layer_label.isVisible()
    assert dialog.overall_progress.value() == 50
    assert dialog.findChild(QLabel, "dockerPullLayerLabel_abcdef123456").text() == "abcdef12..."
    assert dialog.findChild(QLabel, "dockerPullLayerLabel_abcdef123456").accessibleName() == "Docker layer abcdef12"
    assert dialog.findChild(QLabel, "dockerPullLayerStatus_abcdef123456").text() == "Downloading 50%"
    assert dialog.findChild(QLabel, "dockerPullLayerStatus_abcdef123456").accessibleName() == "Docker layer abcdef12 status"
    assert dialog.findChild(QProgressBar, "dockerPullLayerProgress_abcdef123456").value() == 50
    assert dialog.findChild(QProgressBar, "dockerPullLayerProgress_abcdef123456").accessibleName() == "Docker layer abcdef12 progress"


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
        assert plot._r1_bottom_axis is axis_items[plot_attr]
        assert plot.getAxis("bottom") is axis_items[plot_attr]
        assert title_label is not None
        assert title_label.accessibleName() == f"{title_label.text()} title"
        assert title_label.property("role") == "metricPlotTitle"
        assert empty_label is plot._r1_empty_label
        assert empty_label.accessibleName() == f"{title_label.text()} empty state"
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
    assert widget.objectName() == "configEditorWidget"
    assert widget.accessibleName() == "Configuration editor"
    assert widget.btn_edit_config.accessibleName() == "Edit configuration"
    assert widget.btn_edit_config.toolTip() == "Edit configuration"

    qtbot.mouseClick(widget.btn_edit_config, Qt.LeftButton)

    assert len(opened_dialogs) == 1
    dialog = opened_dialogs[0]
    button_box = dialog.findChild(QDialogButtonBox, "configEditorDialogButtons")

    assert dialog.objectName() == "configEditorDialog"
    assert dialog.accessibleName() == "Edit Configuration Files"
    assert dialog.findChild(QTabWidget, "configEditorTabs").accessibleName() == "Configuration tabs"
    assert dialog.findChild(QWidget, "startupConfigTab").accessibleName() == "Startup configuration tab"
    assert dialog.findChild(QWidget, "appConfigTab").accessibleName() == "App configuration tab"
    assert dialog.findChild(QLabel, "startupConfigLabel").accessibleName() == "Startup configuration label"
    assert dialog.findChild(QLabel, "appConfigLabel").accessibleName() == "App configuration label"
    assert dialog.findChild(QTextEdit, "startupConfigText").accessibleName() == "Startup configuration text"
    assert dialog.findChild(QTextEdit, "appConfigText").accessibleName() == "App configuration text"
    assert button_box is not None
    assert button_box.accessibleName() == "Configuration editor actions"
    assert button_box.button(QDialogButtonBox.Ok).objectName() == "configEditorSaveButton"
    assert button_box.button(QDialogButtonBox.Ok).accessibleName() == "Save configuration"
    assert button_box.button(QDialogButtonBox.Ok).toolTip() == "Save configuration"
    assert button_box.button(QDialogButtonBox.Cancel).objectName() == "configEditorCancelButton"
    assert button_box.button(QDialogButtonBox.Cancel).accessibleName() == "Cancel configuration editing"
    assert button_box.button(QDialogButtonBox.Cancel).toolTip() == "Cancel configuration editing"
