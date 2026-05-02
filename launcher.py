"""
EdgeNodeLauncher Wrapper Script

This script serves as a wrapper for the main application, capturing all console output
and ensuring no console windows appear when running Docker commands.
"""

import sys
import os
import traceback
import logging
from logging.handlers import RotatingFileHandler
import ctypes
import tempfile

# Setup logging to file instead of console
def setup_logging():
    """Set up logging to file to capture any console output"""
    log_dir = os.path.join(tempfile.gettempdir(), "EdgeNodeLauncher")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, "launcher.log")
    
    # Configure rotating file handler
    handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    # We won't redirect stdout/stderr as it can cause issues with PyQt
    # Just log our own messages
    logging.info("Logging initialized")
    return log_file

def hide_console_window():
    """Hide the console window on Windows"""
    if os.name == 'nt':
        try:
            # Get and hide console window
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window:
                ctypes.windll.user32.ShowWindow(console_window, 0)  # SW_HIDE
                logging.info("Console window hidden")
        except Exception as e:
            logging.error(f"Failed to hide console window: {str(e)}")
            # Continue even if this fails

def patch_subprocess_module():
    """Patch subprocess module to hide all console windows"""
    try:
        # Import the subprocess hook which will patch all calls
        import utils.subprocess_hook
        logging.info("Subprocess module patched")
        return True
    except Exception as e:
        logging.error(f"Failed to patch subprocess module: {str(e)}")
        # Continue even if patching fails
        return False

def run_main_application():
    """Run the main application directly"""
    try:
        # Import the necessary components directly from main
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        from app_forms.frm_main import EdgeNodeLauncher
        from utils.icon_helper import apply_icon_to_app
        
        # Patch subprocess first
        patch_subprocess_module()
        
        # Handle high DPI displays
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Create application
        app = QApplication(sys.argv)
        
        # Set app name for better integration
        app.setApplicationName("EdgeNodeLauncher")
        app.setOrganizationName("Ratio1")
        
        # Apply icon from helper
        icon = apply_icon_to_app(app)
        
        # Set app ID for Windows
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ratio1.edge_node_launcher")
                logging.info("Set Windows AppUserModelID for taskbar icon")
            except Exception as e:
                logging.error(f"Error setting AppUserModelID: {e}")
        
        # Create the main window. The launcher shows itself after UI setup so startup checks can log into it.
        manager = EdgeNodeLauncher(icon)
        
        # Start the event loop
        return app.exec_()
        
    except Exception as e:
        logging.error(f"Application error: {str(e)}")
        logging.error(traceback.format_exc())
        # Show error message to user
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(0, 
                f"Application error: {str(e)}\n\nSee log file at: {log_file}", 
                "EdgeNodeLauncher Error", 0x10)
        return 1

if __name__ == "__main__":
    # Set up logging to file
    log_file = setup_logging()
    logging.info("Starting EdgeNodeLauncher wrapper")
    
    # Hide console window
    hide_console_window()
    
    # Run the application directly instead of importing main.py
    sys.exit(run_main_application())
