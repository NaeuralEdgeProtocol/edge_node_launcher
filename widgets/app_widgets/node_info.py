from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QGridLayout, QGroupBox, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt
from models.NodeInfo import NodeInfo


_NODE_INFO_STYLE_COLORS = {
    False: {
        "surface": "#FFFFFF",
        "border": "#CBD5E1",
        "text": "#1F2937",
        "muted": "#64748B",
        "value_bg": "#F8FAFC",
        "secondary": "#F7F9FC",
        "secondary_hover": "#EEF4FF",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
        "available_bg": "#DCFCE7",
        "available_text": "#166534",
        "unknown_bg": "#F1F5F9",
        "unknown_text": "#475569",
    },
    True: {
        "surface": "#122033",
        "border": "#3E5876",
        "text": "#E8EEF8",
        "muted": "#93A4B8",
        "value_bg": "#172A42",
        "secondary": "#243447",
        "secondary_hover": "#2E465E",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
        "available_bg": "#163B2D",
        "available_text": "#86EFAC",
        "unknown_bg": "#182233",
        "unknown_text": "#C7D4E8",
    },
}

_NODE_INFO_STYLE_TEMPLATE = """
QWidget#nodeInfoWidget {{
    background: transparent;
}}
QGroupBox#nodeInfoGroup {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 12px;
    font-weight: 600;
}}
QGroupBox#nodeInfoGroup::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0px 4px;
}}
QLabel[role="nodeInfoFieldLabel"] {{
    color: {muted};
    font-size: 10pt;
    font-weight: 600;
    background: transparent;
}}
QLabel[role="nodeInfoValue"] {{
    color: {text};
    background: transparent;
    font-size: 10pt;
    padding: 2px 0px;
}}
QLabel[role="nodeInfoAddress"] {{
    color: {text};
    background-color: {value_bg};
    border: 1px solid {border};
    border-radius: 6px;
    font-family: "Courier New";
    font-size: 9pt;
    padding: 5px 7px;
}}
QLabel#nodeInfoStatusValue[status="available"] {{
    color: {available_text};
    background-color: {available_bg};
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 600;
}}
QLabel#nodeInfoStatusValue[status="unknown"] {{
    color: {unknown_text};
    background-color: {unknown_bg};
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 600;
}}
QPushButton#nodeInfoCopyAddressButton,
QPushButton#nodeInfoCopyEthButton {{
    background-color: {secondary};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    min-width: 54px;
    min-height: 30px;
}}
QPushButton#nodeInfoCopyAddressButton:hover,
QPushButton#nodeInfoCopyEthButton:hover {{
    background-color: {secondary_hover};
}}
QPushButton#nodeInfoRefreshButton {{
    background-color: {primary};
    color: {primary_text};
    border: 1px solid {primary};
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 34px;
    font-weight: 600;
}}
QPushButton#nodeInfoRefreshButton:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}
"""


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ElidedAddressLabel(QLabel):
    """QLabel that stores full text while rendering a middle-elided address."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._update_display_text()

    def text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display_text()

    def _update_display_text(self):
        available_width = max(24, self.contentsRect().width() - 8)
        display_text = self.fontMetrics().elidedText(self._full_text, Qt.ElideMiddle, available_width)
        QLabel.setText(self, display_text)


class NodeInfoWidget(QWidget):
    """
    Widget for displaying node information
    """
    # Signals
    refresh_requested = pyqtSignal()  # Emitted when refresh button is clicked
    copy_address_requested = pyqtSignal(str)  # Emitted when copy address button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("nodeInfoWidget")
        self.setAccessibleName("Node information")
        self._is_dark_theme = False
        
        # Initialize UI components
        self.lbl_node_address = ElidedAddressLabel("N/A")
        self.lbl_node_address.setObjectName("nodeInfoAddressValue")
        self.lbl_node_address.setAccessibleName("Node address")
        self.lbl_eth_address = ElidedAddressLabel("N/A")
        self.lbl_eth_address.setObjectName("nodeInfoEthAddressValue")
        self.lbl_eth_address.setAccessibleName("ETH address")
        self.lbl_node_status = QLabel("Unknown")
        self.lbl_node_status.setObjectName("nodeInfoStatusValue")
        self.lbl_node_status.setAccessibleName("Node status")
        self.lbl_uptime = QLabel("N/A")
        self.lbl_uptime.setObjectName("nodeInfoUptimeValue")
        self.lbl_uptime.setAccessibleName("Node uptime")
        self.lbl_node_name = QLabel("N/A")
        self.lbl_node_name.setObjectName("nodeInfoNameValue")
        self.lbl_node_name.setAccessibleName("Node name")
        
        self.btn_copy_address = QPushButton("Copy")
        self.btn_copy_address.setObjectName("nodeInfoCopyAddressButton")
        self.btn_copy_address.setAccessibleName("Copy node address")
        self.btn_copy_address.setProperty("actionRole", "utility")
        self.btn_copy_address.setToolTip("Copy node address")
        self.btn_copy_eth = QPushButton("Copy")
        self.btn_copy_eth.setObjectName("nodeInfoCopyEthButton")
        self.btn_copy_eth.setAccessibleName("Copy ETH address")
        self.btn_copy_eth.setProperty("actionRole", "utility")
        self.btn_copy_eth.setToolTip("Copy ETH address")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("nodeInfoRefreshButton")
        self.btn_refresh.setAccessibleName("Refresh node information")
        self.btn_refresh.setProperty("actionRole", "primary")
        self.btn_refresh.setToolTip("Refresh node information")
        self.btn_refresh.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._configure_value_labels()
        self.apply_theme(False)
        
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
        
        # Create info group box
        self.info_group = QGroupBox("Node Information")
        self.info_group.setObjectName("nodeInfoGroup")
        self.info_group.setAccessibleName("Node information")
        self.info_group.setProperty("role", "nodeInfoPanel")
        info_layout = QGridLayout()
        info_layout.setContentsMargins(12, 16, 12, 12)
        info_layout.setHorizontalSpacing(10)
        info_layout.setVerticalSpacing(8)
        info_layout.setColumnStretch(0, 0)
        info_layout.setColumnStretch(1, 1)
        
        # Add node status row
        info_layout.addWidget(self._field_label("Status:", "nodeInfoStatusLabel", "Status label"), 0, 0)
        info_layout.addWidget(self.lbl_node_status, 0, 1)
        
        # Add node name row
        info_layout.addWidget(self._field_label("Node Name:", "nodeInfoNameLabel", "Node name label"), 1, 0)
        info_layout.addWidget(self.lbl_node_name, 1, 1)
        
        # Add uptime row
        info_layout.addWidget(self._field_label("Uptime:", "nodeInfoUptimeLabel", "Uptime label"), 2, 0)
        info_layout.addWidget(self.lbl_uptime, 2, 1)
        
        # Add Node address row with copy button
        info_layout.addWidget(self._field_label("Node Address:", "nodeInfoAddressLabel", "Node address label"), 3, 0)
        addr_layout = QHBoxLayout()
        addr_layout.setContentsMargins(0, 0, 0, 0)
        addr_layout.setSpacing(8)
        addr_layout.addWidget(self.lbl_node_address, 1)
        addr_layout.addWidget(self.btn_copy_address, 0)
        info_layout.addLayout(addr_layout, 3, 1)
        
        # Add ETH address row with copy button
        info_layout.addWidget(self._field_label("ETH Address:", "nodeInfoEthAddressLabel", "ETH address label"), 4, 0)
        eth_layout = QHBoxLayout()
        eth_layout.setContentsMargins(0, 0, 0, 0)
        eth_layout.setSpacing(8)
        eth_layout.addWidget(self.lbl_eth_address, 1)
        eth_layout.addWidget(self.btn_copy_eth, 0)
        info_layout.addLayout(eth_layout, 4, 1)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_refresh)
        info_layout.addLayout(button_layout, 5, 0, 1, 2)
        
        # Set info group layout
        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group)
        
        # Set layout
        self.setLayout(layout)
        
        # Set text alignment
        self.lbl_node_address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_eth_address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_node_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_uptime.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_node_name.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def _configure_value_labels(self):
        for label in (self.lbl_node_status, self.lbl_uptime, self.lbl_node_name):
            label.setProperty("role", "nodeInfoValue")
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        for label in (self.lbl_node_address, self.lbl_eth_address):
            label.setProperty("role", "nodeInfoAddress")
            label.setWordWrap(False)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self.lbl_node_status.setProperty("status", "unknown")

    def apply_theme(self, is_dark):
        """Apply compact component styling for standalone or embedded use."""
        self._is_dark_theme = bool(is_dark)
        colors = _NODE_INFO_STYLE_COLORS[self._is_dark_theme]
        self.setStyleSheet(_NODE_INFO_STYLE_TEMPLATE.format(**colors))

    def _field_label(self, text: str, object_name: str, accessible_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(accessible_name)
        label.setProperty("role", "nodeInfoFieldLabel")
        return label
    
    def connect_signals(self):
        """Connect widget signals to slots"""
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        self.btn_copy_address.clicked.connect(lambda: self.copy_address_requested.emit('node'))
        self.btn_copy_eth.clicked.connect(lambda: self.copy_address_requested.emit('eth'))
    
    def update_node_info(self, node_info: NodeInfo = None):
        """
        Update the displayed node information
        
        Args:
            node_info: NodeInfo object containing node information
        """
        if node_info:
            # Update node address
            self.lbl_node_address.setText(node_info.address or "N/A")
            self.lbl_node_address.setToolTip(node_info.address or "N/A")
            
            # Update ETH address
            self.lbl_eth_address.setText(node_info.eth_address or "N/A")
            self.lbl_eth_address.setToolTip(node_info.eth_address or "N/A")
            
            # Update status
            self.lbl_node_status.setText("Available")
            self.lbl_node_status.setProperty("status", "available")
            _repolish(self.lbl_node_status)
            
            # NodeInfo snapshots do not include runtime uptime.
            self.lbl_uptime.setText("N/A")
            
            # Update node name
            self.lbl_node_name.setText(node_info.alias or "N/A")
        else:
            self.clear_info()
    
    def clear_info(self):
        """Clear all displayed information"""
        self.lbl_node_address.setText("N/A")
        self.lbl_node_address.setToolTip("N/A")
        self.lbl_eth_address.setText("N/A")
        self.lbl_eth_address.setToolTip("N/A")
        self.lbl_node_status.setText("Unknown")
        self.lbl_node_status.setProperty("status", "unknown")
        _repolish(self.lbl_node_status)
        self.lbl_uptime.setText("N/A")
        self.lbl_node_name.setText("N/A")
    
    def _format_uptime(self, uptime_seconds: int) -> str:
        """
        Format uptime in seconds to a human-readable string
        
        Args:
            uptime_seconds: Uptime in seconds
            
        Returns:
            str: Formatted uptime string
        """
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{int(days)}d {int(hours)}h {int(minutes)}m"
        elif hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"
