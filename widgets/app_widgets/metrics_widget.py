from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QSizePolicy
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg
from models.NodeHistory import NodeHistory
from datetime import datetime
from widgets.app_widgets.metric_plot_grid import configure_metric_plot


_METRICS_WIDGET_STYLE_COLORS = {
    False: {
        "surface": "#FFFFFF",
        "border": "#CBD5E1",
        "text": "#1F2937",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
    },
    True: {
        "surface": "#122033",
        "border": "#3E5876",
        "text": "#E8EEF8",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
    },
}

_METRICS_WIDGET_STYLE_TEMPLATE = """
QWidget#metricsWidget {{
    background: transparent;
}}
QGroupBox#metricsGroup {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 12px;
    font-weight: 600;
}}
QGroupBox#metricsGroup::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0px 4px;
}}
QPushButton#metricsRefreshButton {{
    background-color: {primary};
    color: {primary_text};
    border: 1px solid {primary};
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 34px;
    font-weight: 600;
}}
QPushButton#metricsRefreshButton:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}
"""

class MetricsWidget(QWidget):
    """
    Widget for displaying node metrics charts
    """
    # Signals
    refresh_requested = pyqtSignal()  # Emitted when refresh button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("metricsWidget")
        self.setAccessibleName("Node metrics")
        self._is_dark_theme = False
        
        # Initialize UI components
        self.btn_refresh = QPushButton("Refresh Metrics")
        self.btn_refresh.setObjectName("metricsRefreshButton")
        self.btn_refresh.setAccessibleName("Refresh metrics")
        self.btn_refresh.setProperty("actionRole", "primary")
        self.btn_refresh.setToolTip("Refresh metrics")
        self.btn_refresh.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Create plot widgets
        self.plot_cpu = pg.PlotWidget()
        self.plot_cpu.setObjectName("metricsCpuPlot")
        self.plot_cpu.setAccessibleName("CPU usage plot")
        self.plot_memory = pg.PlotWidget()
        self.plot_memory.setObjectName("metricsMemoryPlot")
        self.plot_memory.setAccessibleName("Memory usage plot")
        self.plot_gpu = pg.PlotWidget()
        self.plot_gpu.setObjectName("metricsGpuPlot")
        self.plot_gpu.setAccessibleName("GPU usage plot")
        self.plot_gpu_memory = pg.PlotWidget()
        self.plot_gpu_memory.setObjectName("metricsGpuMemoryPlot")
        self.plot_gpu_memory.setAccessibleName("GPU memory usage plot")
        self.plot_disk = self.plot_gpu
        self.plot_network = self.plot_gpu_memory
        
        # Configure plots
        self._configure_plots()
        self.apply_theme(False)
        
        # Setup UI layout
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
    
    def _configure_plots(self):
        """Configure plot widgets appearance and behavior"""
        for plot in [self.plot_cpu, self.plot_memory, self.plot_gpu, self.plot_gpu_memory]:
            configure_metric_plot(plot)
            plot.setMinimumHeight(170)
            plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set titles and labels
        self.plot_cpu.setTitle("CPU Usage")
        self.plot_memory.setTitle("Memory Usage")
        self.plot_gpu.setTitle("GPU Usage")
        self.plot_gpu_memory.setTitle("GPU Memory Usage")
        
        # Set Y axis ranges
        self.plot_cpu.setYRange(0, 100)
        self.plot_gpu.setYRange(0, 100)
    
    def init_ui(self):
        """Initialize the UI components and layout"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Create metrics group box
        self.metrics_group = QGroupBox("Node Metrics")
        self.metrics_group.setObjectName("metricsGroup")
        self.metrics_group.setAccessibleName("Node metrics")
        self.metrics_group.setProperty("role", "metricsPanel")
        self.metrics_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(12, 16, 12, 12)
        metrics_layout.setSpacing(10)
        
        # Add plot widgets to layout - organize in a grid
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)
        row1_layout.addWidget(self.plot_cpu)
        row1_layout.addWidget(self.plot_memory)
        
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)
        row2_layout.addWidget(self.plot_gpu)
        row2_layout.addWidget(self.plot_gpu_memory)
        
        metrics_layout.addLayout(row1_layout)
        metrics_layout.addLayout(row2_layout)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_refresh)
        metrics_layout.addLayout(button_layout)
        
        # Set metrics group layout
        self.metrics_group.setLayout(metrics_layout)
        layout.addWidget(self.metrics_group)
        
        # Set layout
        self.setLayout(layout)
    
    def connect_signals(self):
        """Connect widget signals to slots"""
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)

    def apply_theme(self, is_dark):
        """Apply compact component styling for standalone or embedded use."""
        self._is_dark_theme = bool(is_dark)
        colors = _METRICS_WIDGET_STYLE_COLORS[self._is_dark_theme]
        self.setStyleSheet(_METRICS_WIDGET_STYLE_TEMPLATE.format(**colors))
    
    def update_metrics(self, history: NodeHistory = None, limit: int = 100):
        """
        Update the displayed metrics charts
        
        Args:
            history: NodeHistory object containing metrics data
            limit: Maximum number of data points to display
        """
        if not history or not history.timestamps or not history.cpu_load or not history.occupied_memory:
            self._clear_plots()
            return
        
        timestamp_offsets = self._timestamp_offsets(history.timestamps[-limit:])
        if not timestamp_offsets:
            self._clear_plots()
            return
        
        # Get data arrays
        expected_count = len(timestamp_offsets)
        cpu_data = self._series_for_plot(history.cpu_load, expected_count)
        memory_data = self._series_for_plot(history.occupied_memory, expected_count)
        gpu_data = self._series_for_plot(history.gpu_load, expected_count)
        gpu_memory_data = self._series_for_plot(history.gpu_occupied_memory, expected_count)
        
        # Clear existing plots
        self._clear_plots()
        
        # Update plots
        self._update_plot(self.plot_cpu, timestamp_offsets, cpu_data, "CPU Load", "blue")
        self._update_plot(self.plot_memory, timestamp_offsets, memory_data, "Occupied Memory", "green")

        if gpu_data:
            self._update_plot(self.plot_gpu, timestamp_offsets, gpu_data, "GPU Load", "red")
        if gpu_memory_data:
            self._update_plot(self.plot_gpu_memory, timestamp_offsets, gpu_memory_data, "Occupied GPU Memory", "magenta")
    
    def _timestamp_offsets(self, timestamps):
        seconds = []
        for index, value in enumerate(timestamps):
            seconds.append(self._timestamp_seconds(value, fallback=index))

        if not seconds:
            return []

        first = seconds[0]
        return [value - first for value in seconds]

    def _timestamp_seconds(self, value, fallback: int) -> float:
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return float(fallback)

        return float(fallback)

    def _series_for_plot(self, data, expected_count: int):
        if not data:
            return []

        values = list(data)[-expected_count:]
        if len(values) < expected_count:
            values = [0] * (expected_count - len(values)) + values
        return values

    def _update_plot(self, plot_widget, x_values, data, name, color):
        """
        Update a single plot with new data
        
        Args:
            plot_widget: PyQtGraph plot widget to update
            x_values: List of timestamp offsets for X axis
            data: List of values for Y axis
            name: Name of the data series
            color: Color to use for the plot line
        """
        if not x_values or not data or len(x_values) != len(data):
            return
        
        # Plot the data
        plot_widget.plot(x_values, data, pen=color, name=name)
    
    def _clear_plots(self):
        """Clear all plot widgets"""
        self.plot_cpu.clear()
        self.plot_memory.clear()
        self.plot_gpu.clear()
        self.plot_gpu_memory.clear()
