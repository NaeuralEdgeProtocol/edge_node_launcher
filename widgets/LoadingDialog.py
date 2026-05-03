from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
import platform
from app_forms.frm_utils import LoadingIndicator

class LoadingDialog(QDialog):
    """Reusable loading dialog widget that can be used throughout the application.
    
    This dialog shows a loading spinner with a customizable message and title.
    It is designed to be used for any long-running operation in the application.
    """
    
    def __init__(self, parent=None, title="Loading", message="Please wait...", size=50, stylesheet=None):
        """Initialize the loading dialog.
        
        Args:
            parent: Parent widget
            title: Title of the dialog
            message: Message to display
            size: Size of the loading indicator
            stylesheet: Custom stylesheet to apply to the dialog
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("loadingDialog")
        self.setAccessibleName(title)
        
        # Set window flags based on platform
        # On some platforms, we need to keep the default flags for proper functioning
        system = platform.system().lower()
        linux_titlebar_style = False
        if system == "linux":
            # On Linux, we can use custom styling while keeping the title bar
            # But we need to extend the stylesheet for better title bar integration
            linux_titlebar_style = True
        elif system == "windows":
            # Windows handles the custom styling better with default decorations
            pass
        elif system == "darwin":  # macOS
            # macOS needs special handling for proper appearance
            self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        
        self.setFixedSize(300, 180)
        self.setModal(True)
        
        # Use system colors instead of blue background
        # This will match the application's theme
        base_style = """
            QDialog {
                border: none;
                border-radius: 8px;
            }
            QLabel {
                font-size: 14px;
            }
            #loadingDialogTitleLabel {
                font-size: 16px;
                font-weight: bold;
            }
            #loadingDialogMessageLabel {
                font-size: 14px;
            }
        """
        
        # Apply platform-specific styles
        if linux_titlebar_style:
            # On Linux, add specific styling for the title bar
            linux_style = """
                QDialog {
                    border: 1px solid #777777;
                }
            """
            base_style += linux_style
        
        # Apply the base style and any custom stylesheet
        self.setStyleSheet(base_style + (stylesheet or ""))
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Create loading indicator
        self.loading_indicator = LoadingIndicator(size=size)
        self.loading_indicator.setObjectName("loadingDialogIndicator")
        self.loading_indicator.setAccessibleName("Loading indicator")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("loadingDialogTitleLabel")
        self.title_label.setAccessibleName("Loading dialog title")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        
        # Create message label
        self.message_label = QLabel(message)
        self.message_label.setObjectName("loadingDialogMessageLabel")
        self.message_label.setAccessibleName("Loading dialog message")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        
        # Add widgets to layout
        indicator_layout = QHBoxLayout()
        indicator_layout.addStretch()
        indicator_layout.addWidget(self.loading_indicator)
        indicator_layout.addStretch()
        
        layout.addWidget(self.title_label)
        layout.addLayout(indicator_layout)
        layout.addWidget(self.message_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Start the loading animation
        self.loading_indicator.start()
    
    @pyqtSlot(str)
    def set_message(self, message):
        """Update the dialog message.
        
        Args:
            message: New message to display
        """
        if hasattr(self, 'message_label'):
            self.message_label.setText(message)
    
    def closeEvent(self, event):
        """Handle the dialog close event.
        
        Args:
            event: Close event
        """
        # Ensure the timer is stopped before closing
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.stop()
        
        # Safely close without affecting parent widgets
        event.accept()
    
    @pyqtSlot()
    def safe_close(self):
        """Safely close the dialog with a timer to prevent direct deletion."""
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.stop()
        
        # Close immediately and then use a timer to ensure proper cleanup
        self.close()
        # Use a short timer to ensure proper context for closing
        # This must be called from the main thread
        QTimer.singleShot(100, self.deleteLater)

    def _queue_refresh(self):
        """Queue a repaint without synchronously pumping the Qt event loop."""
        QTimer.singleShot(0, self.update)
    
    @pyqtSlot(str)
    def update_progress(self, message, process_events=True):
        """Update the dialog with progress information.
        
        Args:
            message: Progress message to display
            process_events: Whether to queue a refresh after updating
        """
        self.set_message(message)
        if process_events:
            self._queue_refresh()
    
    @pyqtSlot()
    def keep_alive(self):
        """Queue a refresh to keep the dialog visually current.
        
        This method can be called periodically during long operations
        to ensure the UI doesn't freeze.
        """
        self._queue_refresh()
    
    def showEvent(self, event):
        """Override show event to queue an initial refresh."""
        super().showEvent(event)
        self._queue_refresh()
