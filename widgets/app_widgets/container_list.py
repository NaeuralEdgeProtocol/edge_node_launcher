from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal


CONTAINER_LIST_EMPTY_TEXT = "No containers available"

_CONTAINER_LIST_STYLE_COLORS = {
    False: {
        "surface": "#FFFFFF",
        "surface_hover": "#F8FAFC",
        "surface_disabled": "#F1F5F9",
        "border": "#CBD5E1",
        "border_hover": "#1B47F7",
        "text": "#1F2937",
        "muted": "#64748B",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
        "stop": "#FADC33",
        "stop_hover": "#FFE138",
        "stop_text": "#1F2937",
        "secondary": "#F7F9FC",
        "secondary_hover": "#EEF4FF",
        "secondary_text": "#1F2937",
    },
    True: {
        "surface": "#122033",
        "surface_hover": "#172A42",
        "surface_disabled": "#182233",
        "border": "#3E5876",
        "border_hover": "#7DA2D6",
        "text": "#E8EEF8",
        "muted": "#93A4B8",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
        "stop": "#FADC33",
        "stop_hover": "#FFE138",
        "stop_text": "#1F2937",
        "secondary": "#243447",
        "secondary_hover": "#2E465E",
        "secondary_text": "#E8EEF8",
    },
}

_CONTAINER_LIST_STYLE_TEMPLATE = """
QWidget#containerListWidget {{
    background: transparent;
}}
QComboBox#containerListCombo {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 32px 6px 12px;
    min-height: 34px;
    font-family: "Segoe UI";
    font-size: 10pt;
}}
QComboBox#containerListCombo:hover,
QComboBox#containerListCombo:focus {{
    background-color: {surface_hover};
    border-color: {border_hover};
}}
QComboBox#containerListCombo:disabled {{
    background-color: {surface_disabled};
    color: {muted};
    border-color: {border};
}}
QComboBox#containerListCombo QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {primary};
    selection-color: {primary_text};
}}
QComboBox#containerListCombo QAbstractItemView::item {{
    min-height: 26px;
    padding: 4px 8px;
}}
QPushButton#containerListToggleButton,
QPushButton#containerListAddNodeButton {{
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 34px;
    font-family: "Segoe UI";
    font-size: 10pt;
    font-weight: 600;
}}
QPushButton#containerListToggleButton[state="stopped"] {{
    background-color: {primary};
    color: {primary_text};
    border: 1px solid {primary};
}}
QPushButton#containerListToggleButton[state="stopped"]:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}
QPushButton#containerListToggleButton[state="running"] {{
    background-color: {stop};
    color: {stop_text};
    border: 1px solid {stop};
}}
QPushButton#containerListToggleButton[state="running"]:hover {{
    background-color: {stop_hover};
    border-color: {stop_hover};
}}
QPushButton#containerListToggleButton:disabled {{
    background-color: {surface_disabled};
    color: {muted};
    border: 1px solid {border};
}}
QPushButton#containerListAddNodeButton {{
    background-color: {secondary};
    color: {secondary_text};
    border: 1px solid {border};
}}
QPushButton#containerListAddNodeButton:hover {{
    background-color: {secondary_hover};
    border-color: {border_hover};
}}
"""


