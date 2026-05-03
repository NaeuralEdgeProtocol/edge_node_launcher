from PyQt5 import sip
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget
import pyqtgraph as pg

from app_forms.frm_utils import DateAxisItem
from utils.const import CPU_LOAD_TITLE, GPU_LOAD_TITLE, GPU_MEMORY_LOAD_TITLE, MEMORY_USAGE_TITLE


METRIC_PLOT_SPECS = (
    ("cpu_plot", "cpuPlotContainer", "cpuPlotTitle", "cpuPlotEmptyState", "cpuMetricPlot", CPU_LOAD_TITLE, 0, 0),
    (
        "memory_plot",
        "memoryPlotContainer",
        "memoryPlotTitle",
        "memoryPlotEmptyState",
        "memoryMetricPlot",
        MEMORY_USAGE_TITLE,
        0,
        1,
    ),
    ("gpu_plot", "gpuPlotContainer", "gpuPlotTitle", "gpuPlotEmptyState", "gpuMetricPlot", GPU_LOAD_TITLE, 1, 0),
    (
        "gpu_memory_plot",
        "gpuMemoryPlotContainer",
        "gpuMemoryPlotTitle",
        "gpuMemoryPlotEmptyState",
        "gpuMemoryMetricPlot",
        GPU_MEMORY_LOAD_TITLE,
        1,
        1,
    ),
)
METRIC_EMPTY_STATE_TEXT = "No metric history yet"


class MetricPlotWidget(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ignore_late_paints = False
        self._r1_empty_label = None

    def set_empty_state(self, message: str = METRIC_EMPTY_STATE_TEXT) -> None:
        if self._r1_empty_label is None:
            return
        self._r1_empty_label.setText(message)
        self._r1_empty_label.show()

    def clear_empty_state(self) -> None:
        if self._r1_empty_label is not None:
            self._r1_empty_label.hide()

    def disable_late_paints(self) -> None:
        self._ignore_late_paints = True
        self.setUpdatesEnabled(False)
        viewport = self.viewport() if hasattr(self, "viewport") else None
        if viewport is not None and not sip.isdeleted(viewport):
            viewport.setUpdatesEnabled(False)
            viewport.hide()
        self.hide()

    def paintEvent(self, event):
        if self._ignore_late_paints or not self.updatesEnabled() or not self.isVisible():
            if hasattr(event, "accept"):
                event.accept()
            return

        return super().paintEvent(event)


def create_plot_container(
    object_name: str,
    title_object_name: str,
    empty_object_name: str,
    plot_object_name: str,
    title: str,
    plot_widget: MetricPlotWidget,
) -> QWidget:
    container = QWidget()
    container.setObjectName(object_name)
    container.setAccessibleName(title)
    container.setProperty("class", "plot-container")

    title_label = QLabel(title)
    title_label.setObjectName(title_object_name)
    title_label.setAccessibleName(f"{title} title")
    title_label.setProperty("role", "metricPlotTitle")
    title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    empty_label = QLabel(METRIC_EMPTY_STATE_TEXT)
    empty_label.setObjectName(empty_object_name)
    empty_label.setAccessibleName(f"{title} empty state")
    empty_label.setProperty("role", "metricPlotEmptyState")
    empty_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    empty_label.setWordWrap(True)
    plot_widget.setObjectName(plot_object_name)
    plot_widget.setAccessibleName(f"{title} plot")
    plot_widget._r1_empty_label = empty_label

    layout = QVBoxLayout(container)
    layout.setContentsMargins(10, 8, 10, 10)
    layout.setSpacing(4)
    layout.addWidget(title_label)
    layout.addWidget(empty_label)
    layout.addWidget(plot_widget)

    return container


def create_metrics_graph_grid():
    graph_view = QWidget()
    graph_view.setObjectName("metricsGraphGrid")
    graph_view.setAccessibleName("Metrics graph grid")

    graph_layout = QGridLayout()
    graph_layout.setSpacing(10)
    graph_layout.setContentsMargins(0, 0, 0, 0)

    plots = {}
    axis_items = {}
    for plot_attr, container_name, title_name, empty_name, plot_name, title, row, column in METRIC_PLOT_SPECS:
        bottom_axis = DateAxisItem(orientation="bottom")
        plot_widget = MetricPlotWidget(axisItems={"bottom": bottom_axis})
        plot_widget._r1_bottom_axis = bottom_axis
        plots[plot_attr] = plot_widget
        axis_items[plot_attr] = bottom_axis
        graph_layout.addWidget(
            create_plot_container(container_name, title_name, empty_name, plot_name, title, plot_widget),
            row,
            column,
        )

    graph_view.setLayout(graph_layout)
    return graph_view, plots, axis_items
