import logging
import sys
import platform
import os
import json
import dataclasses
import subprocess

from datetime import datetime, timedelta
from time import time
from typing import Optional
import re

from PyQt5.QtWidgets import (
  QApplication,
  QWidget,
  QVBoxLayout,
  QPushButton,
  QLabel,
  QGridLayout,
  QFrame,
  QTextEdit,
  QDialog,
  QHBoxLayout,
  QCheckBox,
  QStyle,
  QComboBox,
  QMessageBox,
  QFileDialog,
  QLineEdit, QGroupBox,
  QGraphicsDropShadowEffect,
  QTabWidget,
  QDialogButtonBox,
  QPlainTextEdit,
  QMenuBar,
  QMenu,
  QAction,
  QSplitter,
  QProgressBar,
  QDesktopWidget,
  QMainWindow,
  QScrollArea,
  QToolButton,
  QTextBrowser,
  QListWidget,
  QGridLayout,
  QStackedWidget,
  QFormLayout,
  QListWidgetItem
)
from PyQt5 import sip
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QThread, QObject, pyqtSignal, QUrl, QSettings, QRect,
    QProcess, QPropertyAnimation, QModelIndex, QSortFilterProxyModel
)
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter
import pyqtgraph as pg
from PyQt5.QtSvg import QSvgRenderer

from models.NodeInfo import NodeInfo
from models.NodeHistory import NodeHistory
from widgets.ToastWidget import ToastWidget, NotificationType
from utils.const import *
from utils.docker import _DockerUtilsMixin
from utils.docker_commands import DockerCommandHandler
from utils.updater import _UpdaterMixin
from utils.system_resources import _SystemResourcesMixin
from utils.docker_utils import get_volume_name, generate_container_name
from utils.config_manager import ConfigManager, ContainerConfig
from utils.container_selection import SelectedContainer, selected_container_from_combo, select_container_by_name
from utils.lifecycle_state import LifecycleState
from utils.window_geometry import calculate_initial_window_geometry, calculate_restored_window_geometry, calculate_visible_frame_client_geometry, format_rect

from utils.icon import ICON_BASE64

from app_forms.frm_utils import (
  get_icon_from_base64, DateAxisItem, LoadingIndicator
)

from ver import __VER__ as __version__
from widgets.dialogs.AuthorizedAddressedDialog import AuthorizedAddressesDialog
from models.AllowedAddress import AllowedAddress, AllowedAddressList
from models.StartupConfig import StartupConfig
from models.ConfigApp import ConfigApp
from widgets.HostSelector import HostSelector
from widgets.ModeSwitch import ModeSwitch
from widgets.dialogs.DockerCheckDialog import DockerCheckDialog
from widgets.CenteredComboBox import CenteredComboBox
from widgets.LoadingDialog import LoadingDialog

from ver import __VER__ as CURRENT_VERSION


DASHBOARD_SPLITTER_DEFAULT_SIZES = [700, 180]


def get_platform_and_os_info():
  platform_info = platform.platform()
  os_name = platform.system()
  os_version = platform.version()
  return platform_info, os_name, os_version

def log_with_color(message, color="gray"):
  """
    Log message with color in the terminal.
    :param message: Message to log
    :param color: Color of the message
  """
  color_codes = {
    "yellow": "\033[93m",
    "red": "\033[91m",
    "gray": "\033[90m",
    "light": "\033[97m",
    "green": "\033[92m",
    "blue" : "\033[94m",
    "cyan" : "\033[96m",
  }
  start_color = color_codes.get(color, "\033[90m")
  end_color = "\033[0m"
  print(f"{start_color}{message}{end_color}", flush=True)
  return

