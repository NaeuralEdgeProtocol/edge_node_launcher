from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, 
                             QPushButton, QHBoxLayout, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QColor

class LogConsoleWidget(QWidget):
    """
    Widget for displaying log output
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logConsoleWidget")
        self.setAccessibleName("Log console")
        
        # Initialize UI components
        self.text_console = QTextEdit()
        self.text_console.setObjectName("logConsoleText")
        self.text_console.setAccessibleName("Console log output")
        self.btn_clear = QPushButton("Clear Log")
        self.btn_clear.setObjectName("logConsoleClearButton")
        self.btn_clear.setAccessibleName("Clear console log")
        self.btn_clear.setToolTip("Clear console log")
        
        # Configure console
        self.text_console.setReadOnly(True)
        self.text_console.setLineWrapMode(QTextEdit.NoWrap)
        
        # Setup UI layout
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
    
    def init_ui(self):
        """Initialize the UI components and layout"""
        # Main layout
        layout = QVBoxLayout()
        
        # Create log group box
        self.log_group = QGroupBox("Console Log")
        self.log_group.setObjectName("logConsoleGroup")
        self.log_group.setAccessibleName("Console log")
        log_layout = QVBoxLayout()
        
        # Add console to layout
        log_layout.addWidget(self.text_console)
        
        # Set log group layout
        self.log_group.setLayout(log_layout)
        layout.addWidget(self.log_group)
        
        # Add button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.btn_clear)
        layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(layout)
    
    def connect_signals(self):
        """Connect widget signals to slots"""
        self.btn_clear.clicked.connect(self.clear_log)
    
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
            
            # Scroll to bottom
            self.text_console.ensureCursorVisible()
    
    def clear_log(self):
        """Clear all log content"""
        self.text_console.clear()
    
    def is_debug_enabled(self):
        """
        Check if debug logging is enabled
        
        Returns:
            bool: True if debug is enabled, False otherwise
        """
        # This would be connected to a debug setting in the parent application
        # For now, always return True to show all messages
        return True
