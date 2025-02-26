from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QCheckBox
)
from PyQt5.QtCore import pyqtSignal, QThread, Qt
from PyQt5.QtGui import QFont, QColor
import subprocess

from models.AnsibleHosts import AnsibleHostsManager

class SSHCheckThread(QThread):
    status_updated = pyqtSignal(str, bool)  # host, is_online

    def __init__(self, host, ssh_command):
        super().__init__()
        self.host = host
        self.ssh_command = ssh_command.split()  # Split into list of arguments

    def run(self):
        try:
            # Try to connect with a timeout of 3 seconds
            cmd = self.ssh_command + ['-o', 'ConnectTimeout=3', 'exit']
            subprocess.run(cmd, capture_output=True, timeout=3)
            self.status_updated.emit(self.host, True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            self.status_updated.emit(self.host, False)
        except Exception as e:
            print(f"SSH check error for {self.host}: {str(e)}")
            self.status_updated.emit(self.host, False)

class StatusIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.setAlignment(Qt.AlignCenter)
        self.setProperty("is_online", False)
        self.set_status(False)

    def set_status(self, is_online):
        color = "#4CAF50" if is_online else "#FF5252"  # Green if online, red if offline
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
                margin: 2px;
            }}
        """)
        self.setProperty("is_online", is_online)

class HostSelector(QWidget):
    host_selected = pyqtSignal(str)  # Emitted when a host is selected
    mode_changed = pyqtSignal(bool)  # Emitted when mode is changed (True for multi-host)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hosts_manager = AnsibleHostsManager()
        self.status_threads = {}  # Keep track of status check threads
        self.status_indicators = {}  # Keep track of status indicators
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Mode selector
        mode_layout = QHBoxLayout()
        self.mode_checkbox = QCheckBox("Multi-host Mode")
        self.mode_checkbox.setFont(QFont("Courier New", 10, QFont.Bold))
        self.mode_checkbox.stateChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_checkbox)
        layout.addLayout(mode_layout)

        # Host selector - vertical layout
        host_layout = QVBoxLayout()
        
        # Label in its own row
        self.host_label = QLabel("Select Host:")
        self.host_label.setFont(QFont("Courier New", 10))
        host_layout.addWidget(self.host_label)
        
        # Dropdown, status indicator and refresh button in a horizontal layout
        controls_layout = QHBoxLayout()
        
        # Create a widget to hold the combobox and status indicator
        combo_container = QWidget()
        combo_layout = QHBoxLayout(combo_container)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.setSpacing(4)
        
        self.host_combo = QComboBox()
        self.host_combo.setFont(QFont("Courier New", 10))
        self.host_combo.setMinimumWidth(200)
        
        # Add status indicator next to the combobox
        self.current_status = StatusIndicator()
        
        combo_layout.addWidget(self.host_combo)
        combo_layout.addWidget(self.current_status)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setFont(QFont("Courier New", 10))
        
        controls_layout.addWidget(combo_container)
        controls_layout.addWidget(self.refresh_button)
        
        host_layout.addLayout(controls_layout)
        layout.addLayout(host_layout)
        
        self.setLayout(layout)
        
        # Connect signals
        self.refresh_button.clicked.connect(self.refresh_hosts)
        self.host_combo.currentTextChanged.connect(self._on_host_selected)
        
        # Initial state
        self.host_label.setVisible(False)
        self.host_combo.setVisible(False)
        self.refresh_button.setVisible(False)
        self.current_status.setVisible(False)
        
        # Load hosts
        self.refresh_hosts()

    def refresh_hosts(self):
        """Refresh the list of available hosts."""
        current_host = self.host_combo.currentText()  # Store current selection
        self.host_combo.clear()
        host_names = self.hosts_manager.get_host_names()
        self.host_combo.addItems(host_names)
        
        # Restore previous selection if it still exists in the list
        if current_host in host_names:
            index = self.host_combo.findText(current_host)
            if index >= 0:
                self.host_combo.setCurrentIndex(index)
        
        # Start checking status for all hosts
        for host in host_names:
            self.check_host_status(host)

    def check_host_status(self, host_name):
        """Check if a host is online."""
        if host_name in self.status_threads and self.status_threads[host_name].isRunning():
            self.status_threads[host_name].terminate()
        
        ssh_command = self.hosts_manager.get_ssh_command(host_name)
        if ssh_command:
            thread = SSHCheckThread(host_name, ssh_command)
            thread.status_updated.connect(self._on_status_updated)
            self.status_threads[host_name] = thread
            thread.start()

    def _on_status_updated(self, host_name, is_online):
        """Handle status update from the check thread."""
        if host_name == self.host_combo.currentText():
            self.current_status.set_status(is_online)

    def get_current_host(self):
        """Get the currently selected host name."""
        return self.host_combo.currentText()

    def _on_host_selected(self, host_name):
        """Handle host selection."""
        if host_name:
            self.check_host_status(host_name)
            if self.mode_checkbox.isChecked():
                self.host_selected.emit(host_name)

    def _on_mode_changed(self, state):
        """Handle mode change."""
        is_multi_host = bool(state)
        self.host_label.setVisible(is_multi_host)
        self.host_combo.setVisible(is_multi_host)
        self.refresh_button.setVisible(is_multi_host)
        self.current_status.setVisible(is_multi_host)
        self.mode_changed.emit(is_multi_host)

    def get_ssh_command(self, host_name: str) -> str:
        """Get SSH command for the selected host."""
        return self.hosts_manager.get_ssh_command(host_name)

    def apply_stylesheet(self, is_dark_theme: bool):
        """Apply theme-specific styles."""
        if is_dark_theme:
            # Dark theme
            text_color = "white"
            bg_color = "#2b2b2b"
            border_color = "#555555"
            hover_color = "#3b3b3b"
            
            # Style for checkbox
            checkbox_style = f"""
                QCheckBox {{
                    color: {text_color};
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid {border_color};
                    border-radius: 4px;
                    background: {bg_color};
                }}
                QCheckBox::indicator:checked {{
                    background: #4CAF50;
                    border: 2px solid #4CAF50;
                }}
                QCheckBox::indicator:hover {{
                    border: 2px solid #4CAF50;
                }}
            """
            
            # Style for combobox
            combobox_style = f"""
                QComboBox {{
                    color: {text_color};
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 4px;
                    min-width: 100px;
                }}
                QComboBox:hover {{
                    background-color: {hover_color};
                    border: 1px solid #4CAF50;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 20px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid {text_color};
                    margin-right: 8px;
                }}
                QComboBox QAbstractItemView {{
                    color: {text_color};
                    background-color: {bg_color};
                    selection-background-color: {hover_color};
                    selection-color: {text_color};
                }}
            """
            
            # Style for refresh button
            button_style = f"""
                QPushButton {{
                    color: {text_color};
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                    border: 1px solid #4CAF50;
                }}
            """
        else:
            # Light theme
            text_color = "black"
            bg_color = "white"
            border_color = "#cccccc"
            hover_color = "#f5f5f5"
            
            # Style for checkbox
            checkbox_style = f"""
                QCheckBox {{
                    color: {text_color};
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid {border_color};
                    border-radius: 4px;
                    background: {bg_color};
                }}
                QCheckBox::indicator:checked {{
                    background: #4CAF50;
                    border: 2px solid #4CAF50;
                }}
                QCheckBox::indicator:hover {{
                    border: 2px solid #4CAF50;
                }}
            """
            
            # Style for combobox
            combobox_style = f"""
                QComboBox {{
                    color: {text_color};
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 4px;
                    min-width: 100px;
                }}
                QComboBox:hover {{
                    background-color: {hover_color};
                    border: 1px solid #4CAF50;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 20px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid {text_color};
                    margin-right: 8px;
                }}
                QComboBox QAbstractItemView {{
                    color: {text_color};
                    background-color: {bg_color};
                    selection-background-color: {hover_color};
                    selection-color: {text_color};
                }}
            """
            
            # Style for refresh button
            button_style = f"""
                QPushButton {{
                    color: {text_color};
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                    border: 1px solid #4CAF50;
                }}
            """

        # Apply styles
        self.mode_checkbox.setStyleSheet(checkbox_style)
        self.host_combo.setStyleSheet(combobox_style)
        self.refresh_button.setStyleSheet(button_style)
        self.host_label.setStyleSheet(f"color: {text_color};") 