def _repolish(widget):
    """Refresh Qt stylesheet selectors after dynamic properties change."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ContainerListWidget(QWidget):
    """
    Widget for displaying and selecting Docker containers
    """
    # Signals
    container_selected = pyqtSignal(str)  # Emitted when a container is selected (container_name)
    container_toggle_requested = pyqtSignal(str)  # Emitted when a container start/stop is requested
    add_container_requested = pyqtSignal()  # Emitted when add container button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("containerListWidget")
        self.setAccessibleName("Container list")
        self._is_dark_theme = False
        
        # Initialize UI components
        self.containers_combo = QComboBox()
        self.containers_combo.setObjectName("containerListCombo")
        self.containers_combo.setAccessibleName("Container selector")
        self.containers_combo.setToolTip("Select a node container")
        self.containers_combo.setInsertPolicy(QComboBox.NoInsert)
        self.containers_combo.setMaxVisibleItems(8)
        self.containers_combo.setMinimumHeight(36)
        self.containers_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_toggle = QPushButton("Start Container")
        self.btn_toggle.setObjectName("containerListToggleButton")
        self.btn_toggle.setProperty("actionRole", "primary")
        self.btn_toggle.setMinimumHeight(36)
        self.btn_toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_toggle.setToolTip("Start selected container")

        self.btn_add_node = QPushButton("Add Node")
        self.btn_add_node.setObjectName("containerListAddNodeButton")
        self.btn_add_node.setAccessibleName("Add node")
        self.btn_add_node.setProperty("actionRole", "secondary")
        self.btn_add_node.setMinimumHeight(36)
        self.btn_add_node.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_add_node.setToolTip("Add a node container")
        self.update_toggle_button(is_running=False)
        self._set_controls_available(False)
        self.apply_theme(False)
        self.update_containers([])
        
        # Setup UI layout
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
    
    def init_ui(self):
        """Initialize the UI components and layout"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Combo box for container selection
        combo_layout = QHBoxLayout()
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.setSpacing(0)
        combo_layout.addWidget(self.containers_combo)
        layout.addLayout(combo_layout)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addWidget(self.btn_toggle)
        button_layout.addWidget(self.btn_add_node)
        layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(layout)
    
    def connect_signals(self):
        """Connect widget signals to slots"""
        self.containers_combo.currentIndexChanged.connect(self._on_container_selected)
        self.btn_toggle.clicked.connect(self._on_toggle_clicked)
        self.btn_add_node.clicked.connect(self._on_add_node_clicked)

    def apply_theme(self, is_dark):
        """Apply compact component styling for standalone or embedded use."""
        self._is_dark_theme = bool(is_dark)
        colors = _CONTAINER_LIST_STYLE_COLORS[self._is_dark_theme]
        self.setStyleSheet(_CONTAINER_LIST_STYLE_TEMPLATE.format(**colors))

    def _on_container_selected(self, index):
        """Handle container selection from combo box"""
        if index >= 0:
            container_name = self.containers_combo.itemData(index)
            if container_name:
                self.container_selected.emit(container_name)
    
    def _on_toggle_clicked(self):
        """Handle container toggle button click"""
        index = self.containers_combo.currentIndex()
        if index >= 0:
            container_name = self.containers_combo.itemData(index)
            if container_name:
                self.container_toggle_requested.emit(container_name)
    
    def _on_add_node_clicked(self):
        """Handle add node button click"""
        self.add_container_requested.emit()
    
    def update_containers(self, containers, current_container=None):
        """
        Update the containers combo box with the provided containers
        
        Args:
            containers: List of container dictionaries with 'name', 'running', etc.
            current_container: Name of the currently selected container
        """
        # Save current container name
        current_name = current_container or (
            self.containers_combo.itemData(self.containers_combo.currentIndex()) 
            if self.containers_combo.currentIndex() >= 0 else None
        )
        
        # Clear combo box
        self.containers_combo.clear()
        self._set_controls_available(bool(containers))

        if not containers:
            self.containers_combo.addItem(CONTAINER_LIST_EMPTY_TEXT, None)
            self.containers_combo.setCurrentIndex(0)
            return
        
        # Add containers to combo box
        select_index = 0
        for i, container in enumerate(containers):
            name = container.get("name", "")
            self.containers_combo.addItem(f"{name} ({'Running' if container.get('running', False) else 'Stopped'})", name)
            
            # If this is the current container, set as selected
            if name == current_name:
                select_index = i
        
        # Set current index
        if containers:
            self.containers_combo.setCurrentIndex(select_index)
    
    def update_toggle_button(self, is_running):
        """
        Update the toggle button text based on container state
        
        Args:
            is_running: Whether the container is running
        """
        if is_running:
            self.btn_toggle.setText("Stop Container")
            self.btn_toggle.setAccessibleName("Stop selected container")
            self.btn_toggle.setToolTip("Stop selected container")
            self.btn_toggle.setProperty("state", "running")
        else:
            self.btn_toggle.setText("Start Container")
            self.btn_toggle.setAccessibleName("Start selected container")
            self.btn_toggle.setToolTip("Start selected container")
            self.btn_toggle.setProperty("state", "stopped")
        _repolish(self.btn_toggle)

    def _set_controls_available(self, has_containers):
        """Keep controls honest when there is no selectable container."""
        self.containers_combo.setEnabled(has_containers)
        self.btn_toggle.setEnabled(has_containers)
        if has_containers:
            self.containers_combo.setToolTip("Select a node container")
            self.btn_toggle.setToolTip(
                "Stop selected container"
                if self.btn_toggle.property("state") == "running"
                else "Start selected container"
            )
        else:
            self.containers_combo.setToolTip("No node containers are available")
            self.btn_toggle.setToolTip("Add a node before starting or stopping a container")
        _repolish(self.containers_combo)
        _repolish(self.btn_toggle)
    
    def get_current_container(self):
        """
        Get the currently selected container name
        
        Returns:
            str: Current container name or None
        """
        index = self.containers_combo.currentIndex()
        if index >= 0:
            return self.containers_combo.itemData(index)
        return None
