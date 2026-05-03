from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGridLayout, QGroupBox)
from PyQt5.QtCore import pyqtSignal, Qt
from models.NodeInfo import NodeInfo

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
        
        # Initialize UI components
        self.lbl_node_address = QLabel("N/A")
        self.lbl_node_address.setObjectName("nodeInfoAddressValue")
        self.lbl_node_address.setAccessibleName("Node address")
        self.lbl_eth_address = QLabel("N/A")
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
        self.btn_copy_address.setToolTip("Copy node address")
        self.btn_copy_eth = QPushButton("Copy")
        self.btn_copy_eth.setObjectName("nodeInfoCopyEthButton")
        self.btn_copy_eth.setAccessibleName("Copy ETH address")
        self.btn_copy_eth.setToolTip("Copy ETH address")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("nodeInfoRefreshButton")
        self.btn_refresh.setAccessibleName("Refresh node information")
        self.btn_refresh.setToolTip("Refresh node information")
        
        # Setup UI layout
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
    
    def init_ui(self):
        """Initialize the UI components and layout"""
        # Main layout
        layout = QVBoxLayout()
        
        # Create info group box
        self.info_group = QGroupBox("Node Information")
        self.info_group.setObjectName("nodeInfoGroup")
        self.info_group.setAccessibleName("Node information")
        info_layout = QGridLayout()
        
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
        addr_layout.addWidget(self.lbl_node_address, 1)
        addr_layout.addWidget(self.btn_copy_address, 0)
        info_layout.addLayout(addr_layout, 3, 1)
        
        # Add ETH address row with copy button
        info_layout.addWidget(self._field_label("ETH Address:", "nodeInfoEthAddressLabel", "ETH address label"), 4, 0)
        eth_layout = QHBoxLayout()
        eth_layout.addWidget(self.lbl_eth_address, 1)
        eth_layout.addWidget(self.btn_copy_eth, 0)
        info_layout.addLayout(eth_layout, 4, 1)
        
        # Set info group layout
        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group)
        
        # Add refresh button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.btn_refresh)
        layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(layout)
        
        # Set text alignment
        self.lbl_node_address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_eth_address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_node_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_uptime.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_node_name.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def _field_label(self, text: str, object_name: str, accessible_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(accessible_name)
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
            
            # Update ETH address
            self.lbl_eth_address.setText(node_info.eth_address or "N/A")
            
            # Update status
            self.lbl_node_status.setText("Available")
            
            # NodeInfo snapshots do not include runtime uptime.
            self.lbl_uptime.setText("N/A")
            
            # Update node name
            self.lbl_node_name.setText(node_info.alias or "N/A")
        else:
            self.clear_info()
    
    def clear_info(self):
        """Clear all displayed information"""
        self.lbl_node_address.setText("N/A")
        self.lbl_eth_address.setText("N/A")
        self.lbl_node_status.setText("Unknown")
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