class EdgeNodeLauncher(QWidget, _DockerUtilsMixin, _UpdaterMixin, _SystemResourcesMixin):
  def __init__(self, app_icon=None):
    self.logView = None
    self.dashboard_splitter = None
    self.log_buffer = []
    self.__force_debug = False
    super().__init__()
    self._window_geometry_log_timer = QTimer(self)
    self._window_geometry_log_timer.setSingleShot(True)
    self._window_geometry_log_timer.timeout.connect(self._flush_window_geometry_log)
    self._pending_window_geometry_context = "changed"

    # Set current environment (you'll need to get this from your configuration)
    self.current_environment = DEFAULT_ENVIRONMENT

    self.__current_node_uptime = -1
    self.__current_node_epoch = -1
    self.__current_node_epoch_avail = -1
    self.__current_node_ver = -1
    self.__display_uptime = None

    self._current_stylesheet = DARK_STYLESHEET  # Default to dark theme
    self.__last_plot_data = None
    self.__last_auto_update_check = 0

    # Track update process state to prevent duplicate notifications
    self.__update_in_progress = False
    self.__update_dialog_shown = False
    
    # Track Docker pull state to prevent concurrent pulls
    self.__lifecycle_state = LifecycleState()
    self.__docker_pull_in_progress = False
    self.__pending_launch_context = None
    self.__active_lifecycle_operation = None
    self.__shutting_down = False
    
    self.__version__ = __version__
    self.__last_timesteps = []
    self._icon = get_icon_from_base64(ICON_BASE64)
    self.setWindowIcon(self._icon)
    
    # Initialize the button colors based on current theme
    self.init_button_colors()

    self.runs_in_production = self.is_running_in_production()

    # Set the application icon - use the provided icon directly
    self._icon = app_icon
    if self._icon is None:
      # Only fall back to base64 if no icon provided
      from utils.icon_helper import get_app_icon
      self._icon = get_app_icon()
      self.add_log("Loaded application icon via helper", debug=True)
    else:
      self.add_log("Using provided application icon", debug=True)

    # Apply window icon immediately
    self.setWindowIcon(self._icon)

    # Initialize config manager for container configurations
    self.config_manager = ConfigManager()

    # Initialize force debug from saved settings
    self.__force_debug = self.config_manager.get_force_debug()

    self.initUI()
    
    # Set initial theme class
    self.force_debug_checkbox.setProperty('class', 'dark')

    self.__cwd = os.getcwd()
    
    self.show_initial_window()
    self.add_log(f'Edge Node Launcher v{self.__version__} started. Running in production: {self.runs_in_production}, running with debugger: {self.runs_with_debugger()}, running in ipython: {self.runs_from_ipython()},  running from exe: {not self.not_running_from_exe()}')
    self.add_log(f'Running from: {self.__cwd}')

    platform_info, os_name, os_version = get_platform_and_os_info()
    self.add_log(f'Platform: {platform_info}')
    self.add_log(f'OS: {os_name} {os_version}')

    # Check Docker and handle UI interactions
    if not self.check_docker_with_ui():
        self.close()
        sys.exit(1)

    self.docker_initialize()
    self.docker_handler = DockerCommandHandler(DOCKER_CONTAINER_NAME)

    # Initialize container list
    self.refresh_container_list()

    # Set initial container status
    self.container_last_run_status = False
    
    # Track if user intentionally stopped the container to prevent auto-restart
    self.user_stopped_container = False
    
    # Track failed get_node_info requests for auto-restart
    self.node_info_failure_count = 0
    
    # Check if container is running and update UI accordingly
    if self.is_container_running():
        self.add_log("Container is running on startup, updating UI", debug=True)
        # Clear the stop flag since container is already running
        self.user_stopped_container = False
        self.post_launch_setup()
        self.refresh_node_info()
        self.plot_data()  # Initial plot
    else:
        self.add_log("No running container found on startup", debug=True)

    # Ensure button state is correct
    self.update_toggle_button_text()

    self.timer = QTimer(self)
    self.timer.timeout.connect(self.refresh_all)
    self.timer.start(REFRESH_TIME)  # Refresh every 10 seconds
    self.toast = ToastWidget(self)

    # Initialize copy button icons based on current theme
    self.update_copy_button_icons()

    # Initialize system resources display
    self.update_resources_display()

    # Perform initial force refresh to get the latest data
    if self.container_combo.count() > 0:
        self.add_log("Performing initial force refresh on startup...", color="blue")
        # Use a timer to ensure UI is fully initialized before refreshing
        QTimer.singleShot(500, self.force_refresh_all)

    # Perform initial update check on startup
    self.check_for_updates(verbose=True)

  def init_button_colors(self):
    """Initialize or update button colors based on current theme"""
    is_dark = self._current_stylesheet == DARK_STYLESHEET
    colors = DARK_COLORS if is_dark else LIGHT_COLORS
    
    self.button_colors = {
        'start': {
            'bg': colors['toggle_button_start_bg'],
            'hover': colors['toggle_button_start_hover'],
            'text': colors['toggle_button_start_text'],
            'border': colors['toggle_button_start_border']
        },
        'stop': {
            'bg': colors['toggle_button_stop_bg'],
            'hover': colors['toggle_button_stop_hover'],
            'text': colors['toggle_button_stop_text'],
            'border': colors['toggle_button_stop_border']
        },
        'disabled': {
            'bg': colors['toggle_button_disabled_bg'],
            'hover': colors['toggle_button_disabled_hover'],
            'text': colors['toggle_button_disabled_text'],
            'border': colors['toggle_button_disabled_border']
        },
        'toggle_start': {
            'bg': colors['toggle_button_start_bg'],
            'hover': colors['toggle_button_start_hover'],
            'text': colors['toggle_button_start_text'],
            'border': colors['toggle_button_start_border']
        },
        'toggle_stop': {
            'bg': colors['toggle_button_stop_bg'],
            'hover': colors['toggle_button_stop_hover'],
            'text': colors['toggle_button_stop_text'],
            'border': colors['toggle_button_stop_border']
        },
        'toggle_disabled': {
            'bg': colors['toggle_button_disabled_bg'],
            'text': colors['toggle_button_disabled_text'],
            'border': colors['toggle_button_disabled_border'],
            'hover': colors['toggle_button_disabled_hover']
        }
    }

  def apply_button_style(self, button, style_type):
    """Apply button style based on button colors and state
    
    Args:
        button: The button to style
        style_type: The type of style to apply ('start', 'stop', 'disabled')
    """
    if style_type == 'disabled':
        button.setStyleSheet(f"background-color: {self.button_colors['disabled']['bg']}; color: {self.button_colors['disabled']['text']};")
        return
    
    # Check if the style type has a hover property
    has_hover = 'hover' in self.button_colors[style_type]
    
    hover_css = f"""
        QPushButton:hover {{
            background-color: {self.button_colors[style_type]['hover']};
        }}
    """ if has_hover else ""
    
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: {self.button_colors[style_type]['bg']};
            color: {self.button_colors[style_type]['text']};
            border: 2px solid {self.button_colors[style_type]['border']};
            padding: 5px 10px;
            border-radius: 15px;
        }}
        {hover_css}
    """)

  def create_sidebar_section_label(self, text, object_name):
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setProperty("role", "sidebarSection")
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setFont(QFont("Courier New", 9, QFont.Bold))
    return label

  def check_docker_with_ui(self):
    """Check Docker status and handle UI interactions.
    
    Returns:
        bool: True if Docker is ready to use, False otherwise
    """
    while True:
        is_installed, is_running, error_msg = super().check_docker()
        if is_installed and is_running:
            return True
            
        # Show the Docker check dialog
        dialog = DockerCheckDialog(self, self._icon)
        if error_msg:
            dialog.message.setText(error_msg + '\nPlease install/start Docker and try again.')
        
        result = dialog.exec_()
        if result == QDialog.Accepted:  # User clicked "Try Again"
            continue
        else:  # User clicked "Quit" or closed the dialog
            return False
  
  @staticmethod
  def not_running_from_exe():
    """
    Checks if the script is running from a PyInstaller-generated executable.

    Returns
    -------
    bool
      True if running from a PyInstaller executable, False otherwise.
    """
    return not (hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'))
  
  @staticmethod
  def runs_from_ipython():
    try:
      __IPYTHON__
      return True
    except NameError:
      return False
    
  @staticmethod
  def runs_with_debugger():
    gettrace = getattr(sys, 'gettrace', None)
    if gettrace is None:
      return False
    else:
      return not gettrace() is None    
    
  def is_running_in_production(self):
    return not (self.runs_from_ipython() or self.runs_with_debugger() or self.not_running_from_exe())
  
  
  def add_log(self, line, debug=False, color="gray"):
    show = (debug and not self.runs_in_production) or not debug
    show = show or self.__force_debug
    if show:      
      timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
      line = f'{timestamp} {line}'
      if self.logView is not None:
        self.logView.append(line)
      else:
        self.log_buffer.append(line)
      QApplication.processEvents()  # Flush the event queue
      if debug or self.__force_debug:
        log_with_color(line, color=color)
    return  
  
  def center(self):
    geometry = calculate_initial_window_geometry(
      self._available_screen_geometry(),
      preferred_width=self.width(),
      preferred_height=self.height(),
    )
    self.setGeometry(geometry)
    return

  def _available_screen_geometry(self):
    screen = self.screen() or QApplication.primaryScreen()
    if screen:
      return screen.availableGeometry()
    return QApplication.desktop().availableGeometry(self)

  def _screen_geometry(self):
    screen = self.screen() or QApplication.primaryScreen()
    if screen:
      return screen.geometry()
    return QApplication.desktop().screenGeometry(self)

  def apply_initial_window_geometry(self):
    available_geometry = self._available_screen_geometry()
    saved_geometry = self._saved_main_window_geometry()
    if saved_geometry is not None:
      window_geometry = calculate_restored_window_geometry(available_geometry, saved_geometry)
    else:
      window_geometry = calculate_initial_window_geometry(available_geometry)
    min_width = min(1100, window_geometry.width())
    min_height = min(700, window_geometry.height())
    self.setMinimumSize(min_width, min_height)
    self.setGeometry(window_geometry)
    self.log_window_geometry("configured", visible=True)
    return

  def _saved_main_window_geometry(self):
    if not hasattr(self, "config_manager") or self.config_manager is None:
      return None

    saved_geometry = self.config_manager.get_main_window_geometry()
    if not saved_geometry:
      return None

    return QRect(
      saved_geometry["x"],
      saved_geometry["y"],
      saved_geometry["width"],
      saved_geometry["height"],
    )

  def _current_main_window_geometry_payload(self):
    geometry = self.geometry()
    if self.isMaximized():
      normal_geometry = self.normalGeometry()
      if normal_geometry.isValid():
        geometry = normal_geometry

    if geometry is None or geometry.isNull() or not geometry.isValid():
      return None

    return {
      "x": geometry.x(),
      "y": geometry.y(),
      "width": geometry.width(),
      "height": geometry.height(),
    }

  def _save_main_window_geometry(self):
    if not hasattr(self, "config_manager") or self.config_manager is None:
      return False
    if self.isFullScreen() or self.isMinimized():
      return False

    geometry = self._current_main_window_geometry_payload()
    if geometry is None:
      return False

    return self.config_manager.set_main_window_geometry(geometry)

  def show_initial_window(self):
    self.show()
    QTimer.singleShot(0, self.ensure_window_frame_visible)
    QTimer.singleShot(50, self.ensure_window_frame_visible)
    QTimer.singleShot(100, lambda: self.log_window_geometry("shown", visible=True))
    return

  def ensure_window_frame_visible(self):
    if self.isFullScreen():
      return

    available_geometry = self._available_screen_geometry()
    adjusted_geometry = calculate_visible_frame_client_geometry(
      available_geometry,
      self.geometry(),
      self.frameGeometry(),
    )
    if adjusted_geometry != self.geometry():
      self.setGeometry(adjusted_geometry)
      self.add_log(
        f"Adjusted startup window geometry to keep title bar visible: client=[{format_rect(self.geometry())}], frame=[{format_rect(self.frameGeometry())}], available=[{format_rect(available_geometry)}]",
        debug=True,
      )
    return

  def log_window_geometry(self, context="window", visible=False):
    try:
      message = (
        f"Window geometry ({context}): "
        f"screen=[{format_rect(self._screen_geometry())}], "
        f"available=[{format_rect(self._available_screen_geometry())}], "
        f"client=[{format_rect(self.geometry())}], "
        f"frame=[{format_rect(self.frameGeometry())}], "
        f"maximized={self.isMaximized()}, full_screen={self.isFullScreen()}"
      )
      logging.info(message)
      if visible:
        self.add_log(message, debug=True)
    except Exception as e:
      logging.error(f"Failed to log window geometry: {e}")
    return

  def _schedule_window_geometry_log(self, context):
    if hasattr(self, "_window_geometry_log_timer") and self._window_geometry_log_timer is not None:
      self._pending_window_geometry_context = context
      self._window_geometry_log_timer.start(500)
    return

  def _flush_window_geometry_log(self):
    self.log_window_geometry(self._pending_window_geometry_context)
    self._save_main_window_geometry()
    return

  def moveEvent(self, event):
    super().moveEvent(event)
    self._schedule_window_geometry_log("moved")
    return

  def resizeEvent(self, event):
    super().resizeEvent(event)
    self._schedule_window_geometry_log("resized")
    return

  def set_windows_taskbar_icon(self):
    # Set app id for Windows taskbar
    if os.name == 'nt':  # Windows
      try:
        import ctypes
        myappid = 'ratio1.edge_node_launcher'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        self.add_log(f"Set Windows taskbar AppUserModelID to {myappid}", debug=True)
      except Exception as e:
        self.add_log(f"Error setting Windows AppUserModelID: {str(e)}", debug=True)

    # Apply icon to window and application
    self.setWindowIcon(self._icon)
    app = QApplication.instance()
    if app:
      app.setWindowIcon(self._icon)
      self.add_log(f"Applied icon to application and window", debug=True)
    return

  def _create_plot_container(self, object_name: str, plot_widget: QWidget) -> QWidget:
    """Create one styled plot container for the metrics grid."""
    container = QWidget()
    container.setObjectName(object_name)
    container.setProperty('class', 'plot-container')

    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(plot_widget)

    return container

  def _create_metrics_graph_grid(self) -> QWidget:
    """Build the four-panel metrics graph grid and retain public plot attributes."""
    graph_view = QWidget()
    graph_view.setObjectName("metricsGraphGrid")

    graph_layout = QGridLayout()
    graph_layout.setSpacing(10)
    graph_layout.setContentsMargins(0, 0, 0, 0)

    plot_specs = (
      ("cpu_plot", "cpuPlotContainer", 0, 0),
      ("memory_plot", "memoryPlotContainer", 0, 1),
      ("gpu_plot", "gpuPlotContainer", 1, 0),
      ("gpu_memory_plot", "gpuMemoryPlotContainer", 1, 1),
    )

    for plot_attr, container_name, row, column in plot_specs:
      plot_widget = pg.PlotWidget()
      setattr(self, plot_attr, plot_widget)
      graph_layout.addWidget(
        self._create_plot_container(container_name, plot_widget),
        row,
        column,
      )

    graph_view.setLayout(graph_layout)
    return graph_view

  def _create_activity_log_view(self) -> QTextEdit:
    """Create the activity log view with a stable automation target."""
    log_view = QTextEdit()
    log_view.setObjectName("logView")
    log_view.setReadOnly(True)
    log_view.setStyleSheet(self._current_stylesheet)
    log_view.setMinimumHeight(120)
    log_view.setFont(QFont("Courier New"))
    return log_view

  def _flush_log_buffer_to_view(self) -> None:
    if not self.log_buffer or self.logView is None:
      return

    for line in self.log_buffer:
      self.logView.append(line)
    self.log_buffer = []

  def _dashboard_splitter_initial_sizes(self) -> list:
    saved_sizes = self.config_manager.get_dashboard_splitter_sizes()
    return saved_sizes if saved_sizes else list(DASHBOARD_SPLITTER_DEFAULT_SIZES)

  def _save_dashboard_splitter_sizes(self) -> None:
    if self.dashboard_splitter is None:
      return
    self.config_manager.set_dashboard_splitter_sizes(self.dashboard_splitter.sizes())

  def _create_dashboard_panel(self) -> QWidget:
    """Create the right-side metrics and activity panel."""
    dashboard_panel = QWidget()
    dashboard_panel.setObjectName("dashboardPanel")

    dashboard_layout = QVBoxLayout(dashboard_panel)
    dashboard_layout.setContentsMargins(10, 0, 10, 10)
    dashboard_layout.setSpacing(10)

    self.dashboard_splitter = QSplitter(Qt.Vertical)
    self.dashboard_splitter.setObjectName("dashboardSplitter")
    self.dashboard_splitter.setChildrenCollapsible(False)
    self.dashboard_splitter.setHandleWidth(8)

    self.graphView = self._create_metrics_graph_grid()
    self.logView = self._create_activity_log_view()
    self.dashboard_splitter.addWidget(self.graphView)
    self.dashboard_splitter.addWidget(self.logView)
    self.dashboard_splitter.setStretchFactor(0, 4)
    self.dashboard_splitter.setStretchFactor(1, 1)
    self.dashboard_splitter.setSizes(self._dashboard_splitter_initial_sizes())
    self.dashboard_splitter.splitterMoved.connect(lambda _pos, _index: self._save_dashboard_splitter_sizes())

    dashboard_layout.addWidget(self.dashboard_splitter)
    self._flush_log_buffer_to_view()

    return dashboard_panel

  def _create_right_dashboard_container(self) -> QWidget:
    right_container = QWidget()
    right_container.setObjectName("rightDashboardContainer")

    right_container_layout = QVBoxLayout(right_container)
    right_container_layout.setContentsMargins(0, 0, 0, 29)
    right_container_layout.setSpacing(0)
    right_container_layout.addSpacing(5)
    right_container_layout.addWidget(self._create_dashboard_panel())

    return right_container

  def _create_sidebar_scroll_area(self, sidebar_widget: QWidget) -> QScrollArea:
    sidebar_scroll = QScrollArea()
    sidebar_scroll.setObjectName("sidebarScrollArea")
    sidebar_scroll.setWidgetResizable(True)
    sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    sidebar_scroll.setFrameShape(QFrame.NoFrame)
    sidebar_scroll.setFixedWidth(300)
    sidebar_scroll.setWidget(sidebar_widget)
    return sidebar_scroll

  def _create_sidebar_panel(self) -> QWidget:
    """Create the left navigation and status sidebar."""
    menu_widget = QWidget()
    menu_widget.setObjectName("sidebarPanel")
    menu_widget.setProperty("role", "navigationSidebar")
    menu_widget.setFixedWidth(300)

    menu_layout = QVBoxLayout(menu_widget)
    menu_layout.setAlignment(Qt.AlignTop)
    menu_layout.setContentsMargins(0, 2, 0, 2)

    top_button_area = QVBoxLayout()
    top_button_area.setObjectName("topButtonArea")
    top_button_area.setContentsMargins(5, 0, 5, 4)
    top_button_area.addWidget(self.create_sidebar_section_label("Node", "nodeControlsSectionLabel"))

    container_selector_layout = QVBoxLayout()
    self.add_node_button = QPushButton("Add New Node")
    self.add_node_button.clicked.connect(self.show_add_node_dialog)
    self.add_node_button.setObjectName("addNodeButton")
    self.add_node_button.setToolTip(ADD_NODE_TOOLTIP)
    container_selector_layout.addWidget(self.add_node_button)

    self.container_combo = CenteredComboBox()
    self.container_combo.setFont(QFont("Courier New", 10))
    self.container_combo.currentTextChanged.connect(self._on_container_selected)
    self.container_combo.setMinimumHeight(32)
    is_dark = self._current_stylesheet == DARK_STYLESHEET
    if hasattr(self.container_combo, 'set_theme'):
        self.container_combo.set_theme(is_dark)
    container_selector_layout.addWidget(self.container_combo)

    top_button_area.addLayout(container_selector_layout)

    self.renameNodeButton = QPushButton(RENAME_NODE_BUTTON_TEXT)
    self.renameNodeButton.setObjectName("renameNodeButton")
    self.renameNodeButton.setToolTip(RENAME_NODE_TOOLTIP)
    self.renameNodeButton.clicked.connect(self.show_rename_dialog)
    top_button_area.addWidget(self.renameNodeButton)

    self.toggleButton = QPushButton(LAUNCH_CONTAINER_BUTTON_TEXT)
    self.toggleButton.setObjectName("startNodeButton")
    self.toggleButton.setToolTip(TOGGLE_NODE_TOOLTIP)
    self.toggleButton.clicked.connect(self.toggle_container)
    self.apply_button_style(self.toggleButton, 'toggle_start')
    top_button_area.addWidget(self.toggleButton)

    top_button_area.addWidget(self.create_sidebar_section_label("Network", "networkActionsSectionLabel"))

    self.docker_download_button = QPushButton(DOWNLOAD_DOCKER_BUTTON_TEXT)
    self.docker_download_button.setObjectName("downloadDockerButton")
    self.docker_download_button.setToolTip(DOCKER_DOWNLOAD_TOOLTIP)
    self.docker_download_button.clicked.connect(self.open_docker_download)
    top_button_area.addWidget(self.docker_download_button)

    self.dapp_button = QPushButton(DAPP_BUTTON_TEXT)
    self.dapp_button.setObjectName("openDappButton")
    self.dapp_button.setToolTip(DAPP_TOOLTIP)
    self.dapp_button.clicked.connect(self.dapp_button_clicked)
    top_button_area.addWidget(self.dapp_button)

    self.explorer_button = QPushButton(EXPLORER_BUTTON_TEXT)
    self.explorer_button.setObjectName("openExplorerButton")
    self.explorer_button.setToolTip(EXPLORER_TOOLTIP)
    self.explorer_button.clicked.connect(self.explorer_button_clicked)
    top_button_area.addWidget(self.explorer_button)

    top_button_area.addSpacing(7)
    top_button_area.addWidget(self.create_sidebar_section_label("Status", "statusSectionLabel"))

    self.refreshButton = QPushButton("Refresh Node Info")
    self.refreshButton.setObjectName("refreshNodeInfoButton")
    self.refreshButton.clicked.connect(self.force_refresh_all)
    self.refreshButton.setToolTip(REFRESH_NODE_INFO_TOOLTIP)
    top_button_area.addWidget(self.refreshButton)

    top_button_area.addSpacing(7)
    top_button_area.addWidget(self._create_node_status_panel())
    top_button_area.addSpacing(7)
    top_button_area.addWidget(self._create_resource_status_panel())

    menu_layout.addLayout(top_button_area)
    menu_layout.addStretch(1)
    menu_layout.addLayout(self._create_sidebar_settings_section())

    return menu_widget

  def _create_node_status_panel(self) -> QGroupBox:
    info_box = QGroupBox()
    info_box.setObjectName("infoBox")
    info_box.setProperty("role", "statusPanel")
    info_box.setContentsMargins(5, 0, 5, 0)

    info_box_layout = QVBoxLayout()
    info_box_layout.setContentsMargins(5, 6, 5, 8)

    self.loading_indicator = LoadingIndicator(size=30)
    self.loading_indicator.hide()
    loading_layout = QHBoxLayout()
    loading_layout.addStretch()
    loading_layout.addWidget(self.loading_indicator)
    loading_layout.addStretch()
    info_box_layout.addLayout(loading_layout)

    addr_layout = QHBoxLayout()
    self.addressDisplay = QLabel('')
    self.addressDisplay.setFont(QFont("Courier New"))
    self.addressDisplay.setObjectName("infoBoxText")
    addr_layout.addWidget(self.addressDisplay)

    self.copyAddrButton = QPushButton()
    self.copyAddrButton.setToolTip(COPY_ADDRESS_TOOLTIP)
    self.copyAddrButton.clicked.connect(self.copy_address)
    self.copyAddrButton.setFixedSize(28, 28)
    self.copyAddrButton.setObjectName("copyAddrButton")
    self.copyAddrButton.hide()
    addr_layout.addWidget(self.copyAddrButton)
    addr_layout.addStretch()
    info_box_layout.addLayout(addr_layout)

    eth_addr_layout = QHBoxLayout()
    self.ethAddressDisplay = QLabel('')
    self.ethAddressDisplay.setObjectName("infoBoxText")
    self.ethAddressDisplay.setFont(QFont("Courier New"))
    eth_addr_layout.addWidget(self.ethAddressDisplay)

    self.copyEthButton = QPushButton()
    self.copyEthButton.setToolTip(COPY_ETH_ADDRESS_TOOLTIP)
    self.copyEthButton.clicked.connect(self.copy_eth_address)
    self.copyEthButton.setFixedSize(28, 28)
    self.copyEthButton.setObjectName("copyEthButton")
    self.copyEthButton.hide()
    eth_addr_layout.addWidget(self.copyEthButton)
    eth_addr_layout.addStretch()
    info_box_layout.addLayout(eth_addr_layout)

    self.nameDisplay = QLabel('')
    self.nameDisplay.setFont(QFont("Courier New"))
    self.nameDisplay.setObjectName("infoBoxText")
    info_box_layout.addWidget(self.nameDisplay)

    self.node_uptime = QLabel(UPTIME_LABEL)
    self.node_uptime.setObjectName("infoBoxText")
    self.node_uptime.setFont(QFont("Courier New"))
    info_box_layout.addWidget(self.node_uptime)

    self.node_epoch = QLabel(EPOCH_LABEL)
    self.node_epoch.setObjectName("infoBoxText")
    self.node_epoch.setFont(QFont("Courier New"))
    info_box_layout.addWidget(self.node_epoch)

    self.node_epoch_avail = QLabel(EPOCH_AVAIL_LABEL)
    self.node_epoch_avail.setObjectName("infoBoxText")
    self.node_epoch_avail.setFont(QFont("Courier New"))
    info_box_layout.addWidget(self.node_epoch_avail)

    self.node_version = QLabel()
    self.node_version.setObjectName("infoBoxText")
    self.node_version.setFont(QFont("Courier New"))
    info_box_layout.addWidget(self.node_version)

    info_box.setLayout(info_box_layout)
    return info_box

  def _create_resource_status_panel(self) -> QGroupBox:
    resources_box = QGroupBox()
    resources_box.setObjectName("resourcesBox")
    resources_box.setProperty("role", "resourcePanel")
    resources_box.setContentsMargins(5, 0, 5, 0)

    resources_box_layout = QVBoxLayout()
    resources_box_layout.setContentsMargins(5, 6, 5, 8)

    self.memoryDisplay = QLabel(MEMORY_LABEL + ' ' + MEMORY_NOT_AVAILABLE)
    self.memoryDisplay.setFont(QFont("Courier New"))
    self.memoryDisplay.setObjectName("resourcesBoxText")
    self.memoryDisplay.setWordWrap(True)
    self.memoryDisplay.setMaximumWidth(270)
    self.memoryDisplay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    resources_box_layout.addWidget(self.memoryDisplay)

    self.vcpusDisplay = QLabel(VCPUS_LABEL + ' ' + VCPUS_NOT_AVAILABLE)
    self.vcpusDisplay.setFont(QFont("Courier New"))
    self.vcpusDisplay.setObjectName("resourcesBoxText")
    self.vcpusDisplay.setWordWrap(True)
    self.vcpusDisplay.setMaximumWidth(270)
    self.vcpusDisplay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    resources_box_layout.addWidget(self.vcpusDisplay)

    self.storageDisplay = QLabel(STORAGE_LABEL + ' ' + STORAGE_NOT_AVAILABLE)
    self.storageDisplay.setFont(QFont("Courier New"))
    self.storageDisplay.setObjectName("resourcesBoxText")
    self.storageDisplay.setWordWrap(True)
    self.storageDisplay.setMaximumWidth(270)
    self.storageDisplay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    resources_box_layout.addWidget(self.storageDisplay)

    resources_box.setLayout(resources_box_layout)
    return resources_box

  def _create_sidebar_settings_section(self) -> QVBoxLayout:
    bottom_button_area = QVBoxLayout()
    bottom_button_area.setObjectName("bottomButtonArea")
    bottom_button_area.setContentsMargins(5, 4, 5, 0)
    bottom_button_area.addWidget(self.create_sidebar_section_label("Settings", "settingsSectionLabel"))

    self.themeToggleButton = QPushButton(LIGHT_DASHBOARD_BUTTON_TEXT)
    self.themeToggleButton.setObjectName("themeToggleButton")
    self.themeToggleButton.setToolTip(THEME_TOGGLE_TOOLTIP)
    self.themeToggleButton.clicked.connect(self.toggle_theme)
    bottom_button_area.addWidget(self.themeToggleButton)

    self.force_debug_checkbox = QCheckBox('Force Debug Mode')
    self.force_debug_checkbox.setObjectName("forceDebugCheckbox")
    self.force_debug_checkbox.setToolTip(FORCE_DEBUG_TOOLTIP)
    self.force_debug_checkbox.setChecked(self.__force_debug)
    self.force_debug_checkbox.setFont(QFont("Courier New", 9, QFont.Bold))

    is_dark = self._current_stylesheet == DARK_STYLESHEET
    if is_dark:
        self.force_debug_checkbox.setStyleSheet(DETAILED_CHECKBOX_STYLE.format(
            debug_checkbox_color=DARK_COLORS["debug_checkbox_color"]
        ))
    else:
        self.force_debug_checkbox.setStyleSheet(DETAILED_CHECKBOX_STYLE.format(
            debug_checkbox_color=LIGHT_COLORS["debug_checkbox_color"]
        ))

    self.force_debug_checkbox.stateChanged.connect(self.toggle_force_debug)
    bottom_button_area.addWidget(self.force_debug_checkbox)
    bottom_button_area.addStretch()

    return bottom_button_area

  def initUI(self):
    self.setWindowTitle(WINDOW_TITLE)
    self.apply_initial_window_geometry()

    # Set the icon right at the beginning
    self.setWindowIcon(self._icon)
    self.set_windows_taskbar_icon()

    # Create the main layout
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(10, 10, 10, 10)  # Add padding around the entire window content
    main_layout.setSpacing(0)

    # Content area with overlay for mode switch
    content_widget = QWidget()
    content_widget.setLayout(QHBoxLayout())
    content_widget.layout().setContentsMargins(0, 0, 0, 0)
    content_widget.layout().setSpacing(0)

    menu_widget = self._create_sidebar_panel()
    right_container = self._create_right_dashboard_container()
    
    # Add the main content widgets
    content_widget.layout().addWidget(self._create_sidebar_scroll_area(menu_widget))
    content_widget.layout().addWidget(right_container)
    
    main_layout.addWidget(content_widget)

    self.setLayout(main_layout)
    self.apply_stylesheet()

    return
  
  def toggle_theme(self):
    if self._current_stylesheet == DARK_STYLESHEET:
        self._current_stylesheet = LIGHT_STYLESHEET
        self.themeToggleButton.setText(DARK_DASHBOARD_BUTTON_TEXT)
        self.force_debug_checkbox.setProperty('class', 'light')
        is_dark = False
    else:
        self._current_stylesheet = DARK_STYLESHEET
        self.themeToggleButton.setText(LIGHT_DASHBOARD_BUTTON_TEXT)
        self.force_debug_checkbox.setProperty('class', 'dark')
        is_dark = True
    
    # Update button colors for the new theme
    self.init_button_colors()
    
    # Update copy button icons for the new theme
    self.update_copy_button_icons()
    
    self.apply_stylesheet()
    self.plot_graphs()
    
    # Update the toggle button styling for theme change
    self.update_toggle_button_text()
    
    # Also directly re-apply the current button style to ensure it updates
    current_text = self.toggleButton.text()
    if current_text == LAUNCH_CONTAINER_BUTTON_TEXT:
        self.apply_button_style(self.toggleButton, 'toggle_start')
    elif current_text == STOP_CONTAINER_BUTTON_TEXT:
        self.apply_button_style(self.toggleButton, 'toggle_stop')
    
    # Apply theme to the combobox dropdown using the new method
    if hasattr(self.container_combo, 'set_theme'):
        self.container_combo.set_theme(is_dark)
    elif hasattr(self.container_combo, 'apply_default_theme'):
        self.container_combo.apply_default_theme()
    
    # Force style update
    self.force_debug_checkbox.style().unpolish(self.force_debug_checkbox)
    self.force_debug_checkbox.style().polish(self.force_debug_checkbox)

    # Update resources display for theme consistency
    self.update_resources_display()

  @staticmethod
  def _qt_object_deleted(obj) -> bool:
    """Return True when a Qt wrapper no longer owns a live C++ object."""
    if obj is None:
      return True

    try:
      return sip.isdeleted(obj)
    except (RuntimeError, TypeError):
      return True

  def _clear_dialog_reference(self, dialog_attr: str, dialog=None) -> None:
    """Clear a dialog attribute when it still points at the supplied dialog."""
    if not hasattr(self, dialog_attr):
      return

    try:
      current_dialog = getattr(self, dialog_attr)
    except RuntimeError:
      setattr(self, dialog_attr, None)
      return

    if dialog is None or current_dialog is dialog:
      setattr(self, dialog_attr, None)

  def _close_dialog_reference(self, dialog_attr: str) -> bool:
    """Close a stored dialog reference, tolerating already-deleted Qt wrappers."""
    if not hasattr(self, dialog_attr):
      return False

    try:
      dialog = getattr(self, dialog_attr)
    except RuntimeError:
      setattr(self, dialog_attr, None)
      self.add_log(f"Cleared deleted {dialog_attr}", debug=True)
      return False

    if dialog is None:
      return False

    if self._qt_object_deleted(dialog):
      setattr(self, dialog_attr, None)
      self.add_log(f"Cleared deleted {dialog_attr}", debug=True)
      return False

    try:
      dialog.close()
      self._clear_dialog_reference(dialog_attr, dialog)
      self.add_log(f"Closed {dialog_attr}", debug=True)
      return True
    except RuntimeError as e:
      if "wrapped C/C++ object" in str(e):
        setattr(self, dialog_attr, None)
        self.add_log(f"Cleared deleted {dialog_attr}", debug=True)
        return False
      self.add_log(f"Error closing {dialog_attr}: {str(e)}", debug=True)
      return False

  def _is_shutting_down(self) -> bool:
    return getattr(self, "_EdgeNodeLauncher__shutting_down", False)

  def _skip_lifecycle_callback_if_shutting_down(self, callback_name: str, container_name: str = None) -> bool:
    """Return True when a late async callback should not mutate UI state."""
    if not self._is_shutting_down():
      return False

    target = f" for {container_name}" if container_name else ""
    self.add_log(f"Ignoring {callback_name}{target}; shutdown is in progress", debug=True)
    if container_name:
      self._end_lifecycle_operation(container_name)
    return True

  def closeEvent(self, event):
    """Handle application close event with proper cleanup."""
    try:
        self.__shutting_down = True
        self.add_log("Starting application shutdown sequence...", debug=True)
        self._save_main_window_geometry()
        
        # Stop any running timers first
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
            self.add_log("Stopped main refresh timer", debug=True)
        
        # Stop any loading indicators
        if hasattr(self, 'loading_indicator') and self.loading_indicator:
            self.loading_indicator.stop()
            self.add_log("Stopped loading indicators", debug=True)
        
        # Close any open dialogs forcefully
        dialog_attrs = ['startup_dialog', 'launcher_dialog', 'toggle_dialog', 'docker_pull_dialog']
        for dialog_attr in dialog_attrs:
            self._close_dialog_reference(dialog_attr)
        
        # Force close any remaining child widgets
        try:
            for child in self.findChildren(QDialog):
                if not self._qt_object_deleted(child) and child.isVisible():
                    child.close()
                    self.add_log(f"Force closed dialog: {type(child).__name__}", debug=True)
        except Exception as e:
            self.add_log(f"Error force closing dialogs: {str(e)}", debug=True)
        
        # Process any remaining events
        try:
            QApplication.processEvents()
            self.add_log("Processed remaining events", debug=True)
        except:
            pass
        
        self.add_log("Application shutdown completed successfully", debug=True)
        
    except Exception as e:
        self.add_log(f"Error during application close: {str(e)}", debug=True)
        # Continue with shutdown even if there are errors
    
    # Always accept the close event to ensure shutdown
    event.accept()

  def force_application_exit(self):
    """Force the application to exit immediately - used during updates."""
    try:
        self.__shutting_down = True
        self.add_log("FORCE EXIT: Initiating immediate application shutdown for update", color="yellow")
        
        # Stop only GUI timers
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
        
        # Close all windows
        app = QApplication.instance()
        if app:
            app.closeAllWindows()
        
        # Force exit at OS level (only this GUI process)
        import os
        import signal
        
        if os.name == 'nt':  # Windows
            try:
                import subprocess
                current_pid = os.getpid()
                # Kill only our GUI process
                subprocess.run(['taskkill', '/F', '/PID', str(current_pid)], 
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except:
                os._exit(0)
        else:
            # Unix systems
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except:
                os._exit(0)
                
    except:
        # Absolute last resort
        import os
        os._exit(0)

  def update_copy_button_icons(self):
    """Update the copy button icons based on the current theme."""
    try:
      # Import the icon module - handle both relative and absolute imports
      try:
        # Try relative import first (works in development)
        import sys
        from pathlib import Path
        
        # Add parent directory to path if needed
        parent_dir = Path(__file__).resolve().parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.append(str(parent_dir))
            
        from app_icons import get_copy_icon
      except ImportError:
        # Fallback for packaged app
        from app_icons import get_copy_icon
        
      # Determine if we're using light theme
      is_light_theme = self._current_stylesheet == LIGHT_STYLESHEET
      
      # Get the icon with appropriate color
      copy_icon = get_copy_icon(is_light_theme)
      
      # Set icon size
      icon_size = QSize(20, 20)
      
      # Apply to buttons
      self.copyAddrButton.setIcon(copy_icon)
      self.copyAddrButton.setIconSize(icon_size)
      self.copyEthButton.setIcon(copy_icon)
      self.copyEthButton.setIconSize(icon_size)
      
    except Exception as e:
      # Log error and fallback to text
      self.add_log(f"Error setting copy icons: {str(e)}", debug=True)
      
      # Fallback to system icon if there's an error
      try:
        default_icon = self.style().standardIcon(QStyle.SP_DialogSaveButton)
        self.copyAddrButton.setIcon(default_icon)
        self.copyAddrButton.setIconSize(QSize(20, 20))
        self.copyEthButton.setIcon(default_icon)
        self.copyEthButton.setIconSize(QSize(20, 20))
      except:
        # Last resort fallback to text
        self.copyAddrButton.setText("Copy")
        self.copyEthButton.setText("Copy")

  def change_text_color(self):
    if self._current_stylesheet == DARK_STYLESHEET:
      self.force_debug_checkbox.setStyleSheet(DETAILED_CHECKBOX_STYLE.format(debug_checkbox_color=DARK_COLORS["debug_checkbox_color"]))
    else:
      self.force_debug_checkbox.setStyleSheet(DETAILED_CHECKBOX_STYLE.format(debug_checkbox_color=LIGHT_COLORS["debug_checkbox_color"]))

  def apply_stylesheet(self):
    is_dark = self._current_stylesheet == DARK_STYLESHEET
    self.change_text_color()

    # Apply larger font size for info box labels on macOS
    if platform.system().lower() == 'darwin':
      # Additional macOS-specific styles
      macos_style = """
        #infoBox QLabel {
          font-size: 12pt !important;
        }
        #infoBoxText QLabel {
          font-size: 12pt !important;
        }
        QComboBox QAbstractItemView {
          min-width: 254px !important; /* Wider dropdown on macOS */
        }
      """
      # Apply base stylesheet plus macOS modifications
      self.setStyleSheet(self._current_stylesheet + macos_style)
      
      # Apply margin directly to logView with its own stylesheet
      self.logView.setStyleSheet("""
        QTextEdit#logView {
          margin-bottom: 6px;
        }
      """)
    else:
      # Apply regular stylesheet for other platforms
      self.setStyleSheet(self._current_stylesheet)
      self.logView.setStyleSheet("")
    
    # Reset plot backgrounds
    self.cpu_plot.setBackground(None)
    self.memory_plot.setBackground(None)
    self.gpu_plot.setBackground(None)
    self.gpu_memory_plot.setBackground(None)

  def toggle_container(self):
    """Toggle the Docker container state (start/stop)."""
    try:
        # Get the current container name
        container_name = self.docker_handler.container_name
        
        # Check if container is running
        is_running = self.is_container_running()
        
        if is_running:
            # Container is running, stop it
            self._stop_container()
        else:
            # Container is not running, start it
            self._start_container()
            
    except Exception as e:
        self.add_log(f"Error toggling container: {str(e)}", color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Error toggling container: {str(e)}")

  def _stop_container(self):
    """Stop the Docker container."""
    try:
        # Get the current container name
        container_name = self.docker_handler.container_name
        self._begin_lifecycle_operation("stop", container_name)
        
        # Get node alias from config if available for better user feedback
        node_display_name = container_name
        container_config = self.config_manager.get_container(container_name)
        if container_config and container_config.node_alias:
            node_display_name = container_config.node_alias
            message = f"Please wait while node '{node_display_name}' is being stopped..."
        else:
            message = "Please wait while Edge Node is being stopped..."
            
        # Show loading dialog for stopping operation
        self.toggle_dialog = LoadingDialog(
            self, 
            title="Stopping Node", 
            message=message,
            size=50
        )
        self.toggle_dialog.show()
        
        # Update message to indicate starting the stop process
        self.toggle_dialog.update_progress("Preparing to stop Docker container...")
        
        # Clear info displays
        self._clear_info_display()
        self.loading_indicator.start()
        
        # Update loading dialog with progress
        if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible():
            self.toggle_dialog.update_progress("Stopping Docker container...")
        
        # Define success callback for threaded operation
        def on_stop_success(result):
            stdout, stderr, return_code = result
            if return_code != 0:
                # Handle error case
                error_msg = f"Failed to stop container: {stderr}"
                self._end_lifecycle_operation(container_name)
                self.add_log(error_msg, color="red")
                self.toast.show_notification(NotificationType.ERROR, error_msg)
                return
            
            # Mark that user intentionally stopped the container to prevent auto-restart
            self.user_stopped_container = True
            
            # Update loading dialog with progress    
            if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible():
                self.toggle_dialog.update_progress("Container stopped, updating UI...")
                
            # Clear and update all UI elements
            self.update_toggle_button_text()
            self.refresh_node_info()  # Updates address displays with cached data
            self.maybe_refresh_uptime()   # Updates uptime displays
            self.plot_data()              # Clears plots
            
            # Stop loading indicator
            self.loading_indicator.stop()
            
            # Update loading dialog with completion message
            if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible():
                self.toggle_dialog.update_progress("Container stopped successfully!")
                
            # Close the loading dialog after a short delay to show success message
            toggle_dialog_visible = hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible()
            if toggle_dialog_visible:
                QTimer.singleShot(500, lambda: self.toggle_dialog.safe_close() if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None else None)
                # Schedule removal of the reference after a delay
                QTimer.singleShot(1000, lambda: setattr(self, 'toggle_dialog', None) if hasattr(self, 'toggle_dialog') else None)
            
            # Process events to ensure immediate UI update
            QApplication.processEvents()
            
            # Show success notification
            # Get node alias from config if available
            node_display_name = container_name
            container_config = self.config_manager.get_container(container_name)
            if container_config and container_config.node_alias:
                node_display_name = container_config.node_alias
                self.toast.show_notification(NotificationType.SUCCESS, f"Node '{node_display_name}' stopped successfully")
            else:
                self.toast.show_notification(NotificationType.SUCCESS, "Edge Node stopped successfully")
            self._end_lifecycle_operation(container_name)
        
        # Define error callback for threaded operation
        def on_stop_error(error_msg):
            # Stop loading indicator in case of error
            self.loading_indicator.stop()
            
            # Update loading dialog with error message
            if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible():
                self.toggle_dialog.update_progress(f"Error: {error_msg}")
                
            # Close the loading dialog after a short delay to show error message
            toggle_dialog_visible = hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible()
            if toggle_dialog_visible:
                QTimer.singleShot(1500, lambda: self.toggle_dialog.safe_close() if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None else None)
                # Schedule removal of the reference after a delay
                QTimer.singleShot(2000, lambda: setattr(self, 'toggle_dialog', None) if hasattr(self, 'toggle_dialog') else None)
                
            self.add_log(f"Error stopping container: {error_msg}", color="red")
            self.toast.show_notification(NotificationType.ERROR, f"Error stopping container: {error_msg}")
            self._end_lifecycle_operation(container_name)
        
        # Pass the container name explicitly to ensure we're stopping the right one
        self.docker_handler.stop_container_threaded(container_name, on_stop_success, on_stop_error)
        
    except Exception as e:
        # Stop loading indicator in case of error
        self.loading_indicator.stop()
        
        # Update loading dialog with error message
        if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible():
            self.toggle_dialog.update_progress(f"Error: {str(e)}")
            
        # Close the loading dialog after a short delay to show error message
        toggle_dialog_visible = hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None and self.toggle_dialog.isVisible()
        if toggle_dialog_visible:
            QTimer.singleShot(1500, lambda: self.toggle_dialog.safe_close() if hasattr(self, 'toggle_dialog') and self.toggle_dialog is not None else None)
            # Schedule removal of the reference after a delay
            QTimer.singleShot(2000, lambda: setattr(self, 'toggle_dialog', None) if hasattr(self, 'toggle_dialog') else None)
            
        self.add_log(f"Error stopping container: {str(e)}", color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Error stopping container: {str(e)}")
        if 'container_name' in locals():
            self._end_lifecycle_operation(container_name)

  def _start_container(self):
    """Start the Docker container."""
    try:
        # Get the current container name
        container_name = self.docker_handler.container_name
        self._begin_lifecycle_operation("start", container_name)
        
        # Get volume name from config or generate one
        volume_name = None
        container_config = self.config_manager.get_container(container_name)
        if container_config:
            volume_name = container_config.volume
            self.add_log(f"Using existing volume name from config: {volume_name}", debug=True)
        else:
            volume_name = get_volume_name(container_name)
            self.add_log(f"Generated volume name: {volume_name}", debug=True)
        
        # Mark that user intentionally started the container (clear stop flag)
        self.user_stopped_container = False
        
        # Get node alias from config if available for better user feedback
        node_display_name = container_name
        container_config = self.config_manager.get_container(container_name)
        if container_config and container_config.node_alias:
            node_display_name = container_config.node_alias
            message = f"Please wait while node '{node_display_name}' is being launched..."
        else:
            message = "Please wait while Edge Node is being launched..."
            
        # Show loading dialog for launching operation
        self.launcher_dialog = LoadingDialog(
            self, 
            title="Launching Node", 
            message=message,
            size=50
        )
        self.launcher_dialog.show()
        
        # Update message to indicate starting the launch process
        self.launcher_dialog.update_progress("Preparing to launch Docker container...")
        
        # Process events to ensure dialog is visible and responsive
        QApplication.processEvents()
        
        # Start the container launch process
        self._perform_container_launch(container_name, volume_name)
        
    except Exception as e:
        # Stop loading indicator on error
        self.loading_indicator.stop()
        
        # Close the launcher dialog if it exists
        launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
        if launcher_dialog_visible:
            self.launcher_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
        self.add_log(f"Error launching container: {str(e)}", color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Error launching container: {str(e)}")
        if 'container_name' in locals():
            self._end_lifecycle_operation(container_name)

  def plot_data(self, assume_running: Optional[bool] = None):
    """Plot container metrics data."""
    # Skip plotting if Docker pull is in progress to avoid conflicts
    if self._docker_pull_in_progress():
        self.add_log("Docker pull in progress, skipping plot data", debug=True)
        return
        
    # Use combo item data for Docker identity; currentText may be a display alias.
    container_name = self._selected_container_name()
    if not container_name:
        self.add_log("No container selected, cannot plot data", debug=True)
        return
        
    # Make sure we're working with the correct container
    self.docker_handler.set_container_name(container_name)
    
    if assume_running is None:
        is_running = self.is_container_running()
    else:
        is_running = assume_running

    if not is_running:
        self.add_log(f"Container {container_name} is not running, skipping plot data", debug=True)
        return

    def on_success(history: NodeHistory) -> None:
        # Make sure we're still on the same container
        current_selected = self._selected_container_name()
        if container_name != current_selected:
            self.add_log(f"Container changed during data plotting from {container_name} to {current_selected}, ignoring results", debug=True)
            return
            
        self.__last_plot_data = history
        self.plot_graphs()
        
        # Update uptime and other metrics only for the currently selected container
        self.__current_node_uptime = history.uptime
        self.__current_node_epoch = history.current_epoch
        self.__current_node_epoch_avail = history.current_epoch_avail
        self.__current_node_ver = history.version
        
        self.maybe_refresh_uptime(assume_running=True)
        self.add_log(f"Updated metrics for container {container_name}", debug=True)

    def on_error(error):
        # Make sure we're still on the same container
        if container_name != self._selected_container_name():
            self.add_log(f"Container changed during data plotting, ignoring error", debug=True)
            return
            
        self.add_log(f'Error getting metrics for {container_name}: {error}', debug=True)
        
        # If this is a timeout error, log it more prominently
        if "timed out" in error.lower():
            self.add_log(f"Metrics request for {container_name} timed out. This may indicate network issues or high load on the remote host.", color="red")

    try:
        self.add_log(f"Plotting data for container: {container_name}", debug=True)
        self.docker_handler.get_node_history(on_success, on_error)
    except Exception as e:
        self.add_log(f"Failed to start metrics request for {container_name}: {str(e)}", debug=True, color="red")
        on_error(str(e))

  def plot_graphs(self, history: Optional[NodeHistory] = None, limit: int = 100) -> None:
    """Plot the graphs with the given history data.
    
    Args:
        history: The history data to plot. If None, use the last data.
        limit: The maximum number of points to plot.
    """
    # Get the currently selected container
    container_name = self.container_combo.currentText()
    if not container_name:
        self.add_log("No container selected, cannot plot graphs", debug=True)
        return
     
    # Use provided history or last data
    if history is None:
       history = self.__last_plot_data
     
    if history is None:
        self.add_log(f"No history data available for container {container_name}", debug=True)
        return
    
    # Make sure we have timestamps
    if not history.timestamps or len(history.timestamps) == 0:
        self.add_log(f"No timestamps in history data for container {container_name}", debug=True)
        return
    
    # Clean and limit data
    timestamps = history.timestamps
    if len(timestamps) > limit:
        timestamps = timestamps[-limit:]
     
    # Get colors based on theme
    colors = DARK_COLORS if self._current_stylesheet == DARK_STYLESHEET else LIGHT_COLORS
    
    # Helper function to update a plot
    def update_plot(plot_widget, timestamps, data, name, color):
        plot_widget.clear()
        if data and len(data) > 0:
            # Ensure data length matches timestamps
            if len(data) > len(timestamps):
                data = data[-len(timestamps):]
            elif len(data) < len(timestamps):
                # Pad with zeros if needed
                data = [0] * (len(timestamps) - len(data)) + data
            
            # Convert string timestamps to numeric values for plotting
            numeric_timestamps = []
            for ts in timestamps:
                try:
                    if isinstance(ts, str):
                        # Convert ISO format string to timestamp
                        numeric_timestamps.append(datetime.fromisoformat(ts).timestamp())
                    else:
                        numeric_timestamps.append(float(ts))
                except (ValueError, TypeError):
                    # If conversion fails, use the index as a fallback
                    self.add_log(f"Failed to convert timestamp: {ts}", debug=True)
                    numeric_timestamps.append(len(numeric_timestamps))
            
            # Plot with numeric timestamps
            plot_widget.plot(numeric_timestamps, data, pen=color, name=name)
    
    # CPU Plot
    cpu_date_axis = DateAxisItem(orientation='bottom')
    cpu_date_axis.setTimestamps(timestamps, parent="cpu")
    self.cpu_plot.getAxis('bottom').setTickSpacing(60, 10)
    self.cpu_plot.getAxis('bottom').setStyle(tickTextOffset=10)
    self.cpu_plot.setAxisItems({'bottom': cpu_date_axis})
    self.cpu_plot.setTitle(CPU_LOAD_TITLE)
    update_plot(self.cpu_plot, timestamps, history.cpu_load, 'CPU Load', colors["graph_cpu_color"])
    
    # Memory Plot
    mem_date_axis = DateAxisItem(orientation='bottom')
    mem_date_axis.setTimestamps(timestamps, parent="mem")
    self.memory_plot.getAxis('bottom').setTickSpacing(60, 10)
    self.memory_plot.getAxis('bottom').setStyle(tickTextOffset=10)
    self.memory_plot.setAxisItems({'bottom': mem_date_axis})
    self.memory_plot.setTitle(MEMORY_USAGE_TITLE)
    update_plot(self.memory_plot, timestamps, history.occupied_memory, 'Occupied Memory', colors["graph_memory_color"])
    
    # GPU Plot if available
    if history and history.gpu_load:
      gpu_date_axis = DateAxisItem(orientation='bottom')
      gpu_date_axis.setTimestamps(timestamps, parent="gpu")
      self.gpu_plot.getAxis('bottom').setTickSpacing(60, 10)
      self.gpu_plot.getAxis('bottom').setStyle(tickTextOffset=10)
      self.gpu_plot.setAxisItems({'bottom': gpu_date_axis})
      self.gpu_plot.setTitle(GPU_LOAD_TITLE)
      update_plot(self.gpu_plot, timestamps, history.gpu_load, 'GPU Load', colors["graph_gpu_color"])

    # GPU Memory if available
    if history and history.gpu_occupied_memory:
      gpumem_date_axis = DateAxisItem(orientation='bottom')
      gpumem_date_axis.setTimestamps(timestamps, parent="gpu_mem")
      self.gpu_memory_plot.getAxis('bottom').setTickSpacing(60, 10)
      self.gpu_memory_plot.getAxis('bottom').setStyle(tickTextOffset=10)
      self.gpu_memory_plot.setAxisItems({'bottom': gpumem_date_axis})
      self.gpu_memory_plot.setTitle(GPU_MEMORY_LOAD_TITLE)
      update_plot(self.gpu_memory_plot, timestamps, history.gpu_occupied_memory, 'Occupied GPU Memory', colors["graph_gpu_memory_color"])
      
    self.add_log(f"Updated graphs for container {container_name} with {len(timestamps)} data points", debug=True)

  def update_plot(plot_widget, timestamps, data, name, color):
    """Update a plot with the given data."""
    plot_widget.setTitle(name)

  def refresh_node_info(self):
    """Refresh the node information by fetching fresh data from the container and updating the UI."""
    # Skip refresh if Docker pull is in progress to avoid conflicts
    if self._docker_pull_in_progress():
        self.add_log("Docker pull in progress, skipping node info refresh", debug=True)
        return
        
    selection = self._selected_container()
    if selection is None:
      self._update_ui_no_container()
      return
    container_name = selection.name

    # Make sure we're working with the correct container
    self.docker_handler.set_container_name(container_name)

    # Check if container is running - if not, show cached data or appropriate messages
    if not self.is_container_running():
      self._update_ui_container_not_running(container_name)
      return

    # Container is running - get fresh node info
    self.add_log(f"Getting node information for {container_name}", debug=True)
    
    def on_success(node_info: NodeInfo) -> None:
      # Reset failure counter on successful request
      if self.node_info_failure_count > 0:
        self.add_log(f"Node info request succeeded after {self.node_info_failure_count} failures, resetting counter", debug=True)
        self.node_info_failure_count = 0
      
      # Update UI with fresh node info data
      self._update_ui_with_fresh_data(node_info, container_name)

    def on_error(error):
      # Increment failure counter
      self.node_info_failure_count += 1
      self.add_log(f"Node info request failed ({self.node_info_failure_count}/{NODE_INFO_FAILURE_THRESHOLD}): {error}", color="yellow")
      
      # Check if we need to restart the container after consecutive failures
      if self.node_info_failure_count >= NODE_INFO_FAILURE_THRESHOLD:
        if self._should_restart_after_node_info_failure(container_name):
          self.add_log(f"Node info failed {NODE_INFO_FAILURE_THRESHOLD} times for {container_name}, restarting container", color="red")
          self._restart_container_after_failures(container_name)
        else:
          self.add_log(f"Node info failed {NODE_INFO_FAILURE_THRESHOLD} times for {container_name}, but auto-restart was skipped", color="yellow")
          self.node_info_failure_count = 0
        return
      
      # Handle error by falling back to cached data or showing error messages
      self._handle_node_info_error(error, container_name)

    # Get node info from the container
    self.docker_handler.get_node_info(on_success, on_error)

  def _selected_container_name(self) -> Optional[str]:
    """Return the selected Docker container name, not the display alias."""
    selection = self._selected_container()
    return selection.name if selection else None

  def _selected_container(self) -> Optional[SelectedContainer]:
    """Return selected container identity, with item data as the Docker id."""
    return selected_container_from_combo(self.container_combo)

  def _select_container_by_name(self, container_name: str) -> bool:
    """Select a configured container by Docker name."""
    return select_container_by_name(self.container_combo, container_name)

  def _sync_lifecycle_state_snapshot(self) -> None:
    """Keep legacy diagnostic fields in sync while lifecycle state is extracted."""
    self.__active_lifecycle_operation = self.__lifecycle_state.active_operation_dict()
    self.__pending_launch_context = self.__lifecycle_state.pending_launch_context_dict()
    self.__docker_pull_in_progress = self.__lifecycle_state.docker_pull_in_progress

  def _active_lifecycle_operation(self) -> Optional[dict]:
    return self.__lifecycle_state.active_operation_dict()

  def _pending_launch_context(self) -> Optional[dict]:
    return self.__lifecycle_state.pending_launch_context_dict()

  def _docker_pull_in_progress(self) -> bool:
    return self.__lifecycle_state.docker_pull_in_progress

  def _begin_lifecycle_operation(self, operation: str, container_name: str) -> None:
    """Mark that a user-visible lifecycle operation is in progress."""
    self.__lifecycle_state.begin_operation(operation, container_name)
    self._sync_lifecycle_state_snapshot()
    self.add_log(f"Lifecycle operation started: {operation} on {container_name}", debug=True)

  def _end_lifecycle_operation(self, container_name: str = None) -> None:
    """Clear an active lifecycle operation when its owning flow completes."""
    ended = self.__lifecycle_state.end_operation(container_name)
    self._sync_lifecycle_state_snapshot()
    if ended is None:
      return
    self.add_log(f"Lifecycle operation finished: {ended.operation} on {ended.container_name}", debug=True)

  def _start_docker_pull(self, container_name: str, volume_name: str) -> None:
    self.__lifecycle_state.start_docker_pull(container_name, volume_name)
    self._sync_lifecycle_state_snapshot()

  def _finish_docker_pull(self) -> Optional[dict]:
    context = self.__lifecycle_state.finish_docker_pull()
    self._sync_lifecycle_state_snapshot()
    return context.to_dict() if context else None

  def _should_restart_after_node_info_failure(self, container_name: str) -> bool:
    """Guard automatic restarts so stale callbacks cannot affect another node."""
    blocker = self.__lifecycle_state.auto_restart_blocker(
      container_name,
      self._selected_container_name(),
      self.user_stopped_container,
    )

    if blocker == "active_operation":
      active = self._active_lifecycle_operation()
      self.add_log(
        f"Skipping auto-restart for {container_name}; lifecycle operation {active.get('operation')} is active on {active.get('container_name')}",
        debug=True,
        color="yellow",
      )
      return False

    if blocker == "stale_selection":
      selected_container = self._selected_container_name()
      self.add_log(
        f"Skipping auto-restart for stale node info failure on {container_name}; selected container is {selected_container}",
        debug=True,
        color="yellow",
      )
      return False

    if blocker == "launch_in_progress":
      self.add_log(
        f"Skipping auto-restart for {container_name}; a launch or Docker pull is already in progress",
        debug=True,
        color="yellow",
      )
      return False

    if blocker == "user_stopped":
      self.add_log(
        f"Skipping auto-restart for {container_name}; user intentionally stopped the container",
        debug=True,
        color="yellow",
      )
      return False

    return True

  def _restart_container_after_failures(self, container_name: str):
    """Restart container after consecutive get_node_info failures.
    
    Args:
        container_name: Name of the container to restart
    """
    try:
      # Reset failure counter before restarting
      self.node_info_failure_count = 0
      self._begin_lifecycle_operation("auto_restart", container_name)
      
      # Show notification to user
      self.toast.show_notification(
        NotificationType.WARNING, 
        f"Container {container_name} is not responding. Updating image and restarting..."
      )
      
      self.add_log(f"Automatically updating and restarting {container_name} due to consecutive failures", color="red")
      
      # Get volume name for restart
      volume_name = None
      container_config = self.config_manager.get_container(container_name)
      if container_config and container_config.volume:
        volume_name = container_config.volume
        self.add_log(f"Using volume {volume_name} for restart", debug=True)
      else:
        from utils.docker_utils import get_volume_name
        volume_name = get_volume_name(container_name)
        self.add_log(f"Generated volume name {volume_name} for restart", debug=True)
      
      # Define restart success callback
      def on_restart_success():
        self.add_log(f"Container {container_name} updated and restarted successfully after failures", color="green")
        self.toast.show_notification(
          NotificationType.SUCCESS, 
          f"Container {container_name} updated and restarted successfully"
        )
        # Update UI after restart
        self.post_launch_setup()
        self.refresh_node_info()
        self.plot_data()
        self._end_lifecycle_operation(container_name)
      
      # Define restart error callback
      def on_restart_error(error_msg):
        self.add_log(f"Failed to update and restart container {container_name}: {error_msg}", color="red")
        self.toast.show_notification(
          NotificationType.ERROR, 
          f"Failed to update and restart container {container_name}: {error_msg}"
        )
        self._end_lifecycle_operation(container_name)
      
      # Stop, pull, and restart the container
      self.add_log(f"Stopping container {container_name} for restart with image update", debug=True)
      
      def on_stop_success(result):
        stdout, stderr, return_code = result
        if return_code == 0:
          self.add_log(f"Container {container_name} stopped, now pulling latest image", debug=True)
          # Pull the latest image before restarting
          self._restart_pull_and_launch(container_name, volume_name, on_restart_success, on_restart_error)
        else:
          on_restart_error(f"Failed to stop container: {stderr}")
      
      def on_stop_error(error_msg):
        on_restart_error(f"Failed to stop container: {error_msg}")
      
      # Stop the container first
      self.docker_handler.stop_container_threaded(container_name, on_stop_success, on_stop_error)
      
    except Exception as e:
      error_msg = f"Error during automatic restart: {str(e)}"
      self.add_log(error_msg, color="red")
      self.toast.show_notification(NotificationType.ERROR, error_msg)
      self._end_lifecycle_operation(container_name)

  def _restart_pull_and_launch(self, container_name: str, volume_name: str, on_success, on_error):
    """Pull latest image and launch container during restart process.
    
    Args:
        container_name: Name of the container to launch
        volume_name: Volume name to use
        on_success: Success callback
        on_error: Error callback  
    """
    try:
      # Check if a main Docker pull is already in progress
      if self._docker_pull_in_progress():
        self.add_log(f"Main Docker pull already in progress, skipping restart of {container_name}", color="yellow")
        return
      
      def on_pull_success(result):
        stdout, stderr, return_code = result
        if return_code == 0:
          self.add_log(f"Latest image pulled successfully, now launching {container_name}", debug=True)
          # Launch the container after successful pull
          self._restart_launch_container(container_name, volume_name, on_success, on_error)
        else:
          on_error(f"Failed to pull latest image: {stderr}")
      
      def on_pull_error(error_msg):
        on_error(f"Failed to pull latest image: {error_msg}")
      
      def on_pull_output(line):
        # Log pull progress for debugging
        self.add_log(f"Pull: {line.strip()}", debug=True)
      
      # Pull the latest image
      self.add_log(f"Pulling latest Docker image for restart of {container_name}", color="blue")
      self.docker_handler.pull_image(on_pull_success, on_pull_error, on_pull_output)
      
    except Exception as e:
      on_error(str(e))

  def _restart_launch_container(self, container_name: str, volume_name: str, on_success, on_error):
    """Launch container during restart process.
    
    Args:
        container_name: Name of the container to launch
        volume_name: Volume name to use
        on_success: Success callback
        on_error: Error callback  
    """
    try:
      self.docker_handler.set_container_name(container_name)

      def on_launch_success(result):
        stdout, stderr, return_code = result
        if return_code == 0:
          self.add_log(f"Container {container_name} launched successfully during restart", debug=True)
          on_success()
        else:
          on_error(f"Failed to launch container: {stderr}")
      
      def on_launch_error(error_msg):
        on_error(f"Failed to launch container: {error_msg}")
      
      # Launch the container
      self.docker_handler.launch_container_threaded(volume_name, on_launch_success, on_launch_error)
      
    except Exception as e:
      on_error(str(e))

  def _update_ui_no_container(self):
    """Update UI when no container is selected."""
    if not hasattr(self, 'node_addr') or not self.node_addr:
      self.addressDisplay.setText('Address: No container selected')
      self.ethAddressDisplay.setText('ETH Address: Not available')
      self.nameDisplay.setText('')
      self.copyAddrButton.hide()
      self.copyEthButton.hide()

  def _update_ui_container_not_running(self, container_name: str):
    """Update UI when container is not running - show cached data or appropriate messages."""
    # Check if we're in a loading state (container starting up)
    is_loading = hasattr(self, 'loading_indicator') and self.loading_indicator.isVisible()
    
    # Try to get cached data from config
    config_container = self.config_manager.get_container(container_name)
    
    if config_container and config_container.node_address:
      # Use cached data if available
      self._display_cached_container_data(config_container)
      self.add_log(f"Showing cached data for stopped container: {container_name}", debug=True)
    else:
      # No cached data available
      if is_loading:
        # Container is starting up - show loading messages
        self.addressDisplay.setText('Address: Starting up...')
        self.ethAddressDisplay.setText('ETH Address: Starting up...')
        self.nameDisplay.setText('Name: Loading...')
      else:
        # Container is stopped - show neutral status
        self.addressDisplay.setText('Address: Node not running')
        self.ethAddressDisplay.setText('ETH Address: -')
        self.nameDisplay.setText('')
      
      self.copyAddrButton.hide()
      self.copyEthButton.hide()

  def _update_ui_with_fresh_data(self, node_info: NodeInfo, container_name: str):
    """Update UI with fresh node info data."""
    # Get current config to check for changes
    config_container = self.config_manager.get_container(container_name)
    
    # Check if node alias has changed and update config
    if config_container and node_info.alias != config_container.node_alias:
        self.add_log(f"Node alias changed from '{config_container.node_alias}' to '{node_info.alias}', updating config", debug=True)
        self.config_manager.update_node_alias(container_name, node_info.alias)
        # Refresh container list to update display in dropdown
        current_container = container_name  # Store current selection
        self.refresh_container_list()
        # Restore the selection
        for i in range(self.container_combo.count()):
            if self.container_combo.itemData(i) == current_container:
                self.container_combo.setCurrentIndex(i)
                break

    self._update_node_identity_display(
      node_info.address,
      node_info.eth_address,
      node_info.alias,
      show_copy_buttons=True,
    )

    # Save fresh data to config
    if container_name:
      self.config_manager.update_node_address(container_name, self.node_addr)
      self.config_manager.update_eth_address(container_name, self.node_eth_address)
      self.add_log(f"Saved fresh node address and ETH address to config for {container_name}", debug=True)

    self.add_log(f'Node info updated with fresh data for {container_name}: {self.node_addr} : {self.node_name}, ETH: {self.node_eth_address}')

  def _handle_node_info_error(self, error: str, container_name: str):
    """Handle errors when fetching node info by falling back to cached data or showing error messages."""
    # Try to fall back to cached data first
    config_container = self.config_manager.get_container(container_name)
    
    if config_container and config_container.node_address and hasattr(self, 'node_addr') and self.node_addr:
      # We have both cached data and current data - just log the error but keep current display
      self.add_log(f'Error getting fresh node info for {container_name}: {error}', debug=True)
      
      if "timed out" in error.lower():
        self.add_log(
          f"Node info request for {container_name} timed out. This may indicate network issues. Using cached data.",
          color="yellow")
    else:
      # No cached data or current data - show appropriate error messages
      is_loading = hasattr(self, 'loading_indicator') and self.loading_indicator.isVisible()
      
      self.add_log(f'Error getting node info for {container_name}: {error}', debug=True)
      
      if is_loading:
        # Container is starting up - show loading messages instead of error
        self.addressDisplay.setText('Address: Starting up...')
        self.ethAddressDisplay.setText('ETH Address: Starting up...')  
        self.nameDisplay.setText('Name: Loading...')
      else:
        # Container is not loading - show error state
        self.addressDisplay.setText('Address: Error getting node info')
        self.ethAddressDisplay.setText('ETH Address: -')
        self.nameDisplay.setText('')
      
      self.copyAddrButton.hide()
      self.copyEthButton.hide()

      if "timeout" in error.lower() or "timed out" in error.lower():
        self.add_log(
          f"Node info request for {container_name} timed out. This may indicate network issues or high load.",
          color="red")

  def _update_address_display(self, address: str, show_copy_button: bool = False):
    """Helper method to update address display with consistent formatting."""
    if address:
      if len(address) > 24:  # Only truncate if long enough
        str_display = f"Address: {address[:16]}...{address[-8:]}"
      else:
        str_display = f"Address: {address}"
      self.addressDisplay.setText(str_display)
      self.copyAddrButton.setVisible(show_copy_button)
    else:
      self.addressDisplay.setText('Address: -')
      self.copyAddrButton.hide()

  def _update_eth_address_display(self, eth_address: str, show_copy_button: bool = False):
    """Helper method to update ETH address display with consistent formatting."""
    if eth_address:
      if len(eth_address) > 24:  # Only truncate if long enough
        str_display = f"ETH Address: {eth_address[:16]}...{eth_address[-8:]}"
      else:
        str_display = f"ETH Address: {eth_address}"
      self.ethAddressDisplay.setText(str_display)
      self.copyEthButton.setVisible(show_copy_button)
    else:
      self.ethAddressDisplay.setText('ETH Address: -')
      self.copyEthButton.hide()

  def _update_name_display(self, node_name: str, empty_text: str = ""):
    if node_name:
      self.nameDisplay.setText('Name: ' + node_name)
    else:
      self.nameDisplay.setText(empty_text)

  def _update_node_identity_display(
    self,
    node_address: str,
    eth_address: str,
    node_name: str,
    show_copy_buttons: bool = False,
    empty_name_text: str = "",
  ):
    self.node_addr = node_address
    self.node_eth_address = eth_address
    self.node_name = node_name
    self._update_address_display(
      self.node_addr,
      show_copy_button=show_copy_buttons and bool(self.node_addr),
    )
    self._update_eth_address_display(
      self.node_eth_address,
      show_copy_button=show_copy_buttons and bool(self.node_eth_address),
    )
    self._update_name_display(self.node_name, empty_text=empty_name_text)

  def _display_cached_container_data(self, config_container):
    self._update_node_identity_display(
      config_container.node_address,
      config_container.eth_address,
      config_container.node_alias,
      show_copy_buttons=True,
    )

  def maybe_refresh_uptime(self, assume_running: Optional[bool] = None):
    """Update uptime, epoch and epoch availability displays.
    
    This method updates the UI with the latest uptime, epoch, and epoch availability data.
    It only updates if the data has changed.
    """
    # Use combo item data for container identity; currentText may be a display alias.
    container_name = self._selected_container_name()
    if not container_name:
        self.add_log("No container selected, cannot refresh uptime", debug=True)
        return
    
    # Get current values
    uptime = self.__current_node_uptime
    node_epoch = self.__current_node_epoch
    node_epoch_avail = self.__current_node_epoch_avail
    ver = self.__current_node_ver
    color = 'black'
    
    if assume_running is None:
      is_running = self.is_container_running()
    else:
      is_running = assume_running

    # Check if container is running
    if not is_running:
      # Check if we're in a loading state (container starting up)
      is_loading = hasattr(self, 'loading_indicator') and self.loading_indicator.isVisible()
      
      if is_loading:
        uptime = "STARTING..."
        node_epoch = "Loading..."
        node_epoch_avail = 0
        ver = "Loading..."
        color = 'blue'
      else:
        uptime = "STOPPED"
        node_epoch = "N/A"
        node_epoch_avail = 0
        ver = "N/A"
        color = 'red'
      
    # Only update if values have changed
    if uptime != self.__display_uptime:

      self.node_uptime.setText(f'Up Time: {uptime}')

      self.node_epoch.setText(f'Epoch: {node_epoch}')

      prc = round(node_epoch_avail * 100 if node_epoch_avail > 0 else node_epoch_avail, 2) if node_epoch_avail is not None else 0
      self.node_epoch_avail.setText(f'Epoch avail: {prc}%')

      self.node_version.setText(f'Running ver: {ver}')

      self.__display_uptime = uptime
      self.add_log(f"Updated uptime display for container {container_name}", debug=True)
    return

  def copy_address(self):
    """Copy the node address to clipboard for the currently selected container."""
    # Use combo item data for config identity; currentText may be a display alias.
    container_name = self._selected_container_name()
    if not container_name:
        self.toast.show_notification(NotificationType.ERROR, "No container selected")
        return
    
    # Check if we have an address
    if not self.node_addr:
      # Try to get from config
      config_container = self.config_manager.get_container(container_name)
      if config_container and config_container.node_address:
          self.node_addr = config_container.node_address
      else:
          self.toast.show_notification(NotificationType.ERROR, NOTIFICATION_ADDRESS_COPY_FAILED)
          return

    clipboard = QApplication.clipboard()
    clipboard.setText(self.node_addr)
    self.toast.show_notification(NotificationType.SUCCESS, NOTIFICATION_ADDRESS_COPIED.format(address=self.node_addr))
    self.add_log(f"Copied node address for container {container_name}", debug=True)
    return

  def copy_eth_address(self):
    """Copy the ETH address to clipboard for the currently selected container."""
    # Use combo item data for config identity; currentText may be a display alias.
    container_name = self._selected_container_name()
    if not container_name:
        self.toast.show_notification(NotificationType.ERROR, "No container selected")
        return
    
    # Check if we have an address
    if not self.node_eth_address:
      # Try to get from config
      config_container = self.config_manager.get_container(container_name)
      if config_container and config_container.eth_address:
          self.node_eth_address = config_container.eth_address
      else:
          self.toast.show_notification(NotificationType.ERROR, NOTIFICATION_ADDRESS_COPY_FAILED)
          return

    clipboard = QApplication.clipboard()
    clipboard.setText(self.node_eth_address)
    self.toast.show_notification(NotificationType.SUCCESS, NOTIFICATION_ADDRESS_COPIED.format(address=self.node_eth_address))
    self.add_log(f"Copied ETH address for container {container_name}", debug=True)
    return

  def refresh_all(self):
    """Refresh all data and UI elements."""
    if self._docker_pull_in_progress():
        self.add_log("Docker pull in progress, skipping refresh all", debug=True)
        return
    active = self._active_lifecycle_operation()
    if active is not None:
        self.add_log(
            f"Lifecycle operation {active.get('operation')} active on {active.get('container_name')}, skipping refresh all",
            debug=True,
        )
        return
    self.add_log('Refreshing', debug=True)

    # Only auto-restart if container is not running, button is enabled, user didn't intentionally stop it, AND no pull is in progress
    if not self.is_container_running() and self.toggleButton.isEnabled() == True and not self.user_stopped_container:
      self.add_log("Container is supposed to run. Starting it now...", debug=True, color="red")
      self._start_container()
      return

    self._refresh_local_containers()

    # Update system resources display
    self.update_resources_display()

    # Check for updates periodically - but only if no update is already in progress
    if not self.__update_in_progress and (time() - self.__last_auto_update_check) > AUTO_UPDATE_CHECK_INTERVAL:
      verbose = self.__last_auto_update_check == 0
      self.__last_auto_update_check = time()
      self.check_for_updates(verbose=verbose or FULL_DEBUG)


  def force_refresh_all(self):
    """Force refresh all node information immediately.
    
    This method is called when the user clicks the refresh button to get the most
    recent data from the node, including addresses, metrics, and status.
    """
    try:
        selection = self._selected_container()
        if selection is None:
            self.toast.show_notification(NotificationType.ERROR, "No container selected")
            return
        container_name = selection.name
            
        self.add_log(f"Force refreshing all information for container: {container_name}", color="blue")
        
        # Show notification that refresh is starting
        self.toast.show_notification(NotificationType.INFO, "Refreshing node information...")
        
        # Make sure the docker handler has the correct container name
        self.docker_handler.set_container_name(container_name)
        
        # Check if container is running first
        if not self.is_container_running():
            self.add_log(f"Container {container_name} is not running, limited refresh available", color="yellow")
            self.toast.show_notification(NotificationType.WARNING, "Container is not running. Only cached data available.")
            
            # Still update what we can
            self.update_toggle_button_text()
            self.maybe_refresh_uptime()  # This will show "STOPPED" status
            self.update_resources_display()
            return
        
        # Container is running - get fresh node info directly
        self.add_log("Getting fresh node information from container...", debug=True)
        
        # Clear current data to force fresh retrieval
        self.node_addr = None
        self.node_eth_address = None
        self.node_name = None
        self.__display_uptime = None
        
        # Define success callback for get_node_info
        def on_node_info_success(node_info: NodeInfo) -> None:
            self.add_log(f"Received fresh node info: {node_info.address}, {node_info.alias}, ETH: {node_info.eth_address}", color="green")
            self._update_ui_with_fresh_data(node_info, container_name)
            
            # Now refresh metrics and other data
            self.add_log("Refreshing node metrics and performance data...", debug=True)
            self.plot_data()
            
            # Force refresh uptime, epoch, and version info
            self.add_log("Refreshing node status information...", debug=True)
            self.maybe_refresh_uptime()
            
            # Update system resources
            self.add_log("Refreshing system resources...", debug=True)
            self.update_resources_display()
            
            # Update button states
            self.update_toggle_button_text()
            
            # Show success notification
            self.toast.show_notification(
                NotificationType.SUCCESS, 
                "Node information refreshed successfully"
            )
            
            self.add_log(f"Completed force refresh for container: {container_name}", color="green")
        
        # Define error callback for get_node_info
        def on_node_info_error(error):
            self.add_log(f"Error getting fresh node info: {error}", color="red")
            self.toast.show_notification(NotificationType.ERROR, f"Failed to refresh node info: {error}")
            
            # Still try to refresh other data
            self.add_log("Attempting to refresh other data despite node info error...", debug=True)
            self.plot_data()
            self.maybe_refresh_uptime()
            self.update_resources_display()
            self.update_toggle_button_text()
        
        # Call get_node_info to get fresh data
        self.docker_handler.get_node_info(on_node_info_success, on_node_info_error)
        
    except Exception as e:
        error_msg = f"Error during force refresh: {str(e)}"
        self.add_log(error_msg, color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Refresh failed: {str(e)}")


  def _refresh_local_containers(self):
    """Refresh local container list and info."""
    try:
        # Stop any stale loading indicator during regular refresh
        if hasattr(self, 'loading_indicator') and not self.is_container_running():
            self.loading_indicator.stop()
        
        # Clear any remote connection settings to ensure we're using local Docker
        if hasattr(self, 'docker_handler'):
            self.docker_handler.remote_ssh_command = None
        
        if hasattr(self, 'ssh_service'):
            self.ssh_service.clear_configuration()
        
        # We don't need to refresh the container list on every refresh
        # The container list only changes when containers are added or removed
        # self.refresh_container_list()
        
        # Update container info if running
        if self.is_container_running():
            try:
                # Refresh address first (usually faster)
                self.refresh_node_info()
                
                # Then plot data (can be slower)
                try:
                    self.plot_data()
                except Exception as e:
                    self.add_log(f"Error plotting data for local container: {str(e)}", debug=True, color="red")
            except Exception as e:
                self.add_log(f"Error refreshing local container info: {str(e)}", color="red")
        else:
            # Even when container is not running, update uptime display to show "STOPPED"
            self.maybe_refresh_uptime()
        
        # Always update the toggle button text
        self.update_toggle_button_text()
    except Exception as e:
        self.add_log(f"Error in local container refresh: {str(e)}", color="red")
        # Ensure toggle button text is updated even if there's an error
        self.update_toggle_button_text()

  def dapp_button_clicked(self):
    import webbrowser
    dapp_url = DAPP_URLS.get(self.current_environment)
    if dapp_url:
      webbrowser.open(dapp_url)
      self.add_log(f'Opening dApp URL: {dapp_url}', debug=True)
    else:
      self.add_log(f'Unknown environment: {self.current_environment}', debug=True)
      self.toast.show_notification(
        NotificationType.ERROR,
        f'Unknown environment: {self.current_environment}'
      )
    return
  
  
  def explorer_button_clicked(self):
    self.toast.show_notification(
      NotificationType.INFO,
      'Ratio1 Explorer is not yet implemented'
    )
    return
  
  
  def update_toggle_button_text(self, assume_running: Optional[bool] = None):
    """Update the toggle button text and style based on the current container state"""
    # Get the current text to check if it needs to be updated
    current_text = self.toggleButton.text()
    current_enabled = self.toggleButton.isEnabled()
    selection = self._selected_container()
    
    if selection is None:
        # Only update if state changed
        if current_text != LAUNCH_CONTAINER_BUTTON_TEXT or current_enabled:
            self.toggleButton.setText(LAUNCH_CONTAINER_BUTTON_TEXT)
            self.apply_button_style(self.toggleButton, 'toggle_disabled')
            self.toggleButton.setEnabled(False)
        return
    container_name = selection.name
    
    # Make sure the docker handler has the correct container name
    self.docker_handler.set_container_name(container_name)

    if assume_running is None:
        # Check if container exists in Docker
        container_exists = self.container_exists_in_docker(container_name)

        # If container doesn't exist in Docker but exists in config, show launch button
        if not container_exists:
            config_container = self.config_manager.get_container(container_name)
            if config_container:
                # Only update if state changed
                if current_text != LAUNCH_CONTAINER_BUTTON_TEXT or not current_enabled:
                    self.toggleButton.setText(LAUNCH_CONTAINER_BUTTON_TEXT)
                    self.apply_button_style(self.toggleButton, 'toggle_start')
                    self.toggleButton.setEnabled(True)
                return

        # Check if the container is running using docker_handler directly
        is_running = self.docker_handler.is_container_running()
    else:
        is_running = assume_running
    
    # Determine the new state
    new_text = STOP_CONTAINER_BUTTON_TEXT if is_running else LAUNCH_CONTAINER_BUTTON_TEXT
    new_style = 'toggle_stop' if is_running else 'toggle_start'
    
    # Update text if changed
    if current_text != new_text:
        self.toggleButton.setText(new_text)
    
    # Always apply the style to ensure it updates when theme changes
    self.apply_button_style(self.toggleButton, new_style)
    self.toggleButton.setEnabled(True)
  
  
  def toggle_force_debug(self, state):
    """Toggle force debug mode based on checkbox state.
    
    Args:
        state: The state of the checkbox (Qt.Checked or Qt.Unchecked)
    """
    from PyQt5.QtCore import Qt
    
    is_checked = state == Qt.Checked
    self.__force_debug = is_checked
    
    # Save the debug state
    self.config_manager.set_force_debug(is_checked)
    
    # Log the change
    if is_checked:
        self.add_log("Force debug mode enabled", color="yellow")
    else:
        self.add_log("Force debug mode disabled", color="yellow")
    
    # Update docker handler debug mode if it exists
    if hasattr(self, 'docker_handler') and self.docker_handler is not None:
        try:
            self.docker_handler.set_debug_mode(is_checked)
        except Exception as e:
            self.add_log(f"Failed to set docker handler debug mode: {str(e)}", color="red")
    
    # If a container is running, we might need to restart it for the change to take effect
    if self.is_container_running():
        self.add_log("Note: You may need to restart the container for debug mode changes to take effect", color="yellow")

  def show_rename_dialog(self):
    selection = self._selected_container()
    if selection is None:
        self.toast.show_notification(NotificationType.ERROR, "No container selected")
        return
    container_name = selection.name
    
    # Check if container is running
    if not self.is_container_running():
        self.toast.show_notification(NotificationType.ERROR, "Container not running. Could not change node name.")
        return
    
    # Get current node alias if it exists
    container_config = self.config_manager.get_container(container_name)
    current_alias = container_config.node_alias if container_config and container_config.node_alias else ""
    
    # Create dialog
    dialog = QDialog(self)
    dialog.setWindowTitle("Rename Node")
    dialog.setMinimumWidth(450)
    
    layout = QVBoxLayout()
    
    # Add explanation
    explanation = QLabel("Name this node for display in the launcher.")
    layout.addWidget(explanation)
    
    # Add input field
    name_input = QLineEdit()
    name_input.setObjectName("renameNodeNameInput")
    name_input.setText(current_alias)
    name_input.setMaxLength(15)
    name_input.setPlaceholderText("Node display name")
    
    # Apply theme-appropriate styles
    is_dark = self._current_stylesheet == DARK_STYLESHEET
    text_color = "white" if is_dark else "black"
    name_input.setStyleSheet(f"color: {text_color};")
    layout.addWidget(name_input)
    
    # Add restrictions section
    restrictions_label = QLabel("Name restrictions:")
    restrictions_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
    layout.addWidget(restrictions_label)
    
    restrictions_text = QLabel("- Maximum 15 characters\n- Letters, numbers, hyphens, and underscores only\n- Cannot be empty")
    restrictions_text.setStyleSheet("margin-left: 10px; margin-bottom: 10px;")
    restrictions_text.setWordWrap(True)
    layout.addWidget(restrictions_text)
    
    # Add buttons
    button_layout = QHBoxLayout()
    save_btn = QPushButton("Save")
    save_btn.setObjectName("renameNodeSaveButton")
    save_btn.setProperty("type", "confirm")  # Set property for styling
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setObjectName("renameNodeCancelButton")
    cancel_btn.setProperty("type", "cancel")  # Set property for styling
    
    button_layout.addWidget(save_btn)
    button_layout.addWidget(cancel_btn)
    layout.addLayout(button_layout)
    
    dialog.setLayout(layout)
    dialog.setStyleSheet(self._current_stylesheet)  # Apply current theme
    
    # Connect buttons
    save_btn.clicked.connect(lambda: self.validate_and_save_node_name(name_input.text(), dialog, container_name))
    cancel_btn.clicked.connect(dialog.reject)
    
    dialog.exec_()

  def validate_and_save_node_name(self, new_name: str, dialog: QDialog, container_name: str = None):
    """Validate and save a new node name.
    
    Args:
        new_name: The new name to save
        dialog: The dialog to close on success
        container_name: Optional container name. If not provided, will use current selection.
    """
    # Strip whitespace
    new_name = new_name.strip()
    
    # If container_name not provided, get from current selection
    if not container_name:
        selection = self._selected_container()
        if selection is None:
            self.toast.show_notification(NotificationType.ERROR, "No container selected")
            return
        container_name = selection.name
    
    # Validate the new name
    validation_error = self._validate_node_alias(new_name)
    if validation_error:
        self.toast.show_notification(NotificationType.ERROR, validation_error)
        return
    
    def on_success(data: dict) -> None:
        self.add_log('Successfully renamed node, restarting container...', debug=True)
        self.toast.show_notification(
            NotificationType.SUCCESS,
            'Node renamed successfully. Restarting...'
        )
        dialog.accept()

        self.config_manager.update_node_alias(container_name, new_name)
        self.refresh_container_list()
        for i in range(self.container_combo.count()):
            if self.container_combo.itemData(i) == container_name:
                self.container_combo.setCurrentIndex(i)
                break

        self._restart_container_after_rename(container_name)

    def on_error(error: str) -> None:
        self.add_log(f'Error renaming node: {error}', debug=True)
        # Extract meaningful error message from the response
        error_message = self._extract_rename_error_message(error)
        self.toast.show_notification(
            NotificationType.ERROR,
            f'Failed to rename node: {error_message}'
        )

    self.docker_handler.update_node_name(new_name, on_success, on_error)

  def _restart_container_after_rename(self, container_name: str) -> None:
    """Restart a renamed container without using legacy modal message boxes."""
    container_config = self.config_manager.get_container(container_name)
    volume_name = container_config.volume if container_config and container_config.volume else get_volume_name(container_name)

    self._begin_lifecycle_operation("rename_restart", container_name)
    self.docker_handler.set_container_name(container_name)
    self.user_stopped_container = False
    self._clear_info_display()
    self.loading_indicator.start()
    self.add_log(f"Restarting renamed node container {container_name}...", color="blue")

    def on_stop_success(result):
        stdout, stderr, return_code = result
        if return_code != 0:
            error_msg = f"Failed to stop renamed node before restart: {stderr}"
            self.loading_indicator.stop()
            self.add_log(error_msg, color="red")
            self.toast.show_notification(NotificationType.ERROR, error_msg)
            self._end_lifecycle_operation(container_name)
            return

        self.add_log(f"Renamed node container {container_name} stopped; launching again...", color="blue")
        self.launch_container(volume_name)

    def on_stop_error(error_msg):
        self.loading_indicator.stop()
        self.add_log(f"Error restarting renamed node: {error_msg}", color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Error restarting renamed node: {error_msg}")
        self._end_lifecycle_operation(container_name)

    self.docker_handler.stop_container_threaded(container_name, on_stop_success, on_stop_error)

  def _validate_node_alias(self, alias: str) -> str:
    """Validate a node alias according to the rules.
    
    Args:
        alias: The alias to validate
        
    Returns:
        str: Error message if validation fails, empty string if valid
    """
    import re
    
    # Check if empty
    if not alias:
        return "Node name cannot be empty"
    
    # Check length
    if len(alias) > MAX_ALIAS_LENGTH:
        return f"Node name cannot exceed {MAX_ALIAS_LENGTH} characters (current: {len(alias)})"
    
    # Check allowed characters: letters, numbers, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', alias):
        return "Node name can only contain letters (a-z, A-Z), numbers (0-9), hyphens (-), and underscores (_)"
    
    return ""  # Valid
  
  def _extract_rename_error_message(self, error: str) -> str:
    """Extract a meaningful error message from the rename operation error.
    
    Args:
        error: The raw error message from the rename operation
        
    Returns:
        str: A user-friendly error message
    """
    error_lower = error.lower()
    
    # Check for common error patterns and provide specific messages
    if "timeout" in error_lower or "timed out" in error_lower:
        return "Operation timed out. Please check your connection and try again."
    elif "connection" in error_lower and ("refused" in error_lower or "failed" in error_lower):
        return "Unable to connect to the node. Please ensure the container is running."
    elif "permission" in error_lower or "forbidden" in error_lower:
        return "Permission denied. Please check your node permissions."
    elif "invalid" in error_lower and "name" in error_lower:
        return "The provided name is invalid or not accepted by the node."
    elif "conflict" in error_lower or "already exists" in error_lower:
        return "A node with this name already exists. Please choose a different name."
    elif "network" in error_lower:
        return "Network error occurred. Please check your connection and try again."
    elif "not found" in error_lower or "404" in error:
        return "Node endpoint not found. The container may not be fully started."
    elif "bad request" in error_lower or "400" in error:
        return "Invalid request. Please check the node name format."
    elif "internal server error" in error_lower or "500" in error:
        return "Internal server error occurred. Please try again later."
    else:
        # Return a cleaned up version of the original error
        # Remove common technical prefixes and clean up the message
        cleaned_error = error.strip()
        if cleaned_error.startswith("Error:"):
            cleaned_error = cleaned_error[6:].strip()
        if cleaned_error.startswith("Failed to"):
            cleaned_error = cleaned_error[9:].strip()
        
        # Capitalize first letter if it's not already
        if cleaned_error and cleaned_error[0].islower():
            cleaned_error = cleaned_error[0].upper() + cleaned_error[1:]
        
        return cleaned_error if cleaned_error else "Unknown error occurred"

  def _clear_info_display(self):
    """Clear all information displays."""
    # Check if we're in a loading state (container starting up)
    is_loading = hasattr(self, 'loading_indicator') and self.loading_indicator.isVisible()
    
    # Don't stop the loading indicator here - let the calling methods manage it
    
    # Get the current container name if available
    container_name = None
    if hasattr(self, 'container_combo') and self.container_combo.currentIndex() >= 0:
        container_name = self.container_combo.itemData(self.container_combo.currentIndex())
    
    # Check if we have cached data for this container
    cached_data = None
    if container_name:
        cached_data = self.config_manager.get_container(container_name)
    
    # If we have cached data, use it instead of clearing
    if cached_data and cached_data.node_address:
        self._display_cached_container_data(cached_data)
    else:
        # No cached data - show loading state if container is starting, otherwise show placeholder
        if is_loading:
            # Container is starting up - show loading messages instead of "Not available"
            if hasattr(self, 'nameDisplay'):
                self.nameDisplay.setText('Name: Loading...')

            if hasattr(self, 'addressDisplay'):
                self.addressDisplay.setText('Address: Starting up...')
                if hasattr(self, 'copyAddrButton'):
                    self.copyAddrButton.hide()
            
            if hasattr(self, 'ethAddressDisplay'):
                self.ethAddressDisplay.setText('ETH Address: Starting up...')
                if hasattr(self, 'copyEthButton'):
                    self.copyEthButton.hide()
        else:
            # Container is not loading - show neutral placeholders
            if hasattr(self, 'nameDisplay'):
                self.nameDisplay.setText('Name: -')

            if hasattr(self, 'addressDisplay'):
                self.addressDisplay.setText('Address: -')
                if hasattr(self, 'copyAddrButton'):
                    self.copyAddrButton.hide()
            
            if hasattr(self, 'ethAddressDisplay'):
                self.ethAddressDisplay.setText('ETH Address: -')
                if hasattr(self, 'copyEthButton'):
                    self.copyEthButton.hide()
        
        # Clear instance variables
        self.node_addr = None
        self.node_eth_address = None
        self.node_name = None
    
    if hasattr(self, 'local_address_label'):
        self.local_address_label.setText("Local Address: -")
    
    if hasattr(self, 'eth_address_label'):
        self.eth_address_label.setText("ETH Address: -")
    
    if hasattr(self, 'uptime_label'):
        self.uptime_label.setText("Uptime: -")
    
    if hasattr(self, 'node_uptime'):
        self.node_uptime.setText(UPTIME_LABEL)

    if hasattr(self, 'node_epoch'):
        self.node_epoch.setText(EPOCH_LABEL)

    if hasattr(self, 'node_epoch_avail'):
        self.node_epoch_avail.setText(EPOCH_AVAIL_LABEL)

    if hasattr(self, 'node_version'):
        self.node_version.setText('')

    # Reset state variables
    if hasattr(self, '__display_uptime'):
        self.__display_uptime = None
    
    if hasattr(self, '__current_node_uptime'):
        self.__current_node_uptime = -1
    
    if hasattr(self, '__current_node_epoch'):
        self.__current_node_epoch = -1
    
    if hasattr(self, '__current_node_epoch_avail'):
        self.__current_node_epoch_avail = -1
    
    if hasattr(self, '__current_node_ver'):
        self.__current_node_ver = -1
    
    if hasattr(self, '__last_plot_data'):
        self.__last_plot_data = None
    
    if hasattr(self, '__last_timesteps'):
        self.__last_timesteps = []
    
    # Clear all graphs
    if hasattr(self, 'cpu_plot'):
        self.cpu_plot.clear()
    
    if hasattr(self, 'memory_plot'):
        self.memory_plot.clear()
    
    if hasattr(self, 'gpu_plot'):
        self.gpu_plot.clear()
    
    if hasattr(self, 'gpu_memory_plot'):
        self.gpu_memory_plot.clear()
    
    # Reset graph titles and labels with current theme color
    for plot_name in ['cpu_plot', 'memory_plot', 'gpu_plot', 'gpu_memory_plot']:
        if hasattr(self, plot_name):
            plot = getattr(self, plot_name)
            plot.setTitle('')
            plot.setLabel('left', '')
            plot.setLabel('bottom', '')
    
    # Update toggle button state and color (commented out but updated to use new styling)
    # if hasattr(self, 'toggleButton'):
    #     self.toggleButton.setText(LAUNCH_CONTAINER_BUTTON_TEXT)
    #     self.apply_button_style(self.toggleButton, 'start')

  def open_docker_download(self):
    """Open Docker download page in default browser."""
    import webbrowser
    webbrowser.open('https://docs.docker.com/get-docker/')

  def _on_container_selected(self, container_name: str):
    """Handle container selection and update dashboard display"""
    # Always clear previous container's data first to ensure no data mixing
    self._clear_info_display()
    
    if not container_name:
        return
        
    try:
        display_name = container_name
        actual_container_name = self._selected_container_name()
        if not actual_container_name:
            self.add_log("No container id found for selected item", debug=True)
            return

        self.add_log(f"Selected container: {display_name} ({actual_container_name})", debug=True)
        
        # Ensure loading indicator is stopped when selecting a new container
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.stop()
        
        # Update both docker handler and mixin container name with the Docker id, not the alias.
        self.docker_handler.set_container_name(actual_container_name)
        self.docker_container_name = actual_container_name
        self.add_log(f"Updated container name to: {actual_container_name}", debug=True)
        
        # Check if container exists in Docker
        container_exists = self.container_exists_in_docker(actual_container_name)
        
        # Get container config
        config_container = self.config_manager.get_container(actual_container_name)
        
        # If container doesn't exist in Docker but exists in config, show a message
        if not container_exists:
            if config_container:
                self.add_log(f"Container {actual_container_name} exists in config but not in Docker. It will be recreated when launched.", debug=True)

                self._display_cached_container_data(config_container)
                if config_container.node_address:
                    self.add_log(f"Displaying saved node address for {actual_container_name}", debug=True)
                if config_container.eth_address:
                    self.add_log(f"Displaying saved ETH address for {actual_container_name}", debug=True)
                if config_container.node_alias:
                    self.add_log(f"Displaying saved node alias for {actual_container_name}", debug=True)
                
                return
        
        # Update UI elements
        self.update_toggle_button_text()
        
        # If container is running, update all information displays
        if self.is_container_running():
            self.post_launch_setup()
            self.refresh_node_info()  # Updates address displays with cached data
            self.plot_data()  # Updates graphs and metrics
            self.maybe_refresh_uptime()  # Updates uptime, epoch, and version info
            self.add_log(f"Updated UI with running container data for: {actual_container_name}", debug=True)
        else:
            # Display saved addresses from config if available
            if config_container:
                self._display_cached_container_data(config_container)
                if config_container.node_address:
                    self.add_log(f"Displaying saved node address for {actual_container_name}", debug=True)
                if config_container.eth_address:
                    self.add_log(f"Displaying saved ETH address for {actual_container_name}", debug=True)
                
                self.add_log(f"Container {actual_container_name} is not running, displaying saved data", debug=True)
            
    except Exception as e:
        self._clear_info_display()
        self.add_log(f"Error selecting container {container_name}: {str(e)}", debug=True, color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Error selecting container: {str(e)}")

  def show_add_node_dialog(self):
    """Show confirmation dialog for adding a new node."""
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QMessageBox
    from utils.const import (INSUFFICIENT_RAM_TITLE, INSUFFICIENT_RAM_MESSAGE, 
                            RAM_CHECK_ERROR_TITLE, RAM_CHECK_ERROR_MESSAGE, MIN_NODE_RAM_GB)

    # Check RAM before showing the dialog
    existing_node_count = len(self.config_manager.get_all_containers())
    ram_check = self.check_ram_for_new_node(existing_node_count)
    
    # If there's an error checking RAM, ask user if they want to proceed
    if 'error' in ram_check:
        reply = QMessageBox.question(
            self, 
            RAM_CHECK_ERROR_TITLE,
            RAM_CHECK_ERROR_MESSAGE,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
    # If there's insufficient RAM, show error and return
    elif not ram_check['can_add_node']:
        QMessageBox.warning(
            self,
            INSUFFICIENT_RAM_TITLE,
            INSUFFICIENT_RAM_MESSAGE.format(
                total_gb=ram_check['total_ram_gb'],
                max_nodes=ram_check['max_nodes_supported'],
                current_nodes=ram_check['current_node_count'],
                min_ram_gb=MIN_NODE_RAM_GB
            )
        )
        return

    # Generate the container name that would be used
    container_name = generate_container_name()
    volume_name = get_volume_name(container_name)

    # Create dialog
    dialog = QDialog(self)
    dialog.setWindowTitle(ADD_NEW_NODE_DIALOG_TITLE)
    dialog.setMinimumWidth(400)

    layout = QVBoxLayout()

    # Add info text with more descriptive message including RAM info
    if 'error' not in ram_check:
        info_text = (f"This action will create a new Edge Node.\n\n"
                    f"System Capacity:\n"
                    f"• Total RAM: {ram_check['total_ram_gb']:.1f} GB\n"
                    f"• RAM per node: {ram_check['min_required_gb']} GB\n"
                    f"• Max nodes supported: {ram_check['max_nodes_supported']}\n"
                    f"• Current nodes: {existing_node_count}\n\n"
                    f"Do you want to proceed?")
    else:
        info_text = f"This action will create a new Edge Node. \n\nDo you want to proceed?"
    
    info_label = QLabel(info_text)
    info_label.setWordWrap(True)  # Enable word wrapping for better readability
    layout.addWidget(info_label)

    # Add buttons
    button_layout = QHBoxLayout()
    create_button = QPushButton("Create Node")
    create_button.setObjectName("createNodeConfirmButton")
    cancel_button = QPushButton("Cancel")
    cancel_button.setObjectName("createNodeCancelButton")

    # Apply the same styling as Start/Stop buttons
    self.apply_button_style(create_button, 'start')  # Use 'start' style for Create button
    self.apply_button_style(cancel_button, 'stop')   # Use 'stop' style for Cancel button

    button_layout.addWidget(create_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    dialog.setStyleSheet(self._current_stylesheet)  # Apply current theme

    # Connect buttons
    create_button.clicked.connect(lambda: self._create_node_with_name(container_name, volume_name, None, dialog))
    cancel_button.clicked.connect(dialog.reject)

    dialog.exec_()

  def _create_node_with_name(self, container_name, volume_name, display_name, dialog):
    """Create a new node with the given name and close the dialog."""
    dialog.accept()
    self.add_new_node(container_name, volume_name, display_name)

  def add_new_node(self, container_name: str, volume_name: str, display_name: str = None):
    """Add a new node with the given container name and volume name,
       select it in the UI, and start it immediately."""
    try:
      from datetime import datetime
      self._begin_lifecycle_operation("add_node", container_name)

      # Show the loading dialog - now with blue background
      node_display_name = display_name if display_name else None
      
      if node_display_name:
        message = f"Please wait while node '{node_display_name}' is being launched..."
      else:
        message = "Please wait while new Edge Node is being launched..."
        
      self.startup_dialog = LoadingDialog(
          self, 
          title="Starting Node", 
          message=message,
          size=50
      )
      self.startup_dialog.show()
      
      # Process events to ensure dialog is visible
      QApplication.processEvents()
      
      # Add a small delay to ensure dialog is fully rendered
      QTimer.singleShot(100, lambda: self._perform_add_new_node(container_name, volume_name, display_name))

    except Exception as e:
      self.add_log(f"Failed to create new node: {str(e)}", color="red")
      self._end_lifecycle_operation(container_name)
      # Close the loading dialog if it's still open
      startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
      if startup_dialog_visible:
        self.startup_dialog.safe_close()
        # Schedule removal of the reference after a delay
        QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)

  def _perform_add_new_node(self, container_name, volume_name, display_name):
    """Perform the actual node creation after the dialog is shown."""
    try:
      if self._skip_lifecycle_callback_if_shutting_down("add-node continuation", container_name):
        return

      from datetime import datetime

      # Mark that user is intentionally starting a new container (clear stop flag)
      self.user_stopped_container = False
    
      # 1) Create & store this container's config
      container_config = ContainerConfig(
        name=container_name,
        volume=volume_name,
        created_at=datetime.now().isoformat(),
        last_used=datetime.now().isoformat(),
        node_alias=display_name
      )
      self.config_manager.add_container(container_config)

      # 2) Refresh the list in the combo box, so it includes the new container
      self.refresh_container_list()

      # 3) Programmatically select the newly created container in the ComboBox
      #    We typically match itemData(...) to the container_name
      index = -1
      for i in range(self.container_combo.count()):
        if self.container_combo.itemData(i) == container_name:
          index = i
          break

      if index >= 0:
        self.container_combo.setCurrentIndex(index)

      # 4) Tell the Docker handler to manage this newly selected container
      self.docker_handler.set_container_name(container_name)

      # 5) Actually start (launch) the container so it shows "active" in the UI
      self.launch_container(volume_name)

      self.add_log(f"Successfully created and started new node: {container_name}", color="green")
      
      # Show success notification
      node_display_name = "Edge Node"
      if display_name:
        node_display_name = display_name
        self.toast.show_notification(NotificationType.SUCCESS, f"New Node '{node_display_name}' created successfully")
      else:
        self.toast.show_notification(NotificationType.SUCCESS, "New Edge Node created successfully")

    except Exception as e:
      self.add_log(f"Failed to create new node: {str(e)}", color="red")
      self._end_lifecycle_operation(container_name)
    finally:
      # Close the loading dialog if it's still open
      startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
      if startup_dialog_visible:
        self.startup_dialog.safe_close()
        # Schedule removal of the reference after a delay
        QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)

  def launch_container(self, volume_name: str = None):
    """Launch the currently selected container with a mounted volume.
    
    Args:
        volume_name: Optional volume name to mount. If None, will be retrieved from config
                    or generated based on container name.
    """
    container_name = self.docker_handler.container_name
    if self._skip_lifecycle_callback_if_shutting_down("launch request", container_name):
      return

    self._begin_lifecycle_operation("launch", container_name)
    
    # If volume_name is not provided, try to get it from config
    if volume_name is None:
        container_config = self.config_manager.get_container(container_name)
        if container_config and container_config.volume:
            volume_name = container_config.volume
            self.add_log(f"Using existing volume name from config: {volume_name}", debug=True)
        else:
            # Generate volume name based on container name
            volume_name = get_volume_name(container_name)
            self.add_log(f"Generated volume name: {volume_name}", debug=True)
    
    # Mark that user is intentionally launching the container (clear stop flag)
    self.user_stopped_container = False
    
    # Ensure volume_name is not None or empty
    if not volume_name:
        self.add_log(f"Warning: No volume name provided for container {container_name}. Using default.", color="yellow")
        volume_name = get_volume_name(container_name)
    
    # Check if volume exists in Docker
    volume_exists = self.config_manager.volume_exists_in_docker(volume_name)
    if not volume_exists:
        self.add_log(f"Volume {volume_name} does not exist. It will be created automatically.", debug=True)
    else:
        self.add_log(f"Using existing volume: {volume_name}", debug=True)
    
    self.add_log(f'Launching container {container_name} with volume {volume_name}...')
    
    try:
        # Show loading dialog if not already showing one from add_new_node or toggle_container
        startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
        launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
        
        if not startup_dialog_visible and not launcher_dialog_visible:
            # Get node alias from config if available for better user feedback
            container_config = self.config_manager.get_container(container_name)
            node_alias = None
            if container_config and container_config.node_alias:
                node_alias = container_config.node_alias
                message = f"Please wait while node '{node_alias}' is being launched..."
            else:
                message = "Please wait while Edge Node is being launched..."
                
            # Show loading dialog for launching operation
            self.launcher_dialog = LoadingDialog(
                self, 
                title="Launching Node", 
                message=message,
                size=50
            )
            self.launcher_dialog.show()
            
            # Update message to indicate starting the launch process
            self.launcher_dialog.update_progress("Preparing to launch Docker container...")
            
            # Process events to ensure dialog is visible and responsive
            QApplication.processEvents()
            
            # Add a small delay to ensure dialog is fully rendered
            QTimer.singleShot(100, lambda: self._perform_container_launch(container_name, volume_name))
        else:
            # If we already have a dialog visible, just perform the launch
            # If launcher_dialog is visible, update its progress message
            if launcher_dialog_visible:
                self.launcher_dialog.update_progress("Launching Docker container...")
            # If startup_dialog is visible, update its progress message
            elif startup_dialog_visible:
                self.startup_dialog.update_progress("Launching Docker container...")
                
            # Perform the launch operation
            self._perform_container_launch(container_name, volume_name)
            
    except Exception as e:
        # Stop loading indicator on error
        self.loading_indicator.stop()
        
        # Close the startup dialog if it exists
        startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
        if startup_dialog_visible:
            self.startup_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)
            
        # Close the launcher dialog if it exists
        launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
        if launcher_dialog_visible:
            self.launcher_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
        error_msg = f"Failed to launch container: {str(e)}"
        self.add_log(error_msg, color="red")
        self.toast.show_notification(NotificationType.ERROR, error_msg)

  def _perform_container_launch(self, container_name, volume_name):
    """Perform the actual container launch operation after the dialog is shown."""
    try:
        if self._skip_lifecycle_callback_if_shutting_down("launch continuation", container_name):
            return

        # Clear info displays
        self._clear_info_display()
        self.loading_indicator.start()
        
        # Update loading dialog with progress
        if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
            self.launcher_dialog.update_progress("Preparing Docker command...")
        
        self.add_log(f"Preparing Docker launch for {container_name} with volume {volume_name}. Container cleanup and command preparation will run in the background.", color="blue")
        
        # Check if Docker pull is already in progress
        if self._docker_pull_in_progress():
            self.add_log(f"Docker pull already in progress, skipping launch of {container_name}", color="yellow")
            self._end_lifecycle_operation(container_name)
            
            # Close any loading dialogs that might have been opened
            if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None:
                self.launcher_dialog.safe_close()
                QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
            if hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible():
                self.startup_dialog.safe_close()
                QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)
            
            # Stop loading indicator
            self.loading_indicator.stop()
            return
        
        # Always pull the latest Docker image before launching
        self._start_docker_pull(container_name, volume_name)
        
        # Stop the loading indicator since we're switching to pull dialog
        self.loading_indicator.stop()
        
        # Close the existing launcher dialog if it's open
        if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
            self.launcher_dialog.safe_close()
            QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
        
        # Show Docker pull dialog
        from widgets.DockerPullDialog import DockerPullDialog
        self.docker_pull_dialog = DockerPullDialog(self)
        
        # Connect the pull_complete signal to handle completion
        self.docker_pull_dialog.pull_complete.connect(self._on_docker_pull_complete)
        
        # The container launch will continue automatically after pull completes
        
        # Show the dialog
        self.docker_pull_dialog.show()
        
        # Define callbacks for Docker pull
        def on_pull_success(result):
            if self._skip_lifecycle_callback_if_shutting_down("Docker pull success", container_name):
                return

            stdout, stderr, return_code = result
            # No need to process lines here as they're processed in real-time by on_pull_output
            
            # If pull completed successfully
            if return_code == 0:
                if hasattr(self, 'docker_pull_dialog') and self.docker_pull_dialog is not None :
                    self.docker_pull_dialog.set_pull_complete(True, "Docker image pulled successfully")
            else:
                error_msg = f"Failed to pull Docker image: {stderr}"
                self.add_log(error_msg, color="red")
                if hasattr(self, 'docker_pull_dialog') and self.docker_pull_dialog is not None :
                    self.docker_pull_dialog.set_pull_complete(False, error_msg)
        
        def on_pull_error(error_msg):
            if self._skip_lifecycle_callback_if_shutting_down("Docker pull error", container_name):
                return

            self.add_log(f"Error pulling Docker image: {error_msg}", color="red")
            if hasattr(self, 'docker_pull_dialog') and self.docker_pull_dialog is not None :
                self.docker_pull_dialog.set_pull_complete(False, error_msg)
        
        def on_pull_output(line):
            if self._is_shutting_down():
                return

            # Process each line of output in real-time to update the dialog
            if hasattr(self, 'docker_pull_dialog') and self.docker_pull_dialog is not None :
                self.docker_pull_dialog.update_pull_progress(line)
        
        # Always pull the latest image to ensure we have the most recent version
        self.add_log("Pulling latest Docker image before container launch...", color="blue")
        self.docker_handler.pull_image(on_pull_success, on_pull_error, on_pull_output)
        
        # The live launch path resumes from _on_docker_pull_complete.
        return
        
    except Exception as e:
        # Stop loading indicator on error
        self.loading_indicator.stop()
        
        # Close the startup dialog if it exists
        startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
        if startup_dialog_visible:
            self.startup_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)
            
        # Close the launcher dialog if it exists
        launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
        if launcher_dialog_visible:
            self.launcher_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
        error_msg = f"Failed to launch container: {str(e)}"
        self.add_log(error_msg, color="red")
        self.toast.show_notification(NotificationType.ERROR, error_msg)
        self._end_lifecycle_operation(container_name)

  def _on_docker_pull_complete(self, success, message):
    """Handle Docker pull completion.
    
    Args:
        success: Whether the pull was successful
        message: Success or error message
    """
    launch_context = self._pending_launch_context()
    if self._is_shutting_down():
        if launch_context:
            self._skip_lifecycle_callback_if_shutting_down("Docker pull completion", launch_context["container_name"])
        self._finish_docker_pull()
        return

    # Reset the pull state first
    launch_context = self._finish_docker_pull()
    
    # Log the result
    if success:
        self.add_log("Docker image pulled successfully", color="green")
        logging.info(f"Docker pull completed successfully: {message}")
    else:
        self.add_log(f"Docker image pull failed: {message}", color="red")
        logging.error(f"Docker pull failed: {message}")
        
    # Ensure the Docker pull dialog is closed
    # The dialog should already be closing itself via set_pull_complete, but we'll make sure
    if hasattr(self, 'docker_pull_dialog') and self.docker_pull_dialog is not None:
        self.docker_pull_dialog.safe_close()
        # Remove the reference immediately
        self.docker_pull_dialog = None
    
    # Process events to ensure UI updates
    QApplication.processEvents()
    
    # If pull was successful, continue with the launch target captured before the pull.
    if success:
        if launch_context:
            container_name = launch_context["container_name"]
            volume_name = launch_context["volume_name"]
            self.docker_handler.set_container_name(container_name)
            self._select_container_by_name(container_name)
            container_config = self.config_manager.get_container(container_name)

            if container_config and container_config.node_alias:
                message = f"Please wait while node '{container_config.node_alias}' is being launched..."
            else:
                message = "Please wait while Edge Node is being launched..."

            self.launcher_dialog = LoadingDialog(
                self,
                title="Launching Node",
                message=message,
                size=50
            )
            self.launcher_dialog.show()

            # Update message to indicate starting the launch process
            self.launcher_dialog.update_progress("Preparing to launch Docker container...")

            # Process events to ensure dialog is visible and responsive
            QApplication.processEvents()

            # Continue with container launch after pull - use a short timer to ensure UI is updated first
            QTimer.singleShot(100, lambda: self._perform_container_launch_after_pull(container_name, volume_name))
        else:
            self.add_log("Docker pull completed without a pending launch target", color="yellow")
            self._end_lifecycle_operation()
    else:
        # Show error notification
        if launch_context:
            self._end_lifecycle_operation(launch_context["container_name"])
        self.toast.show_notification(NotificationType.ERROR, f"Failed to pull Docker image: {message}")

  def _perform_container_launch_after_pull(self, container_name, volume_name):
    """Perform the container launch operation after Docker pull is complete."""
    try:
        if self._skip_lifecycle_callback_if_shutting_down("post-pull launch continuation", container_name):
            return

        self.docker_handler.set_container_name(container_name)

        # Start loading indicator
        self.loading_indicator.start()
        
        # Update loading dialog with progress
        if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
            self.launcher_dialog.update_progress("Launching Docker container...")
        
        # Define success callback for threaded operation
        def on_launch_success(result):
            if self._skip_lifecycle_callback_if_shutting_down("launch success", container_name):
                return

            stdout, stderr, return_code = result
            if return_code != 0:
                # Handle error case
                error_msg = f"Failed to launch container: {stderr}"
                self.loading_indicator.stop()
                self._close_dialog_reference("launcher_dialog")
                self._close_dialog_reference("startup_dialog")
                self.add_log(error_msg, color="red")
                self.toast.show_notification(NotificationType.ERROR, error_msg)
                self._end_lifecycle_operation(container_name)
                return
            
            # Update loading dialogs with progress    
            if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
                self.launcher_dialog.update_progress("Container launched, updating configuration...")
            elif hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible():
                self.startup_dialog.update_progress("Container launched, updating configuration...")
            
            # Update last used timestamp in config
            from datetime import datetime
            self.config_manager.update_last_used(container_name, datetime.now().isoformat())
            
            # Update volume name in config if it's not already set
            container_config = self.config_manager.get_container(container_name)
            if container_config and not container_config.volume:
                self.config_manager.update_volume(container_name, volume_name)
                self.add_log(f"Updated volume name in config: {volume_name}", debug=True)
            
            # Update loading dialogs with progress
            if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
                self.launcher_dialog.update_progress("Updating user interface...")
            elif hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible():
                self.startup_dialog.update_progress("Updating user interface...")
            
            # Update UI after launch
            self.post_launch_setup()
            self.refresh_node_info()
            self.plot_data(assume_running=True)
            self.update_toggle_button_text(assume_running=True)
            
            # Stop loading indicator
            self.loading_indicator.stop()
            
            # Update loading dialogs with completion message
            if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
                self.launcher_dialog.update_progress("Container launched successfully!")
            elif hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible():
                self.startup_dialog.update_progress("Container launched successfully!")
            
            # Close the loading dialogs immediately
            launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
            if launcher_dialog_visible:
                self.launcher_dialog.safe_close()
                # Schedule removal of the reference after a delay
                QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
            startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
            if startup_dialog_visible:
                self.startup_dialog.safe_close()
                # Schedule removal of the reference after a delay
                QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)
            
            # Show success notification
            # Get node alias from config if available
            node_display_name = container_name
            container_config = self.config_manager.get_container(container_name)
            if container_config and container_config.node_alias:
                node_display_name = container_config.node_alias
                self.toast.show_notification(NotificationType.SUCCESS, f"Node '{node_display_name}' launched successfully")
            else:
                self.toast.show_notification(NotificationType.SUCCESS, "Edge Node launched successfully")
            self._end_lifecycle_operation(container_name)
        
        # Define error callback for threaded operation
        def on_launch_error(error_msg):
            if self._skip_lifecycle_callback_if_shutting_down("launch error", container_name):
                return

            # Stop loading indicator on error
            self.loading_indicator.stop()
            
            # Check if this is a "container already exists" error
            if "Conflict" in error_msg and "is already in use" in error_msg:
                # Update loading dialogs with specific error message
                if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
                    self.launcher_dialog.update_progress("Container name conflict detected. Trying again with container removal...")
                elif hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible():
                    self.startup_dialog.update_progress("Container name conflict detected. Trying again with container removal...")
                
                # Try to forcefully remove the container and retry launch
                try:
                    # Extract container ID from error message if possible
                    import re
                    container_id_match = re.search(r'by container "([^"]+)"', error_msg)
                    container_id = container_id_match.group(1) if container_id_match else None
                    
                    if container_id:
                        self.add_log(f"Attempting to forcefully remove container with ID: {container_id}", color="yellow")
                        def on_conflict_remove_success(result):
                            _stdout, stderr, return_code = result
                            if return_code != 0:
                                self.add_log(f"Failed to remove conflicting container: {stderr}", color="red")
                                return

                            self.add_log("Successfully removed conflicting container, retrying launch", color="blue")
                            QTimer.singleShot(1000, lambda: self.docker_handler.launch_container_threaded(volume_name, on_launch_success, on_launch_error))

                        self.docker_handler.remove_container_threaded(container_id, on_conflict_remove_success, on_launch_error, force=True)
                        return
                except Exception as retry_err:
                    self.add_log(f"Failed to resolve container conflict: {retry_err}", color="red")
            
            # Update loading dialogs with error message
            if hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None :
                self.launcher_dialog.update_progress(f"Error: {error_msg}")
            elif hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible():
                self.startup_dialog.update_progress(f"Error: {error_msg}")
            
            # Close the loading dialogs immediately
            launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
            if launcher_dialog_visible:
                self.launcher_dialog.safe_close()
                # Schedule removal of the reference after a delay
                QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
            startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
            if startup_dialog_visible:
                self.startup_dialog.safe_close()
                # Schedule removal of the reference after a delay
                QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)
                
            error_msg = f"Failed to launch container: {error_msg}"
            self.add_log(error_msg, color="red")
            self.toast.show_notification(NotificationType.ERROR, error_msg)
            self._end_lifecycle_operation(container_name)
        
        # Launch the container in a thread (without pulling again)
        self.docker_handler.launch_container_threaded(volume_name, on_launch_success, on_launch_error)
        
    except Exception as e:
        # Stop loading indicator on error
        self.loading_indicator.stop()
        
        # Close the startup dialog if it exists
        startup_dialog_visible = hasattr(self, 'startup_dialog') and self.startup_dialog is not None and self.startup_dialog.isVisible()
        if startup_dialog_visible:
            self.startup_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'startup_dialog', None) if hasattr(self, 'startup_dialog') else None)
            
        # Close the launcher dialog if it exists
        launcher_dialog_visible = hasattr(self, 'launcher_dialog') and self.launcher_dialog is not None 
        if launcher_dialog_visible:
            self.launcher_dialog.safe_close()
            # Schedule removal of the reference after a delay
            QTimer.singleShot(500, lambda: setattr(self, 'launcher_dialog', None) if hasattr(self, 'launcher_dialog') else None)
            
        error_msg = f"Failed to launch container: {str(e)}"
        self.add_log(error_msg, color="red")
        self.toast.show_notification(NotificationType.ERROR, error_msg)
        self._end_lifecycle_operation(container_name)
  
  def refresh_container_list(self):
    """Refresh the container list in the combo box."""
    # Store current selection
    current_index = self.container_combo.currentIndex()
    selected_container = self.container_combo.itemData(current_index) if current_index >= 0 else None
    
    # Clear the combo box
    self.container_combo.clear()
    
    # Get containers from config
    containers = self.config_manager.get_all_containers()
    
    # If no containers found, create a default one
    if not containers:
        default_container = ContainerConfig(
            name="r1node",
            volume="r1vol",
            node_alias="r1node"
        )
        self.config_manager.add_container(default_container)
        containers = [default_container]
    
    # Sort containers by name
    containers.sort(key=lambda x: x.name.lower())
    
    # Add containers to combo box
    for container in containers:
        # Use node alias if available, otherwise use container name
        display_text = container.node_alias if container.node_alias else container.name
        self.container_combo.addItem(display_text, container.name)
    
    # Center align all items in the dropdown is now handled by our CenteredComboBox class
    
    # Restore previous selection if it exists
    if selected_container:
        index = -1
        for i in range(self.container_combo.count()):
            if self.container_combo.itemData(i) == selected_container:
                index = i
                break
        if index >= 0:
            self.container_combo.setCurrentIndex(index)
    elif self.container_combo.count() > 0:
        # If no previous selection or it wasn't found, select the first item
        self.container_combo.setCurrentIndex(0)

    self.add_log(f'Displayed {self.container_combo.count()} containers in dropdown', debug=True)

  def is_container_running(self):
    """Check if the currently selected container is running.
    
    Returns:
        bool: True if the container is running, False otherwise
    """
    try:
        selection = self._selected_container()
        if selection is None:
            return False
        container_name = selection.name
            
        # Make sure the docker handler has the correct container name
        self.docker_handler.set_container_name(container_name)
        
        # Use the docker_handler's is_container_running method directly
        is_running = self.docker_handler.is_container_running()
        
        # Log status changes for debugging
        if hasattr(self, 'container_last_run_status') and self.container_last_run_status != is_running:
            self.add_log(f'Container {container_name} status changed: {self.container_last_run_status} -> {is_running}', debug=True)
            self.container_last_run_status = is_running
            
        return is_running
    except Exception as e:
        self.add_log(f"Error checking if container is running: {str(e)}", debug=True, color="red")
        return False


  def container_exists_in_docker(self, container_name: str) -> bool:
    """Check if a container exists in Docker.
    
    Args:
        container_name: Name of the container to check
        
    Returns:
        bool: True if the container exists in Docker, False otherwise
    """
    try:
        # Check directly with docker ps command
        stdout, stderr, return_code = self.docker_handler.execute_command(['docker', 'ps', '-a', '--format', '{{.Names}}', '--filter', f'name={container_name}'])
        if return_code == 0:
            containers = [name.strip() for name in stdout.split('\n') if name.strip() and name.strip() == container_name]
            return len(containers) > 0
        return False
    except Exception as e:
        self.add_log(f"Error checking if container exists in Docker: {str(e)}", debug=True, color="red")
        return False

  def post_launch_setup(self):
    """Execute post-launch setup tasks.
    
    This method is called after a container is launched to update the UI.
    It overrides the method from _DockerUtilsMixin.
    """
    # Call the parent method first
    super().post_launch_setup()
    
    # Ensure loading indicator is stopped after launch
    if hasattr(self, 'loading_indicator'):
        self.loading_indicator.stop()
    
    # Update button state to show container is running
    self.toggleButton.setText(STOP_CONTAINER_BUTTON_TEXT)
    self.apply_button_style(self.toggleButton, 'toggle_stop')
    self.toggleButton.setEnabled(True)
    
    # Log the setup
    self.add_log('Post-launch setup completed', debug=True)
    
    # Process events to update UI immediately
    QApplication.processEvents()
    
    return


  def update_resources_display(self):
    """Update the system resources display with current information."""
    try:
        # Use the new mixin helper methods for cleaner, more maintainable code
        memory_info = self.get_formatted_memory_info()
        cpu_info = self.get_formatted_cpu_info()
        storage_info = self.get_formatted_storage_info()
        
        # Update displays
        self.memoryDisplay.setText(f"{MEMORY_LABEL} {memory_info}")
        self.vcpusDisplay.setText(f"{VCPUS_LABEL} {cpu_info}")
        self.storageDisplay.setText(f"{STORAGE_LABEL} {storage_info}")
        
        self.add_log("Updated system resources display", debug=True)

    except Exception as e:
        self.add_log(f"Error updating resources display: {str(e)}", debug=True)
        # Set fallback values on error
        self.memoryDisplay.setText(f"{MEMORY_LABEL} {MEMORY_NOT_AVAILABLE}")
        self.vcpusDisplay.setText(f"{VCPUS_LABEL} {VCPUS_NOT_AVAILABLE}")
        self.storageDisplay.setText(f"{STORAGE_LABEL} {STORAGE_NOT_AVAILABLE}")

  def check_for_updates(self, verbose=True):
    """Override the _UpdaterMixin check_for_updates method to manage update state and prevent multiple dialogs."""
    # Don't check for updates if one is already in progress or dialog is shown
    if self.__update_in_progress or self.__update_dialog_shown:
        if verbose:
            self.add_log("Update check skipped - update already in progress or dialog is shown", debug=True)
        return
    
    # Set the flags to indicate update process is starting
    self.__update_in_progress = True
    
    try:
        # Implement the update check logic directly here to control dialog display
        latest_version, download_urls = self.get_latest_release_version()
        latest_version = latest_version.lstrip('v').strip().replace('"', '').replace("'", '')
        
        if verbose:
            self.add_log(f'Obtained latest version: {latest_version}')
        
        # Compare versions using the parent method
        if self._compare_versions(CURRENT_VERSION, latest_version):
            # Only show dialog if one isn't already shown
            if not self.__update_dialog_shown:
                self.__update_dialog_shown = True
                
                try:
                    from PyQt5.QtWidgets import QMessageBox

                    reply = QMessageBox.question(
                        self, 'Update Available',
                        f'A new version v{latest_version} is available (current v{CURRENT_VERSION}). Do you want to update?',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    
                    if reply == QMessageBox.Yes:
                        # Continue with the update process by calling the parent's update logic
                        self._proceed_with_update(latest_version, download_urls)
                    else:
                        self.add_log("Update declined by user")
                        
                finally:
                    # Reset dialog flag when dialog is closed
                    self.__update_dialog_shown = False
            else:
                self.add_log("Update dialog already shown, skipping duplicate", debug=True)
        else:
            if verbose:
                self.add_log("You are already using the latest version. Current: {}, Online: {}".format(CURRENT_VERSION, latest_version))
                
    except Exception as e:
        self.add_log(f"Error during update check: {str(e)}", color="red")
        # Reset dialog flag in case of error
        self.__update_dialog_shown = False
    finally:
        # Always reset the progress flag when update check is complete
        self.__update_in_progress = False

  def _proceed_with_update(self, latest_version, download_urls):
    """Handle the update process after user confirmation."""
    import platform
    from PyQt5.QtWidgets import QMessageBox
    
    platform_system = platform.system()
    
    try:
        # Get download URL based on platform
        download_url = download_urls.get(platform_system)
        
        if not download_url:
            self.add_log(f"No download URL available for platform: {platform_system}")
            QMessageBox.information(self, 'Update Not Available', f'No update available for your OS: {platform_system}.')
            return
            
    except Exception as e:
        self.add_log(f"Failed to find download URL for your platform: {e}")
        QMessageBox.warning(self, 'Update Error', f'Could not find a compatible download for your system: {platform_system}.')
        return
    
    # Use user's temp directory for downloads to avoid permission issues
    import sys
    import os
    if sys.platform == "win32":
        download_dir = os.path.join(os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA'), 'EdgeNodeLauncher', 'updates')
    else:
        download_dir = os.path.join(os.getcwd(), 'downloads')
        
    os.makedirs(download_dir, exist_ok=True)
    self.add_log(f'Downloading update from {download_url} to {download_dir}...')
    
    # Download the update
    try:
        downloaded_file = self._download_update(download_url, download_dir)
        
        # For macOS, extract the zip file
        if platform_system == 'Darwin':
            self.add_log(f'Extracting update from {downloaded_file}...')
            self._extract_zip(downloaded_file, os.path.dirname(downloaded_file))
        
        # Show final confirmation before proceeding with update
        reply = QMessageBox.question(
            self, 'Ready to Update', 
            'The update has been downloaded and is ready to install.\n\n' +
            'The application will close and update itself automatically.\n' +
            'This process may take 30-60 seconds.\n\n' +
            'Do you want to proceed with the update now?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # Replace the executable
            self._replace_executable(downloaded_file, 'EdgeNodeLauncher')
        else:
            self.add_log("Update cancelled by user")
            QMessageBox.information(self, 'Update Cancelled', 'The update has been cancelled. You can update later from the menu.')
            
    except Exception as e:
        self.add_log(f"Error during download or installation: {str(e)}")
        QMessageBox.critical(self, 'Update Failed', f'Failed to download or install the update: {str(e)}')
