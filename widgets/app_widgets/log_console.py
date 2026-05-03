from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit,
                             QPushButton, QHBoxLayout, QGroupBox, QSizePolicy)
from PyQt5.QtGui import QTextCursor, QColor


MAX_LOG_LINES = 1000

_LOG_CONSOLE_STYLE_COLORS = {
    False: {
        "surface": "#FFFFFF",
        "border": "#CBD5E1",
        "text": "#1F2937",
        "muted": "#64748B",
        "console_bg": "#F8FAFC",
        "secondary": "#F7F9FC",
        "secondary_hover": "#EEF4FF",
        "disabled_bg": "#F1F5F9",
        "disabled_text": "#94A3B8",
    },
    True: {
        "surface": "#122033",
        "border": "#3E5876",
        "text": "#E8EEF8",
        "muted": "#93A4B8",
        "console_bg": "#0B1626",
        "secondary": "#243447",
        "secondary_hover": "#2E465E",
        "disabled_bg": "#182233",
        "disabled_text": "#71839A",
    },
}

_LOG_CONSOLE_STYLE_TEMPLATE = """
QWidget#logConsoleWidget {{
    background: transparent;
}}
QGroupBox#logConsoleGroup {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 12px;
    font-weight: 600;
}}
QGroupBox#logConsoleGroup::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0px 4px;
}}
QTextEdit#logConsoleText {{
    background-color: {console_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px;
    font-family: "Courier New";
    font-size: 9pt;
}}
QTextEdit#logConsoleText:focus {{
    border-color: {muted};
}}
QPushButton#logConsoleClearButton {{
    background-color: {secondary};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 32px;
    font-weight: 600;
}}
QPushButton#logConsoleClearButton:hover {{
    background-color: {secondary_hover};
}}
QPushButton#logConsoleClearButton:disabled {{
    background-color: {disabled_bg};
    color: {disabled_text};
}}
"""


class LogConsoleWidget(QWidget):
    """
    Widget for displaying log output
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logConsoleWidget")
        self.setAccessibleName("Log console")
        self._is_dark_theme = False
        
        # Initialize UI components
        self.text_console = QTextEdit()
        self.text_console.setObjectName("logConsoleText")
        self.text_console.setAccessibleName("Console log output")
        self.text_console.setProperty("role", "logConsoleOutput")
        self.btn_clear = QPushButton("Clear Log")
        self.btn_clear.setObjectName("logConsoleClearButton")
        self.btn_clear.setAccessibleName("Clear console log")
        self.btn_clear.setProperty("actionRole", "secondary")
        self.btn_clear.setToolTip("Clear console log")
        
        # Configure console
        self.text_console.setAcceptRichText(False)
        self.text_console.setReadOnly(True)
        self.text_console.setLineWrapMode(QTextEdit.NoWrap)
        self.text_console.setPlaceholderText("No log entries yet")
        self.text_console.document().setMaximumBlockCount(MAX_LOG_LINES)
        self.text_console.setMinimumHeight(140)
        self.text_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_clear.setEnabled(False)
        self.btn_clear.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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
        
        # Create log group box
        self.log_group = QGroupBox("Console Log")
        self.log_group.setObjectName("logConsoleGroup")
        self.log_group.setAccessibleName("Console log")
        self.log_group.setProperty("role", "logConsolePanel")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(12, 16, 12, 12)
        log_layout.setSpacing(8)
        
        # Add console to layout
        log_layout.addWidget(self.text_console)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_clear)
        log_layout.addLayout(button_layout)
        
        # Set log group layout
        self.log_group.setLayout(log_layout)
        layout.addWidget(self.log_group)
        
        # Set layout
        self.setLayout(layout)
    
    def connect_signals(self):
        """Connect widget signals to slots"""
        self.btn_clear.clicked.connect(self.clear_log)

    def apply_theme(self, is_dark):
        """Apply compact component styling for standalone or embedded use."""
        self._is_dark_theme = bool(is_dark)
        colors = _LOG_CONSOLE_STYLE_COLORS[self._is_dark_theme]
        self.setStyleSheet(_LOG_CONSOLE_STYLE_TEMPLATE.format(**colors))
    
    def add_log(self, text, color="gray", debug=False):
        """
        Add a log entry to the console
        
        Args:
            text: Text to add
            color: Text color (name or hex code)
            debug: Whether this is a debug message
        """
        # Check if this is a debug message and if debug is enabled
        if not debug or self.is_debug_enabled():
            # Move cursor to end
            self.text_console.moveCursor(QTextCursor.End)
            
            # Set text color
            self.text_console.setTextColor(QColor(color))
            
            # Append text
            self.text_console.insertPlainText(text + "\n")
            self.btn_clear.setEnabled(True)
            
            # Scroll to bottom
            self.text_console.ensureCursorVisible()
    
    def clear_log(self):
        """Clear all log content"""
        self.text_console.clear()
        self.btn_clear.setEnabled(False)
    
    def is_debug_enabled(self):
        """
        Check if debug logging is enabled
        
        Returns:
            bool: True if debug is enabled, False otherwise
        """
        # This would be connected to a debug setting in the parent application
        # For now, always return True to show all messages
        return True
