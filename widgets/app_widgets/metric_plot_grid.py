from PyQt5 import sip
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QWidget
import pyqtgraph as pg

from app_forms.frm_utils import DateAxisItem


METRIC_PLOT_SPECS = (
    ("cpu_plot", "cpuPlotContainer", 0, 0),
    ("memory_plot", "memoryPlotContainer", 0, 1),
    ("gpu_plot", "gpuPlotContainer", 1, 0),
    ("gpu_memory_plot", "gpuMemoryPlotContainer", 1, 1),
)


class MetricPlotWidget(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ignore_late_paints = False

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


def create_plot_container(object_name: str, plot_widget: QWidget) -> QWidget:
    container = QWidget()
    container.setObjectName(object_name)
    container.setProperty("class", "plot-container")

    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(plot_widget)

    return container


def create_metrics_graph_grid():
    graph_view = QWidget()
    graph_view.setObjectName("metricsGraphGrid")

    graph_layout = QGridLayout()
    graph_layout.setSpacing(10)
    graph_layout.setContentsMargins(0, 0, 0, 0)

    plots = {}
    axis_items = {}
    for plot_attr, container_name, row, column in METRIC_PLOT_SPECS:
        bottom_axis = DateAxisItem(orientation="bottom")
        plot_widget = MetricPlotWidget(axisItems={"bottom": bottom_axis})
        plot_widget._r1_bottom_axis = bottom_axis
        plots[plot_attr] = plot_widget
        axis_items[plot_attr] = bottom_axis
        graph_layout.addWidget(
            create_plot_container(container_name, plot_widget),
            row,
            column,
        )

    graph_view.setLayout(graph_layout)
    return graph_view, plots, axis_items
