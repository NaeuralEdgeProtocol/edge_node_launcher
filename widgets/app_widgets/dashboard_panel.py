from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSplitter, QVBoxLayout, QWidget


class DashboardPanel(QWidget):
    """Right-side dashboard shell that owns metrics/activity splitter layout."""

    def __init__(
        self,
        graph_view: QWidget,
        activity_log_panel: QWidget,
        initial_sizes: list,
        splitter_moved_handler,
        parent=None,
    ):
        super().__init__(parent)
        self.graph_view = graph_view
        self.activity_log_panel = activity_log_panel
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setObjectName("dashboardSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        self.splitter.addWidget(self.graph_view)
        self.splitter.addWidget(self.activity_log_panel)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes(initial_sizes)
        self.splitter.splitterMoved.connect(splitter_moved_handler)

        self.setObjectName("dashboardPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(self.splitter)
