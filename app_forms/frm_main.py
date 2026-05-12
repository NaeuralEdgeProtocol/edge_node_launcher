import logging
import sys
import platform
import os
import json
import dataclasses

from datetime import datetime, timedelta, timezone
from html import escape
from time import time
from typing import Optional
import re

from PyQt5.QtWidgets import (
  QApplication,
  QWidget,
  QVBoxLayout,
  QPushButton,
  QFrame,
  QDialog,
  QHBoxLayout,
  QStyle,
  QComboBox,
  QMessageBox,
  QFileDialog,
  QLineEdit,
  QGraphicsDropShadowEffect,
  QTabWidget,
  QDialogButtonBox,
  QPlainTextEdit,
  QMenuBar,
  QMenu,
  QAction,
  QProgressBar,
  QMainWindow,
  QScrollArea,
  QTextBrowser,
  QListWidget,
  QStackedWidget,
  QFormLayout,
  QListWidgetItem,
  QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QThread, QObject, pyqtSignal, QUrl, QSettings, QRect,
    QProcess, QPropertyAnimation, QModelIndex, QSortFilterProxyModel
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from models.NodeInfo import NodeInfo
from models.NodeHistory import NodeHistory
from models.ContainerStats import ContainerStats
from widgets.ToastWidget import ToastWidget, NotificationType
from widgets.dialogs.AddNodeDialog import AddNodeDialog
from widgets.dialogs.RenameNodeDialog import RenameNodeDialog
from widgets.app_widgets.activity_log import ActivityLogWidget
from widgets.app_widgets.dashboard_panel import DashboardPanel
from widgets.app_widgets.metric_plot_grid import METRIC_EMPTY_STATE_TEXT, create_metrics_graph_grid
from widgets.app_widgets.sidebar_controls import (
  SIDEBAR_ACTION_BUTTON_HEIGHTS,
  create_sidebar_action_button as build_sidebar_action_button,
  create_sidebar_section_label as build_sidebar_section_label,
)
from widgets.app_widgets.sidebar_panel import SidebarPanel
from utils.const import *
from utils.docker import _DockerUtilsMixin
from utils.docker_commands import DockerCommandHandler
from utils.updater import _UpdaterMixin, UpdateCheckThread
from utils.system_resources import _SystemResourcesMixin
from utils.docker_utils import (
  generate_container_name,
  get_default_container_name,
  get_default_volume_name,
  get_volume_name,
  is_container_name_for_config,
)
from utils.docker_errors import extract_conflicting_container_id
from utils.edge_image_config import MAINNET_CONTAINER_PREFIX, get_edge_node_image_config
from utils.config_manager import ConfigManager, ContainerConfig
from utils.container_selection import SelectedContainer, selected_container_from_combo, select_container_by_name
from utils.lifecycle_copy import (
  launch_success_notification,
  new_node_success_notification,
  stop_success_notification,
)
from utils.lifecycle_state import LaunchContext, LifecycleState
from utils.screen_geometry import available_screen_geometry, screen_geometry
from utils.window_geometry import calculate_initial_window_geometry, calculate_restored_window_geometry, calculate_visible_frame_client_geometry, format_rect
from utils.subprocess_utils import terminate_process_by_pid
from services.app_launch_preflight import AppLaunchPreflightService
from services.docker_runtime_service import DockerRuntimeService
from services.node_allowlist_service import NodeAllowListService
from services.node_telemetry_service import NodeTelemetryMetadata, NodeTelemetryService
from services.node_status_service import (
  NODE_INFO_FAILURE_ACTION_DEFER_STARTUP,
  NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED,
  NodeRuntimeStateDecision,
  NodeStatusService,
)
from services.node_runtime_policy import runtime_policy_display
from services.sdk_identity_service import SdkIdentityService
from widgets.app_widgets.lifecycle_dialog_presenter import LifecycleDialogPresenter
from widgets.app_widgets.lifecycle_controls import (
  LIFECYCLE_BUSY_TOOLTIP,
  LIFECYCLE_BUSY_TOGGLE_TEXT,
  LifecycleControlsPresenter,
)

from utils.icon import ICON_BASE64

from app_forms.frm_utils import get_icon_from_base64

from ver import __VER__ as __version__
from widgets.dialogs.AuthorizedAddressedDialog import AuthorizedAddressesDialog
from models.AllowedAddress import AllowedAddress, AllowedAddressList
from models.StartupConfig import StartupConfig
from models.ConfigApp import ConfigApp
from widgets.ModeSwitch import ModeSwitch
from widgets.dialogs.DockerCheckDialog import DockerCheckDialog
from widgets.LoadingDialog import LoadingDialog

from ver import __VER__ as CURRENT_VERSION


DASHBOARD_SPLITTER_DEFAULT_SIZES = [700, 180]
MAIN_ACTIVITY_LOG_MAX_BLOCKS = 1000
NO_GPU_METRIC_TEXT = "No GPU detected for this node"

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
    self.activityLogPanel = None
    self.activity_log_header = None
    self.activity_log_title = None
    self.activity_log_copy_button = None
    self.activity_log_clear_button = None
    self.dashboard_splitter = None
    self._dashboard_sizes_before_log_focus = None
    self.log_buffer = []
    self.__force_debug = False
    super().__init__()
    self._window_geometry_log_timer = QTimer(self)
    self._window_geometry_log_timer.setSingleShot(True)
    self._window_geometry_log_timer.timeout.connect(self._flush_window_geometry_log)
    self._pending_window_geometry_context = "changed"

    self.edge_image_config = get_edge_node_image_config()
    self.current_environment = self.edge_image_config.environment_key
    self.default_container_name = self._resolve_default_container_name()
    self.default_volume_name = self._resolve_default_volume_name()
    self.container_name_prefix = self.edge_image_config.container_prefix

    self.__current_node_uptime = -1
    self.__current_node_epoch = -1
    self.__current_node_epoch_avail = -1
    self.__current_node_ver = -1
    self.__display_uptime = None
    self.__display_status_metadata = None

    self._current_stylesheet = DARK_STYLESHEET  # Default to dark theme
    self.__last_plot_data = None
    self.__last_plot_source = None
    self.node_telemetry_service = NodeTelemetryService()
    self.__last_auto_update_check = 0

    # Track update process state to prevent duplicate notifications
    self.__update_in_progress = False
    self.__update_dialog_shown = False
    self.__update_check_thread = None
    
    # Track Docker pull state to prevent concurrent pulls
    self.__lifecycle_state = LifecycleState()
    self._lifecycle_dialogs = LifecycleDialogPresenter(self)
    self._lifecycle_controls = LifecycleControlsPresenter(self)
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
    
    self.__cwd = os.getcwd()
    
    self.show_initial_window()
    self.add_log(f'Edge Node Launcher v{self.__version__} started. Running in production: {self.runs_in_production}, running with debugger: {self.runs_with_debugger()}, running in ipython: {self.runs_from_ipython()},  running from exe: {not self.not_running_from_exe()}')
    self.add_log(f'Running from: {self.__cwd}')
    self.add_log(f'Edge Node Docker image: {self.edge_image_config.image} (source: {self.edge_image_config.source})')
    self.add_log(f'Edge Node Docker names: container={self.default_container_name}, volume={self.default_volume_name}')
    if self.edge_image_config.ignored_reason:
      self.add_log(self.edge_image_config.ignored_reason, color="yellow")
    elif not self.edge_image_config.is_mainnet:
      self.add_log('Local testing image override is active. Packaged production runs use mainnet only.', color="yellow")
      self.add_log(
        f'Local testing Docker resources use the {self.container_name_prefix} / {self.edge_image_config.volume_prefix} prefixes to avoid mainnet data.',
        color="yellow",
      )

    platform_info, os_name, os_version = get_platform_and_os_info()
    self.add_log(f'Platform: {platform_info}')
    self.add_log(f'OS: {os_name} {os_version}')

    # Check Docker and handle UI interactions
    if not self.check_docker_with_ui():
        self.close()
        sys.exit(1)

    self.docker_container_name = self.default_container_name
    self.docker_initialize()
    self.docker_handler = DockerRuntimeService(DockerCommandHandler(self.default_container_name))
    self._configure_app_deployment_services()
    self.node_status_service = NodeStatusService(
      failure_threshold=NODE_INFO_FAILURE_THRESHOLD,
      startup_grace_seconds=NODE_STARTUP_GRACE_PERIOD_SECONDS,
    )

    # Set initial container status
    self.container_last_run_status = False
    self._container_running_cache = {}

    # Initialize container list
    self.refresh_container_list()
    
    # Track if user intentionally stopped the container to prevent auto-restart
    self.user_stopped_container = False
    
    # Track failed get_node_info requests for auto-restart
    self.node_info_failure_count = 0
    self.__container_startup_grace_started_at = self.node_status_service.startup_grace_started_at
    
    # Check if container is running and update UI accordingly
    if self.is_container_running():
        self.add_log("Container is running on startup, updating UI", debug=True)
        # Clear the stop flag since container is already running
        self.user_stopped_container = False
        selected_container = self._selected_container_name()
        container_config = self.config_manager.get_container(selected_container) if selected_container else None
        if selected_container and not (container_config and container_config.node_address):
          self._mark_container_startup_grace(selected_container, reason="startup")
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

  def _resolve_default_container_name(self) -> str:
    """Resolve the first managed container for the active network.

    Test and E2E tools may patch DOCKER_CONTAINER_NAME before constructing
    the launcher. Preserve that explicit override while keeping production
    mainnet on the historical r1node name.
    """
    if DOCKER_CONTAINER_NAME != MAINNET_CONTAINER_PREFIX:
      return DOCKER_CONTAINER_NAME
    return get_default_container_name(self.edge_image_config)

  def _resolve_default_volume_name(self) -> str:
    if self.default_container_name != self.edge_image_config.default_container_name:
      return get_volume_name(self.default_container_name)
    return get_default_volume_name(self.edge_image_config)

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
    button_height = SIDEBAR_ACTION_BUTTON_HEIGHTS["primary"]
    if style_type == 'disabled':
        button.setStyleSheet(
            f"background-color: {self.button_colors['disabled']['bg']}; "
            f"color: {self.button_colors['disabled']['text']}; "
            "border-radius: 8px; "
            "padding: 5px 10px;"
            "margin: 3px 6px;"
            "min-height: 24px;"
            "font-size: 14px;"
        )
        button.setMinimumHeight(button_height)
        button.setMaximumHeight(button_height)
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
            margin: 3px 6px;
            border-radius: 8px;
            min-height: 24px;
            font-size: 14px;
            font-weight: bold;
        }}
        {hover_css}
    """)
    button.setMinimumHeight(button_height)
    button.setMaximumHeight(button_height)

  def create_sidebar_section_label(self, text, object_name):
    return build_sidebar_section_label(text, object_name)

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
        self._append_log_line_to_view(line, color=color)
      else:
        self.log_buffer.append(line)
      if debug or self.__force_debug:
        log_with_color(line, color=color)
    return  

  def _append_log_line_to_view(
      self,
      line: str,
      schedule_scroll: bool = True,
      color: str | None = None,
  ) -> None:
    if self.activityLogPanel is None:
      return
    self.activityLogPanel.append_log_line(
      line,
      schedule_scroll=schedule_scroll,
      color=color,
    )

  def _schedule_log_scroll(self) -> None:
    if self.activityLogPanel is None:
      return
    self.activityLogPanel.schedule_scroll_to_latest()

  def _queue_ui_refresh(self, widget=None) -> None:
    target = widget or self
    if target is None:
      return

    def refresh_target() -> None:
      if not self._qt_object_deleted(target):
        target.update()

    QTimer.singleShot(0, refresh_target)
  
  def center(self):
    geometry = calculate_initial_window_geometry(
      self._available_screen_geometry(),
      preferred_width=self.width(),
      preferred_height=self.height(),
    )
    self.setGeometry(geometry)
    return

  def _available_screen_geometry(self):
    return available_screen_geometry(self)

  def _screen_geometry(self):
    return screen_geometry(self)

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

  def _create_metrics_graph_grid(self) -> QWidget:
    """Build the four-panel metrics graph grid and retain public plot attributes."""
    graph_view, plots, axis_items = create_metrics_graph_grid()
    self._metric_axis_items = axis_items
    for plot_attr, plot_widget in plots.items():
      setattr(self, plot_attr, plot_widget)
    return graph_view

  def _activity_log_text(self) -> str:
    if self.activityLogPanel is None:
      return ""
    return self.activityLogPanel.text()

  def _update_activity_log_actions(self) -> None:
    if self.activityLogPanel is not None:
      self.activityLogPanel.update_actions()

  def copy_activity_log(self) -> None:
    if self.activityLogPanel is not None:
      self.activityLogPanel.copy_to_clipboard()

  def clear_activity_log(self) -> None:
    if self.activityLogPanel is not None:
      self.activityLogPanel.clear_log()

  def _create_activity_log_panel(self) -> QWidget:
    """Create the titled activity-log panel while preserving ``self.logView``."""
    panel = ActivityLogWidget(max_blocks=MAIN_ACTIVITY_LOG_MAX_BLOCKS, parent=self)
    self.activity_log_header = panel.header
    self.activity_log_title = panel.title_label
    self.activity_log_copy_button = panel.copy_button
    self.activity_log_clear_button = panel.clear_button
    self.logView = panel.log_view
    return panel

  def _flush_log_buffer_to_view(self) -> None:
    if not self.log_buffer or self.logView is None:
      return

    for line in self.log_buffer:
      self._append_log_line_to_view(line, schedule_scroll=False)
    self.log_buffer = []
    self._update_activity_log_actions()
    self._schedule_log_scroll()

  def _dashboard_splitter_initial_sizes(self) -> list:
    saved_sizes = self.config_manager.get_dashboard_splitter_sizes()
    return saved_sizes if saved_sizes else list(DASHBOARD_SPLITTER_DEFAULT_SIZES)

  def _save_dashboard_splitter_sizes(self) -> None:
    if self.dashboard_splitter is None:
      return
    self.config_manager.set_dashboard_splitter_sizes(self.dashboard_splitter.sizes())

  def _create_dashboard_panel(self) -> QWidget:
    """Create the right-side metrics and activity panel."""
    self.graphView = self._create_metrics_graph_grid()
    self._set_gpu_metric_availability(False)
    self.apps_workspace = self._create_apps_workspace()
    self.main_workspace_stack = QStackedWidget()
    self.main_workspace_stack.setObjectName("mainWorkspaceStack")
    self.main_workspace_stack.setAccessibleName("Main workspace")
    self.main_workspace_stack.setProperty("role", "mainWorkspaceStack")
    self.main_workspace_stack.addWidget(self.graphView)
    self.main_workspace_stack.addWidget(self.apps_workspace)
    self.activityLogPanel = self._create_activity_log_panel()
    dashboard_panel = DashboardPanel(
        self.main_workspace_stack,
        self.activityLogPanel,
        self._dashboard_splitter_initial_sizes(),
        lambda _pos, _index: self._save_dashboard_splitter_sizes(),
        parent=self,
    )
    self.dashboard_splitter = dashboard_panel.splitter
    self._flush_log_buffer_to_view()
    self._on_navigation_page_changed(
      self.sidebar_panel.current_page_name() if hasattr(self, "sidebar_panel") else "nodes"
    )

    return dashboard_panel

  def _create_apps_workspace(self) -> QWidget:
    workspace = QWidget()
    workspace.setObjectName("appsWorkspace")
    workspace.setAccessibleName("Apps workspace")
    workspace.setProperty("role", "appsWorkspace")

    layout = QHBoxLayout(workspace)
    layout.setContentsMargins(10, 0, 10, 0)
    layout.setSpacing(12)

    apps_scroll = QScrollArea()
    apps_scroll.setObjectName("appsWorkspaceScrollArea")
    apps_scroll.setAccessibleName("Apps deployment controls")
    apps_scroll.setWidgetResizable(True)
    apps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    apps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    apps_scroll.setFrameShape(QFrame.NoFrame)
    apps_scroll.setMinimumWidth(540)
    apps_scroll.setMaximumWidth(760)
    apps_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.apps_page.setParent(None)
    self.apps_page.setMinimumWidth(520)
    self.apps_page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    self.apps_page.set_event_logger(self._log_app_event)
    apps_scroll.setWidget(self.apps_page)
    layout.addWidget(apps_scroll, 3)

    details_panel = QWidget()
    details_panel.setObjectName("appsDetailPanel")
    details_panel.setAccessibleName("App details")
    details_panel.setProperty("role", "appsDetailPanel")
    details_layout = QVBoxLayout(details_panel)
    details_layout.setContentsMargins(14, 10, 14, 10)
    details_layout.setSpacing(8)

    self.apps_detail_title = build_sidebar_section_label("Details", "appsDetailTitle")
    self.apps_detail_title.setProperty("role", "dashboardSectionTitle")
    self.apps_detail_text = QTextBrowser()
    self.apps_detail_text.setObjectName("appsDetailText")
    self.apps_detail_text.setAccessibleName("Selected app details")
    self.apps_detail_text.setProperty("role", "appsDetailText")
    self.apps_detail_text.setReadOnly(True)
    self.apps_detail_text.setOpenExternalLinks(False)
    self.apps_detail_text.setHtml(self._apps_empty_detail_html())
    details_layout.addWidget(self.apps_detail_title)
    details_layout.addWidget(self.apps_detail_text, 1)
    layout.addWidget(details_panel, 2)

    self.apps_page.selected_record_changed.connect(self._update_apps_workspace_details)
    return workspace

  def _update_apps_workspace_details(self, record=None) -> None:
    if not hasattr(self, "apps_detail_text"):
      return
    if record is None:
      record = self.apps_page._selected_record()
    if record is None:
      self.apps_detail_text.setHtml(self._apps_empty_detail_html())
      return
    self.apps_detail_text.setHtml(self._apps_detail_html(self._apps_detail_rows(record)))

  def _apps_detail_rows(self, record) -> list[tuple[str, str]]:
    metadata = record.metadata or {}
    rows = [
      ("Name", record.app_name),
      ("Type", record.app_type),
      ("Status", record.status),
      ("Node", record.node_address),
      ("Pipeline", record.pipeline_name),
      ("URL", record.app_url or "-"),
      ("Last action", record.last_action or "-"),
    ]

    checked_at = metadata.get("last_status_checked_at")
    if checked_at:
      rows.append(("Last check", self._format_app_detail_timestamp(checked_at)))

    last_error = metadata.get("last_error")
    if last_error:
      rows.append(("Last error", str(last_error)))

    for label, key in (
      ("Image", "image"),
      ("Repository", "repo_url"),
      ("Branch", "branch"),
    ):
      value = metadata.get(key)
      if value:
        rows.append((label, str(value)))

    resources = self._format_app_detail_resources(metadata.get("resources"))
    if resources:
      rows.append(("Resources", resources))

    volumes = self._format_app_detail_mapping(metadata.get("volumes"))
    if volumes:
      rows.append(("Volumes", volumes))

    file_volumes = self._format_app_detail_file_volumes(metadata.get("file_volumes"))
    if file_volumes:
      rows.append(("Config files", file_volumes))

    policies = self._format_app_detail_policies(metadata)
    if policies:
      rows.append(("Policies", policies))
    return rows

  def _apps_empty_detail_html(self) -> str:
    return (
      '<div class="empty-state">'
      '<p style="font-weight:600; margin:0 0 6px 0;">No app selected</p>'
      '<p style="margin:0;">Select a launcher-owned app to inspect its node, pipeline, URL, and last action.</p>'
      '</div>'
    )

  def _apps_detail_html(self, rows) -> str:
    table_rows = []
    for label, value in rows:
      safe_value = "<br>".join(escape(part) for part in str(value).splitlines())
      table_rows.append(
        "<tr>"
        f'<td style="padding:4px 16px 4px 0; font-weight:600;">{escape(str(label))}</td>'
        f'<td style="padding:4px 0;">{safe_value}</td>'
        "</tr>"
      )
    return '<table cellspacing="0" cellpadding="0">' + "".join(table_rows) + "</table>"

  def _format_app_detail_resources(self, resources) -> str:
    if not isinstance(resources, dict):
      return ""
    parts = []
    for label, key in (("CPU", "cpu"), ("Memory", "memory"), ("GPU", "gpu")):
      value = resources.get(key)
      if value not in (None, "", []):
        parts.append(f"{label}: {value}")
    ports = resources.get("ports")
    if ports:
      parts.append(f"Ports: {', '.join(str(port) for port in ports)}")
    return ", ".join(parts)

  def _format_app_detail_mapping(self, mapping) -> str:
    if not isinstance(mapping, dict) or not mapping:
      return ""
    return "\n".join(
      f"{source} -> {target}"
      for source, target in sorted(mapping.items(), key=lambda item: str(item[0]))
    )

  def _format_app_detail_file_volumes(self, file_volumes) -> str:
    if not isinstance(file_volumes, dict) or not file_volumes:
      return ""
    rows = []
    for name, payload in sorted(file_volumes.items(), key=lambda item: str(item[0])):
      if isinstance(payload, dict):
        mount_path = payload.get("mounting_point") or payload.get("mount_path") or "-"
      else:
        mount_path = "-"
      rows.append(f"{name} -> {mount_path}")
    return "\n".join(rows)

  def _format_app_detail_policies(self, metadata) -> str:
    if not isinstance(metadata, dict):
      return ""
    parts = []
    for label, key in (
      ("Restart", "restart_policy"),
      ("Pull", "image_pull_policy"),
      ("Tunnel", "tunnel_engine"),
      ("VCS poll", "vcs_poll_interval"),
    ):
      value = metadata.get(key)
      if value not in (None, "", []):
        suffix = "s" if key == "vcs_poll_interval" else ""
        parts.append(f"{label}: {value}{suffix}")
    return ", ".join(parts)

  def _format_app_detail_timestamp(self, value) -> str:
    text = str(value or "").strip()
    if not text:
      return ""
    try:
      parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
      return text
    if parsed.tzinfo is not None:
      return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")

  def _log_app_event(self, message: str, *, color: str = "blue", debug: bool = False) -> None:
    self.add_log(message, debug=debug, color=color)

  def _on_navigation_page_changed(self, page_name: str) -> None:
    if not hasattr(self, "main_workspace_stack"):
      return
    if page_name == "logs":
      target = self.graphView
      self._focus_activity_log_panel()
    else:
      target = self.apps_workspace if page_name == "apps" else self.graphView
      self._restore_dashboard_splitter_after_log_focus()
    self.main_workspace_stack.setCurrentWidget(target)

  def _focus_activity_log_panel(self) -> None:
    if self.dashboard_splitter is None:
      return
    current_sizes = self.dashboard_splitter.sizes()
    if current_sizes and sum(current_sizes) > 0 and self._dashboard_sizes_before_log_focus is None:
      self._dashboard_sizes_before_log_focus = list(current_sizes)

    total_height = max(sum(current_sizes), 1)
    log_height = max(280, int(total_height * 0.62))
    graph_height = max(180, total_height - log_height)
    self.dashboard_splitter.setSizes([graph_height, log_height])
    self._schedule_log_scroll()

  def _restore_dashboard_splitter_after_log_focus(self) -> None:
    if self.dashboard_splitter is None or self._dashboard_sizes_before_log_focus is None:
      return
    self.dashboard_splitter.setSizes(self._dashboard_sizes_before_log_focus)
    self._dashboard_sizes_before_log_focus = None

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
    sidebar_scroll.setFixedWidth(390)
    sidebar_scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    sidebar_scroll.setWidget(sidebar_widget)
    return sidebar_scroll

  def _create_sidebar_action_button(self, text, object_name, action_role, tooltip, handler) -> QPushButton:
    return build_sidebar_action_button(text, object_name, action_role, tooltip, handler)

  def _create_sidebar_panel(self) -> QWidget:
    """Create the left navigation and status sidebar."""
    menu_widget = SidebarPanel(
        is_dark=self._current_stylesheet == DARK_STYLESHEET,
        force_debug=self.__force_debug,
        add_node_handler=self.show_add_node_dialog,
        container_selected_handler=self._on_container_selected,
        rename_handler=self.show_rename_dialog,
        toggle_handler=self.toggle_container,
        docker_download_handler=self.open_docker_download,
        dapp_handler=self.dapp_button_clicked,
        explorer_handler=self.explorer_button_clicked,
        refresh_handler=self.force_refresh_all,
        copy_address_handler=self.copy_address,
        copy_eth_handler=self.copy_eth_address,
        theme_toggle_handler=self.toggle_theme,
        force_debug_handler=self.toggle_force_debug,
        copy_log_handler=self.copy_activity_log,
        clear_log_handler=self.clear_activity_log,
        page_changed_handler=self._on_navigation_page_changed,
        event_logger=self._log_app_event,
        parent=self,
    )
    self._bind_sidebar_panel_aliases(menu_widget)
    self.apply_button_style(self.toggleButton, 'toggle_start')

    return menu_widget

  def _bind_sidebar_panel_aliases(self, panel: SidebarPanel) -> None:
    self.sidebar_panel = panel
    self.navigation_page_stack = panel.page_stack
    self.apps_page = panel.apps_page
    self.add_node_button = panel.add_node_button
    self.container_combo = panel.container_combo
    self.renameNodeButton = panel.renameNodeButton
    self.toggleButton = panel.toggleButton
    self.docker_download_button = panel.docker_download_button
    self.dapp_button = panel.dapp_button
    self.explorer_button = panel.explorer_button
    self.refresh_sdk_identity_button = panel.refresh_sdk_identity_button
    self.copy_sdk_identity_address_button = panel.copy_sdk_identity_address_button
    self.sidebar_activity_log_copy_button = panel.sidebar_activity_log_copy_button
    self.sidebar_activity_log_clear_button = panel.sidebar_activity_log_clear_button
    self.refreshButton = panel.refreshButton
    self.themeToggleButton = panel.themeToggleButton
    self.force_debug_checkbox = panel.force_debug_checkbox

    node_panel = panel.node_status_panel
    resource_panel = panel.resource_status_panel

    self.node_status_title = node_panel.node_status_title
    self.edgeImageBadge = node_panel.edgeImageBadge
    self.node_lifecycle_state = node_panel.node_lifecycle_state
    self.node_runtime_policy = node_panel.node_runtime_policy
    self.loading_indicator = node_panel.loading_indicator
    self.addressDisplay = node_panel.addressDisplay
    self.copyAddrButton = node_panel.copyAddrButton
    self.ethAddressDisplay = node_panel.ethAddressDisplay
    self.copyEthButton = node_panel.copyEthButton
    self.nameDisplay = node_panel.nameDisplay
    self.node_uptime = node_panel.node_uptime
    self.node_epoch = node_panel.node_epoch
    self.node_epoch_avail = node_panel.node_epoch_avail
    self.node_version = node_panel.node_version

    self.resource_status_title = resource_panel.resource_status_title
    self.memoryDisplay = resource_panel.memoryDisplay
    self.vcpusDisplay = resource_panel.vcpusDisplay
    self.storageDisplay = resource_panel.storageDisplay
    self._update_edge_image_badge()
    self._update_node_runtime_policy_label(self.default_container_name)

  def _configure_app_deployment_services(self) -> None:
    if not hasattr(self, "apps_page"):
      return
    self.apps_page.set_launch_preflight_service(
      AppLaunchPreflightService(
        identity_service=SdkIdentityService(),
        allowlist_service=NodeAllowListService(self.docker_handler),
      )
    )

  def _update_edge_image_badge(self) -> None:
    if not hasattr(self, "edgeImageBadge"):
      return

    if self.edge_image_config.is_mainnet:
      self.edgeImageBadge.hide()
      return

    self.edgeImageBadge.setText(self.edge_image_config.display_name)
    self.edgeImageBadge.setToolTip(
      f"Local testing Docker image: {self.edge_image_config.image}. "
      "Packaged production runs use mainnet only."
    )
    self.edgeImageBadge.show()

  def _update_node_runtime_policy_label(self, container_name: str = None) -> None:
    if not hasattr(self, "node_runtime_policy"):
      return

    target_container = (
      container_name
      or self._selected_container_name()
      or getattr(self.docker_handler, "container_name", None)
      or self.default_container_name
    )
    display = runtime_policy_display(target_container, self.edge_image_config)
    self.node_runtime_policy.setText(display.text)
    self.node_runtime_policy.setToolTip(display.tooltip)

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
        self.themeToggleButton.setAccessibleName(DARK_DASHBOARD_BUTTON_TEXT)
        is_dark = False
    else:
        self._current_stylesheet = DARK_STYLESHEET
        self.themeToggleButton.setText(LIGHT_DASHBOARD_BUTTON_TEXT)
        self.themeToggleButton.setAccessibleName(LIGHT_DASHBOARD_BUTTON_TEXT)
        is_dark = True

    if hasattr(self, "sidebar_panel"):
        self.sidebar_panel.set_theme_state(is_dark)
    
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
    
    # Update resources display for theme consistency
    self.update_resources_display()

  @staticmethod
  def _qt_object_deleted(obj) -> bool:
    """Return True when a Qt wrapper no longer owns a live C++ object."""
    return LifecycleDialogPresenter.qt_object_deleted(obj)

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

  def _disable_metric_plot_updates_for_shutdown(self) -> None:
    for plot_attr in ("cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"):
      plot_widget = getattr(self, plot_attr, None)
      if plot_widget is None or self._qt_object_deleted(plot_widget):
        continue
      try:
        plot_widget.clear()
        if hasattr(plot_widget, "disable_late_paints"):
          plot_widget.disable_late_paints()
        else:
          plot_widget.setUpdatesEnabled(False)
          viewport = plot_widget.viewport() if hasattr(plot_widget, "viewport") else None
          if viewport is not None and not self._qt_object_deleted(viewport):
            viewport.setUpdatesEnabled(False)
            viewport.hide()
          plot_widget.hide()
      except RuntimeError:
        continue

  def closeEvent(self, event):
    """Handle application close event with proper cleanup."""
    try:
        self.__shutting_down = True
        self.add_log("Starting application shutdown sequence...", debug=True)
        self._save_main_window_geometry()
        self._cancel_update_check_thread()
        
        # Stop any running timers first
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
            self.add_log("Stopped main refresh timer", debug=True)
        
        # Stop any loading indicators
        if hasattr(self, 'loading_indicator') and self.loading_indicator:
            self.loading_indicator.stop()
            self.add_log("Stopped loading indicators", debug=True)

        self._disable_metric_plot_updates_for_shutdown()
        
        # Close any open dialogs forcefully
        dialog_attrs = ['startup_dialog', 'launcher_dialog', 'toggle_dialog', 'docker_pull_dialog']
        for dialog_attr in dialog_attrs:
            self._lifecycle_dialogs.close_reference(dialog_attr)
        
        # Force close any remaining child widgets
        try:
            for child in self.findChildren(QDialog):
                if not self._qt_object_deleted(child) and child.isVisible():
                    child.close()
                    self.add_log(f"Force closed dialog: {type(child).__name__}", debug=True)
        except Exception as e:
            self.add_log(f"Error force closing dialogs: {str(e)}", debug=True)
        
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
        if not terminate_process_by_pid(os.getpid()):
            os._exit(0)
                
    except:
        # Absolute last resort
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

  def apply_stylesheet(self):
    # Apply larger font size for info box labels on macOS
    if platform.system().lower() == 'darwin':
      # Additional macOS-specific styles
      macos_style = """
        #infoBox QLabel {
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

  def _schedule_stop_dialog_close(self, *, success: bool) -> None:
    self._lifecycle_dialogs.schedule_safe_close_reference(
      "toggle_dialog",
      close_delay_ms=500 if success else 1500,
      clear_delay_ms=1000 if success else 2000,
    )

  def _finalize_stop_failure(
    self,
    container_name: str,
    *,
    progress_message: str,
    log_message: str,
    notification_message: str,
  ) -> None:
    self.loading_indicator.stop()
    self._lifecycle_dialogs.update_progress(
      "toggle_dialog",
      f"Error: {progress_message}",
      require_visible=True,
    )
    self._schedule_stop_dialog_close(success=False)
    self.add_log(log_message, color="red")
    self.toast.show_notification(NotificationType.ERROR, notification_message)
    self._end_lifecycle_operation(container_name)

  def _finalize_stop_error(self, container_name: str, error_msg: str) -> None:
    self._finalize_stop_failure(
      container_name,
      progress_message=error_msg,
      log_message=f"Error stopping container: {error_msg}",
      notification_message=f"Error stopping container: {error_msg}",
    )

  def _finalize_stop_success(self, container_name: str, result) -> None:
    _stdout, stderr, return_code = result
    if return_code != 0:
      error_msg = f"Failed to stop container: {stderr}"
      self._finalize_stop_failure(
        container_name,
        progress_message=error_msg,
        log_message=error_msg,
        notification_message=error_msg,
      )
      return

    self.user_stopped_container = True
    self._remember_container_running(container_name, False)
    self._lifecycle_dialogs.update_progress(
      "toggle_dialog",
      "Container stopped, updating UI...",
      require_visible=True,
    )

    self.update_toggle_button_text(assume_running=False)
    self._update_ui_container_not_running(container_name)
    self.maybe_refresh_uptime(assume_running=False)
    self.plot_data(assume_running=False)

    self.loading_indicator.stop()
    self._lifecycle_dialogs.update_progress(
      "toggle_dialog",
      "Container stopped successfully!",
      require_visible=True,
    )
    self._schedule_stop_dialog_close(success=True)
    self._queue_ui_refresh()

    container_config = self.config_manager.get_container(container_name)
    node_alias = container_config.node_alias if container_config and container_config.node_alias else None
    self.toast.show_notification(NotificationType.SUCCESS, stop_success_notification(node_alias))
    self._end_lifecycle_operation(container_name)

  def _create_stop_container_callbacks(self, container_name: str):
    return (
      lambda result: self._finalize_stop_success(container_name, result),
      lambda error_msg: self._finalize_stop_error(container_name, error_msg),
    )

  def _stop_container(self):
    """Stop the Docker container."""
    try:
        # Get the current container name
        container_name = self.docker_handler.container_name
        if not self._try_begin_lifecycle_operation("stop", container_name):
            return
        
        container_config = self.config_manager.get_container(container_name)
        node_alias = container_config.node_alias if container_config and container_config.node_alias else None
        self._lifecycle_dialogs.show_stop_loading(node_alias)
        
        # Clear info displays
        self._clear_info_display()
        self.loading_indicator.start()
        
        self._lifecycle_dialogs.update_progress(
            "toggle_dialog",
            "Stopping Docker container...",
            require_visible=True,
        )
        on_stop_success, on_stop_error = self._create_stop_container_callbacks(container_name)
        
        # Pass the container name explicitly to ensure we're stopping the right one
        self.docker_handler.stop_container_threaded(container_name, on_stop_success, on_stop_error)
        
    except Exception as e:
        error_message = str(e)
        if 'container_name' in locals():
            self._finalize_stop_error(container_name, error_message)
        else:
            self.loading_indicator.stop()
            self.add_log(f"Error stopping container: {error_message}", color="red")
            self.toast.show_notification(NotificationType.ERROR, f"Error stopping container: {error_message}")

  def _start_container(self):
    """Start the Docker container."""
    container_name = None
    try:
        # Get the current container name
        container_name = self.docker_handler.container_name
        if not self._try_begin_lifecycle_operation("start", container_name):
            return
        
        volume_name = self._resolve_launch_volume_name(container_name)
        
        # Mark that user intentionally started the container (clear stop flag)
        self.user_stopped_container = False
        
        container_config = self.config_manager.get_container(container_name)
        node_alias = container_config.node_alias if container_config and container_config.node_alias else None
        self._lifecycle_dialogs.show_launch_loading(node_alias)
        
        # Start the container launch process
        self._perform_container_launch(container_name, volume_name)
        
    except Exception as e:
        if container_name:
            self._finalize_launch_exception(container_name, e)
            return

        self.loading_indicator.stop()
        self.add_log(f"Error launching container: {str(e)}", color="red")
        self.toast.show_notification(NotificationType.ERROR, f"Error launching container: {str(e)}")

  def _telemetry_metadata(self) -> NodeTelemetryMetadata:
    current_epoch = self.__current_node_epoch if self.__current_node_epoch != -1 else 0
    current_epoch_avail = self.__current_node_epoch_avail if self.__current_node_epoch_avail != -1 else 0.0
    uptime = self.__current_node_uptime if self.__current_node_uptime != -1 else ""
    version = self.__current_node_ver if self.__current_node_ver != -1 else ""
    return NodeTelemetryMetadata(
        address=getattr(self, "node_addr", "") or "",
        alias=getattr(self, "node_name", "") or "",
        eth_address=getattr(self, "node_eth_address", "") or "",
        current_epoch=current_epoch,
        current_epoch_avail=current_epoch_avail,
        uptime=str(uptime),
        version=str(version),
    )

  def _apply_metric_history(self, history: NodeHistory, source: str) -> None:
    self.__last_plot_data = history
    self.__last_plot_source = source
    self.plot_graphs()

  def _request_container_stats(self, container_name: str) -> None:
    if not hasattr(self.docker_handler, "get_container_stats"):
        self.add_log(f"Telemetry source=Docker stats target={container_name} result=skipped reason=handler unavailable", debug=True)
        return

    stats_started = time()

    def on_stats_success(stats: ContainerStats) -> None:
        duration = time() - stats_started
        current_selected = self._selected_container_name()
        if container_name != current_selected:
            self.add_log(
                f"Telemetry source=Docker stats target={container_name} result=ignored duration={duration:.2f}s selected={current_selected}",
                debug=True,
            )
            return

        selection = self.node_telemetry_service.select_for_docker_stats(
            container_name,
            stats,
            current_history=self.__last_plot_data,
            current_source=self.__last_plot_source,
            metadata=self._telemetry_metadata(),
        )
        if selection.updated_ui and selection.history is not None:
            self._apply_metric_history(selection.history, selection.source)

        result = "updated UI" if selection.updated_ui else "sampled"
        fallback_text = f"; fallback used because {selection.fallback_reason}" if selection.fallback_reason else ""
        self.add_log(
            f"Telemetry source=Docker stats target={container_name} result={result} duration={duration:.2f}s "
            f"{self.node_telemetry_service.stats_log_summary(stats)}{fallback_text}",
            debug=True,
        )

    def on_stats_error(error) -> None:
        duration = time() - stats_started
        current_selected = self._selected_container_name()
        if container_name != current_selected:
            self.add_log(
                f"Telemetry source=Docker stats target={container_name} result=ignored-error duration={duration:.2f}s selected={current_selected}",
                debug=True,
            )
            return
        self.add_log(
            f"Telemetry source=Docker stats target={container_name} result=error duration={duration:.2f}s error={error}",
            debug=True,
        )

    try:
        self.docker_handler.get_container_stats(on_stats_success, on_stats_error)
    except Exception as e:
        on_stats_error(str(e))

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

    node_history_started = time()

    def on_success(history: NodeHistory) -> None:
        duration = time() - node_history_started
        current_selected = self._selected_container_name()
        if container_name != current_selected:
            self.add_log(
                f"Telemetry source=node_history target={container_name} result=ignored duration={duration:.2f}s selected={current_selected}",
                debug=True,
            )
            return

        # Update uptime and other metrics only for the currently selected container.
        self.__current_node_uptime = getattr(history, "uptime", self.__current_node_uptime)
        self.__current_node_epoch = getattr(history, "current_epoch", self.__current_node_epoch)
        self.__current_node_epoch_avail = getattr(history, "current_epoch_avail", self.__current_node_epoch_avail)
        self.__current_node_ver = getattr(history, "version", self.__current_node_ver)
        self.maybe_refresh_uptime(assume_running=True)

        selection = self.node_telemetry_service.select_for_node_history(
            container_name,
            history,
            metadata=self._telemetry_metadata(),
        )
        if selection.source == "docker_stats" and selection.history is not None:
            self._apply_metric_history(selection.history, selection.source)
            self.add_log(
                f"Telemetry source=node_history target={container_name} result=fallback duration={duration:.2f}s "
                f"fallback=Docker stats because {selection.fallback_reason}",
                debug=True,
            )
            return

        self._apply_metric_history(selection.history, selection.source)
        fallback_text = "fallback=unavailable; rendered available sample" if selection.fallback_reason else "fallback=none"
        self.add_log(
            f"Telemetry source=node_history target={container_name} result=updated UI duration={duration:.2f}s {fallback_text}",
            debug=True,
        )

    def on_error(error):
        duration = time() - node_history_started
        if container_name != self._selected_container_name():
            self.add_log(
                f"Telemetry source=node_history target={container_name} result=ignored-error duration={duration:.2f}s",
                debug=True,
            )
            return

        stats_history = self.node_telemetry_service.history_from_stats_samples(
            container_name,
            base_history=self.__last_plot_data,
            metadata=self._telemetry_metadata(),
        )
        if stats_history is not None:
            self._apply_metric_history(stats_history, "docker_stats")
            self.add_log(
                f"Telemetry source=node_history target={container_name} result=fallback duration={duration:.2f}s "
                f"fallback=Docker stats because error={error}",
                debug=True,
            )
        else:
            self.add_log(
                f"Telemetry source=node_history target={container_name} result=error duration={duration:.2f}s error={error}",
                debug=True,
            )
        
        if "timed out" in str(error).lower():
            self.add_log(f"Metrics request for {container_name} timed out. This may indicate Docker is busy or the local node is under high load.", color="red")

    try:
        self.add_log(f"Telemetry request started target={container_name} sources=node_history,Docker stats", debug=True)
        self._request_container_stats(container_name)
        self.docker_handler.get_node_history(on_success, on_error)
    except Exception as e:
        self.add_log(f"Failed to start metrics request for {container_name}: {str(e)}", debug=True, color="red")
        on_error(str(e))

  def _clear_metric_plots(self, empty_message: Optional[str] = METRIC_EMPTY_STATE_TEXT) -> None:
    for plot_attr in ("cpu_plot", "memory_plot", "gpu_plot", "gpu_memory_plot"):
      plot_widget = getattr(self, plot_attr, None)
      if plot_widget is not None:
        plot_widget.clear()
        plot_widget.setTitle("")
        if empty_message and hasattr(plot_widget, "set_empty_state"):
          plot_widget.set_empty_state(empty_message)
        elif hasattr(plot_widget, "clear_empty_state"):
          plot_widget.clear_empty_state()

  def _configure_metric_axis(self, plot_widget, timestamps, parent: str) -> None:
    date_axis = plot_widget.getAxis('bottom')
    if hasattr(date_axis, "setTimestamps"):
      date_axis.setTimestamps(timestamps, parent=parent)
    date_axis.setTickSpacing(60, 10)
    date_axis.setStyle(tickTextOffset=10)

  def _set_gpu_metric_availability(self, gpu_available: bool) -> None:
    if hasattr(self, "graphView") and self.graphView is not None and self.graphView.layout() is not None:
        layout = self.graphView.layout()
        layout.setRowStretch(0, 1 if gpu_available else 3)
        layout.setRowStretch(1, 1 if gpu_available else 0)

    for plot_widget in (getattr(self, "gpu_plot", None), getattr(self, "gpu_memory_plot", None)):
        if plot_widget is None:
            continue
        container = getattr(plot_widget, "_r1_plot_container", None)
        if container is not None:
            container.setVisible(gpu_available)
        if not gpu_available and hasattr(plot_widget, "set_empty_state"):
            plot_widget.set_empty_state(NO_GPU_METRIC_TEXT)
        if getattr(plot_widget, "_ignore_late_paints", False):
            continue
        plot_widget.setVisible(gpu_available)

  def plot_graphs(self, history: Optional[NodeHistory] = None, limit: int = 100) -> None:
    """Plot the graphs with the given history data.
    
    Args:
        history: The history data to plot. If None, use the last data.
        limit: The maximum number of points to plot.
    """
    # Use combo item data for Docker identity; currentText may be a display alias.
    container_name = self._selected_container_name()
    if not container_name:
        self._clear_metric_plots()
        self._set_gpu_metric_availability(False)
        self.add_log("No container selected, cannot plot graphs", debug=True)
        return
     
    # Use provided history or last data
    if history is None:
       history = self.__last_plot_data
     
    if history is None:
        self._clear_metric_plots()
        self._set_gpu_metric_availability(False)
        self.add_log(f"No history data available for container {container_name}", debug=True)
        return
    
    # Make sure we have timestamps
    if not history.timestamps or len(history.timestamps) == 0:
        self._clear_metric_plots()
        self._set_gpu_metric_availability(False)
        self.add_log(f"No timestamps in history data for container {container_name}", debug=True)
        return
    
    # Clean and limit data
    timestamps = history.timestamps
    if len(timestamps) > limit:
        timestamps = timestamps[-limit:]
     
    # Get colors based on theme
    colors = DARK_COLORS if self._current_stylesheet == DARK_STYLESHEET else LIGHT_COLORS

    self._clear_metric_plots(empty_message=None)

    def numeric_values(values):
        result = []
        for value in values or []:
            try:
                if value is not None:
                    result.append(float(value))
            except (TypeError, ValueError):
                continue
        return result

    def percent_axis_max(values) -> float:
        numbers = numeric_values(values)
        return max(100.0, max(numbers) * 1.15) if numbers else 100.0

    def memory_axis_max(used_values, total_values=None) -> float:
        totals = [value for value in numeric_values(total_values) if value > 0]
        if totals:
            return max(totals)
        used = numeric_values(used_values)
        return max(1.0, max(used) * 1.2) if used else 1.0
    
    # Helper function to update a plot
    def update_plot(plot_widget, timestamps, data, name, color, y_min=None, y_max=None):
        plot_widget.clear()
        if data and len(data) > 0:
            if hasattr(plot_widget, "clear_empty_state"):
                plot_widget.clear_empty_state()
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
            
            plot_options = {
                "pen": color,
                "name": name,
            }
            if len(numeric_timestamps) == 1:
                plot_options.update(
                    symbol="o",
                    symbolSize=7,
                    symbolBrush=color,
                    symbolPen=color,
                )
            plot_widget.plot(numeric_timestamps, data, **plot_options)
            if len(numeric_timestamps) == 1:
                plot_widget.setXRange(numeric_timestamps[0] - 30, numeric_timestamps[0] + 30, padding=0)
            if y_min is not None and y_max is not None and y_max > y_min:
                plot_widget.setYRange(y_min, y_max, padding=0.04)
        elif hasattr(plot_widget, "set_empty_state"):
            plot_widget.set_empty_state(METRIC_EMPTY_STATE_TEXT)
    
    # CPU Plot
    self._configure_metric_axis(self.cpu_plot, timestamps, parent="cpu")
    update_plot(
        self.cpu_plot,
        timestamps,
        history.cpu_load,
        'CPU Load',
        colors["graph_cpu_color"],
        y_min=0,
        y_max=percent_axis_max(history.cpu_load),
    )
    
    # Memory Plot
    self._configure_metric_axis(self.memory_plot, timestamps, parent="mem")
    update_plot(
        self.memory_plot,
        timestamps,
        history.occupied_memory,
        'Occupied Memory',
        colors["graph_memory_color"],
        y_min=0,
        y_max=memory_axis_max(history.occupied_memory, history.total_memory),
    )
    
    gpu_has_data = bool(history and history.gpu_load)
    gpu_memory_has_data = bool(history and history.gpu_occupied_memory)
    self._set_gpu_metric_availability(gpu_has_data or gpu_memory_has_data)

    # GPU Plot if available
    if gpu_has_data:
      self._configure_metric_axis(self.gpu_plot, timestamps, parent="gpu")
      update_plot(
          self.gpu_plot,
          timestamps,
          history.gpu_load,
          'GPU Load',
          colors["graph_gpu_color"],
          y_min=0,
          y_max=percent_axis_max(history.gpu_load),
      )
    elif hasattr(self.gpu_plot, "set_empty_state"):
      self.gpu_plot.set_empty_state(NO_GPU_METRIC_TEXT)

    # GPU Memory if available
    if gpu_memory_has_data:
      self._configure_metric_axis(self.gpu_memory_plot, timestamps, parent="gpu_mem")
      update_plot(
          self.gpu_memory_plot,
          timestamps,
          history.gpu_occupied_memory,
          'Occupied GPU Memory',
          colors["graph_gpu_memory_color"],
          y_min=0,
          y_max=memory_axis_max(history.gpu_occupied_memory, history.gpu_total_memory),
      )
    elif hasattr(self.gpu_memory_plot, "set_empty_state"):
      self.gpu_memory_plot.set_empty_state(NO_GPU_METRIC_TEXT)
      
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
      status_result = self.node_status_service.record_node_info_success(container_name)
      if status_result.startup_grace_cleared:
        self.add_log(f"Startup grace period cleared for {container_name}; node info is available.", debug=True)

      # Reset failure counter on successful request
      if status_result.previous_failure_count > 0:
        self.add_log(f"Node info request succeeded after {status_result.previous_failure_count} failures, resetting counter", debug=True)
      
      # Update UI with fresh node info data
      self._update_ui_with_fresh_data(node_info, container_name)

    def on_error(error):
      decision = self.node_status_service.record_node_info_failure(container_name, str(error))

      if decision.action == NODE_INFO_FAILURE_ACTION_DEFER_STARTUP:
        remaining = decision.startup_grace_remaining_seconds
        self.add_log(
          f"Node {container_name} is still starting; auto-restart is paused for {remaining} more seconds. Last health check: {error}",
          color="yellow",
        )
        self._show_node_starting_state()
        return

      self.add_log(f"Node info request failed ({decision.failure_count}/{decision.threshold}): {error}", color="yellow")
      
      # Check if we need to restart the container after consecutive failures
      if decision.action == NODE_INFO_FAILURE_ACTION_THRESHOLD_REACHED:
        self._refresh_node_lifecycle_state(
          container_running=True,
          container_name=container_name,
          failure_count=decision.failure_count,
        )
        if self._should_restart_after_node_info_failure(container_name):
          self.add_log(f"Node info failed {NODE_INFO_FAILURE_THRESHOLD} times for {container_name}, restarting container", color="red")
          self._restart_container_after_failures(container_name)
        else:
          self.add_log(f"Node info failed {NODE_INFO_FAILURE_THRESHOLD} times for {container_name}, but auto-restart was skipped", color="yellow")
          self.node_status_service.reset_node_info_failure_count()
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
    snapshot = self.__lifecycle_state.diagnostic_snapshot()
    self.__active_lifecycle_operation = snapshot.active_operation
    self.__pending_launch_context = snapshot.pending_launch_context
    self.__docker_pull_in_progress = snapshot.docker_pull_in_progress

  def lifecycle_diagnostics(self) -> dict:
    """Return JSON-friendly lifecycle state for diagnostics and E2E tools."""
    snapshot = self.__lifecycle_state.diagnostic_snapshot()
    return {
      "lifecycle_operation": snapshot.active_operation,
      "docker_pull_in_progress": snapshot.docker_pull_in_progress,
      "pending_launch_context": snapshot.pending_launch_context,
    }

  @property
  def node_info_failure_count(self) -> int:
    status_service = getattr(self, "node_status_service", None)
    if status_service is None:
      return getattr(self, "_legacy_node_info_failure_count", 0)
    return status_service.node_info_failure_count

  @node_info_failure_count.setter
  def node_info_failure_count(self, value: int) -> None:
    status_service = getattr(self, "node_status_service", None)
    if status_service is None:
      self._legacy_node_info_failure_count = value
      return
    status_service.node_info_failure_count = value

  def _set_node_lifecycle_state(self, decision: NodeRuntimeStateDecision) -> None:
    label = getattr(self, "node_lifecycle_state", None)
    if label is None:
      return

    label.setText(f"Status: {decision.state}")
    label.setToolTip(decision.detail)
    label.setProperty("nodeState", decision.state)
    style = label.style()
    if style is not None:
      style.unpolish(label)
      style.polish(label)

  def _refresh_node_lifecycle_state(
    self,
    *,
    container_running: bool,
    container_name: Optional[str] = None,
    is_launching: bool = False,
    needs_attention: bool = False,
    failure_count: Optional[int] = None,
  ) -> None:
    container = container_name or self._selected_container_name() or ""
    self._set_node_lifecycle_state(
      self.node_status_service.runtime_state(
        container_running=container_running,
        container_name=container,
        is_launching=is_launching,
        needs_attention=needs_attention,
        failure_count=failure_count,
      )
    )

  def _active_lifecycle_operation(self) -> Optional[dict]:
    return self.__lifecycle_state.active_operation_dict()

  def _pending_launch_context(self) -> Optional[dict]:
    return self.__lifecycle_state.pending_launch_context_dict()

  def _pending_launch_context_object(self) -> Optional[LaunchContext]:
    return self.__lifecycle_state.pending_launch_context

  def _docker_pull_in_progress(self) -> bool:
    return self.__lifecycle_state.docker_pull_in_progress

  def _mark_container_startup_grace(self, container_name: str, *, reason: str = "launch") -> None:
    if not container_name:
      return
    self.node_status_service.mark_startup_grace(container_name)
    self._refresh_node_lifecycle_state(
      container_running=True,
      container_name=container_name,
      is_launching=True,
    )
    self.add_log(
      f"Startup grace period started for {container_name} after {reason}; auto-restart is paused while the node initializes.",
      debug=True,
      color="yellow",
    )

  def _clear_container_startup_grace(self, container_name: str) -> None:
    if self.node_status_service.clear_startup_grace(container_name):
      self.add_log(f"Startup grace period cleared for {container_name}; node info is available.", debug=True)

  def _container_startup_grace_remaining_seconds(self, container_name: str) -> int:
    return self.node_status_service.startup_grace_remaining_seconds(container_name)

  def _is_startup_pending_node_info_error(self, error: str) -> bool:
    return self.node_status_service.is_startup_pending_node_info_error(error)

  def _should_defer_node_info_failure(self, container_name: str, error: str) -> bool:
    return self.node_status_service.should_defer_node_info_failure(container_name, error)

  def _show_node_starting_state(self) -> None:
    self._refresh_node_lifecycle_state(
      container_running=True,
      container_name=self._selected_container_name(),
      is_launching=True,
    )
    self.addressDisplay.setText('Address: Starting up...')
    self.ethAddressDisplay.setText('ETH Address: Starting up...')
    self.nameDisplay.setText('Name: Loading...')
    self.copyAddrButton.hide()
    self.copyEthButton.hide()
    self.update_toggle_button_text(assume_running=True)

  def _begin_lifecycle_operation(self, operation: str, container_name: str) -> None:
    """Mark that a user-visible lifecycle operation is in progress."""
    self.__lifecycle_state.begin_operation(operation, container_name)
    self._sync_lifecycle_state_snapshot()
    self.add_log(f"Lifecycle operation started: {operation} on {container_name}", debug=True)
    self._sync_lifecycle_control_state()

  def _try_begin_lifecycle_operation(self, operation: str, container_name: str) -> bool:
    result = self.__lifecycle_state.try_begin_operation(
      operation,
      container_name,
      container_running=self.is_container_running(),
    )
    self._sync_lifecycle_state_snapshot()

    if not result.started:
      blocked = result.blocked_operation
      self.add_log(
        f"Ignoring {operation} on {container_name}; lifecycle operation {blocked.operation} is already active on {blocked.container_name}",
        color="yellow",
      )
      self._sync_lifecycle_control_state()
      return False

    if result.superseded_operation is not None:
      superseded = result.superseded_operation
      self.add_log(
        f"Starting {container_name} after Docker reports the stop operation completed",
        debug=True,
      )
      self.add_log(
        f"Lifecycle operation finished: {superseded.operation} on {superseded.container_name}",
        debug=True,
      )

    started = result.operation
    self.add_log(f"Lifecycle operation started: {started.operation} on {started.container_name}", debug=True)
    self._sync_lifecycle_control_state()
    return True

  def _end_lifecycle_operation(self, container_name: str = None) -> None:
    """Clear an active lifecycle operation when its owning flow completes."""
    ended = self.__lifecycle_state.end_operation(container_name)
    self._sync_lifecycle_state_snapshot()
    if ended is None:
      self._sync_lifecycle_control_state()
      return
    self.add_log(f"Lifecycle operation finished: {ended.operation} on {ended.container_name}", debug=True)
    self._sync_lifecycle_control_state()
    self._restore_toggle_button_after_lifecycle(ended)

  def _start_docker_pull(self, container_name: str, volume_name: str) -> None:
    self.__lifecycle_state.start_docker_pull(container_name, volume_name)
    self._sync_lifecycle_state_snapshot()
    self._sync_lifecycle_control_state()

  def _finish_docker_pull(self) -> Optional[LaunchContext]:
    context = self.__lifecycle_state.finish_docker_pull()
    self._sync_lifecycle_state_snapshot()
    self._sync_lifecycle_control_state(use_operation_text=False)
    return context

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

    remaining_startup_grace = self._container_startup_grace_remaining_seconds(container_name)
    if remaining_startup_grace > 0:
      self.add_log(
        f"Skipping auto-restart for {container_name}; startup grace period has {remaining_startup_grace} seconds remaining",
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
      self._refresh_node_lifecycle_state(
        container_running=True,
        container_name=container_name,
        needs_attention=True,
      )
      
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
        self._report_restart_skipped_for_active_pull(container_name, on_error)
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
      self.docker_handler.pull_image(
        on_pull_success,
        on_pull_error,
        on_pull_output,
        container_name=container_name,
      )
      
    except Exception as e:
      on_error(str(e))

  def _report_restart_skipped_for_active_pull(self, container_name: str, on_error) -> None:
    error_msg = "Another Docker pull is already in progress; restart skipped."
    self.add_log(
      f"{error_msg} Container: {container_name}",
      color="yellow",
    )
    on_error(error_msg)

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
          self._mark_container_startup_grace(container_name, reason="auto-restart")
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
    self._refresh_node_lifecycle_state(
      container_running=False,
      container_name=container_name,
      is_launching=is_loading,
    )
    
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
    self._refresh_node_lifecycle_state(
      container_running=True,
      container_name=container_name,
      failure_count=0,
    )

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
    self._refresh_node_lifecycle_state(
      container_running=True,
      container_name=container_name,
      failure_count=self.node_info_failure_count,
    )

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
    if hasattr(self, "apps_page"):
      self.apps_page.set_target_node(
        node_address=self.node_addr,
        container_name=self._selected_container_name() or "",
      )
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
      self._refresh_node_lifecycle_state(
        container_running=False,
        container_name=container_name,
        is_launching=is_loading,
      )
    else:
      self._refresh_node_lifecycle_state(
        container_running=True,
        container_name=container_name,
      )
      
    prc = round(node_epoch_avail * 100 if node_epoch_avail > 0 else node_epoch_avail, 2) if node_epoch_avail is not None else 0
    metadata = (uptime, node_epoch, prc, ver)

    # Only update if values have changed
    if metadata != self.__display_status_metadata:
      self.node_uptime.setText(f'{UPTIME_LABEL} {uptime}')

      self.node_epoch.setText(f'{EPOCH_LABEL} {node_epoch}')

      self.node_epoch_avail.setText(f'{EPOCH_AVAIL_LABEL} {prc}%')

      self.node_version.setText(f'{NODE_VERSION_LABEL} {ver}')

      self.__display_uptime = uptime
      self.__display_status_metadata = metadata
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
    selected_name = self._selected_container_name() or "no selected container"
    self.add_log(f"Periodic refresh started target={selected_name}: Docker state, host resources, and update check", debug=True)

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
            self.add_log(f"Force refresh telemetry target={container_name}: node history and Docker stats", debug=True)
            self.plot_data()
            
            # Force refresh uptime, epoch, and version info
            self.add_log(f"Force refresh status target={container_name}: uptime, epoch, and version", debug=True)
            self.maybe_refresh_uptime()
            
            # Update system resources
            self.add_log("Force refresh host resources: memory, CPU, and storage", debug=True)
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
  
  def _apply_toggle_button_state(self, is_running: bool, *, enabled: bool = True) -> None:
    self._lifecycle_controls.apply_toggle_state(is_running, enabled=enabled)

  def _remember_container_running(self, container_name: str, is_running: bool) -> None:
    if not container_name:
      return
    self._container_running_cache[container_name] = is_running
    if container_name == self._selected_container_name():
      self.container_last_run_status = is_running

  def _cached_container_running(
    self,
    container_name: Optional[str] = None,
    *,
    default: bool = False,
  ) -> bool:
    container = container_name or self._selected_container_name()
    if not container:
      return default
    return self._container_running_cache.get(container, default)

  def _sync_lifecycle_control_state(self, *, use_operation_text: bool = True) -> bool:
    return self._lifecycle_controls.sync(use_operation_text=use_operation_text)

  def _restore_toggle_button_after_lifecycle(self, ended_operation=None) -> None:
    self._lifecycle_controls.restore_after_lifecycle(ended_operation)
  
  def update_toggle_button_text(self, assume_running: Optional[bool] = None):
    """Update the toggle button text and style based on the current container state"""
    lifecycle_controls_busy = self._sync_lifecycle_control_state(use_operation_text=assume_running is None)
    if lifecycle_controls_busy and assume_running is None:
      return

    # Get the current text to check if it needs to be updated
    current_text = self.toggleButton.text()
    current_enabled = self.toggleButton.isEnabled()
    selection = self._selected_container()
    
    if selection is None:
        # Only update if state changed
        if current_text != LAUNCH_CONTAINER_BUTTON_TEXT or current_enabled:
            self.toggleButton.setText(LAUNCH_CONTAINER_BUTTON_TEXT)
            self.toggleButton.setAccessibleName(LAUNCH_CONTAINER_BUTTON_TEXT)
            self.apply_button_style(self.toggleButton, 'toggle_disabled')
            self.toggleButton.setEnabled(False)
        return
    container_name = selection.name
    
    # Make sure the docker handler has the correct container name
    self.docker_handler.set_container_name(container_name)

    if assume_running is None:
        is_running = self._cached_container_running(container_name, default=False)
    else:
        is_running = assume_running
        self._remember_container_running(container_name, is_running)
    
    self._apply_toggle_button_state(is_running, enabled=not lifecycle_controls_busy)
  
  
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
    
    is_dark = self._current_stylesheet == DARK_STYLESHEET
    text_color = "white" if is_dark else "black"

    dialog = RenameNodeDialog(
        self,
        current_alias=current_alias,
        max_length=MAX_ALIAS_LENGTH,
        stylesheet=self._current_stylesheet,
        input_text_color=text_color,
        validate_alias=self._validate_node_alias,
        show_error=lambda message: self.toast.show_notification(NotificationType.ERROR, message),
        submit_alias=lambda new_name, on_error: self.validate_and_save_node_name(
            new_name,
            dialog,
            container_name,
            on_error_callback=on_error,
        ),
    )
    
    dialog.exec_()

  def validate_and_save_node_name(
    self,
    new_name: str,
    dialog: QDialog,
    container_name: str = None,
    on_error_callback=None,
  ) -> bool:
    """Validate and save a new node name.
    
    Args:
        new_name: The new name to save
        dialog: The dialog to close on success
        container_name: Optional container name. If not provided, will use current selection.
        on_error_callback: Optional callback used by dialogs to re-enable submit controls.
    """
    # Strip whitespace
    new_name = new_name.strip()
    
    # If container_name not provided, get from current selection
    if not container_name:
        selection = self._selected_container()
        if selection is None:
            self.toast.show_notification(NotificationType.ERROR, "No container selected")
            return False
        container_name = selection.name
    
    # Validate the new name
    validation_error = self._validate_node_alias(new_name)
    if validation_error:
        self.toast.show_notification(NotificationType.ERROR, validation_error)
        return False
    
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
        if on_error_callback is not None:
            on_error_callback()

    self.docker_handler.update_node_name(new_name, on_success, on_error)
    return True

  def _restart_container_after_rename(self, container_name: str) -> None:
    """Restart a renamed container without using legacy modal message boxes."""
    container_config = self.config_manager.get_container(container_name)
    volume_name = container_config.volume if container_config and container_config.volume else get_volume_name(container_name)

    if not self._try_begin_lifecycle_operation("rename_restart", container_name):
      return

    self.docker_handler.set_container_name(container_name)
    self.user_stopped_container = False
    self._clear_info_display()
    self.loading_indicator.start()
    self.add_log(f"Restarting renamed node container {container_name}...", color="blue")

    on_stop_success, on_stop_error = self._create_rename_restart_stop_callbacks(
        container_name,
        volume_name,
    )
    self.docker_handler.stop_container_threaded(container_name, on_stop_success, on_stop_error)

  def _create_rename_restart_stop_callbacks(self, container_name: str, volume_name: str):
    """Create callbacks for stopping a renamed node before launching it again."""
    def on_stop_success(result):
        if self._skip_lifecycle_callback_if_shutting_down("rename restart stop success", container_name):
            return

        _stdout, stderr, return_code = result
        if return_code != 0:
            self._finalize_rename_restart_failure(
                container_name,
                f"Failed to stop renamed node before restart: {stderr}",
            )
            return

        self._continue_rename_restart_after_stop(container_name, volume_name)

    def on_stop_error(error_msg):
        if self._skip_lifecycle_callback_if_shutting_down("rename restart stop error", container_name):
            return

        self._finalize_rename_restart_failure(
            container_name,
            f"Error restarting renamed node: {error_msg}",
        )

    return on_stop_success, on_stop_error

  def _continue_rename_restart_after_stop(self, container_name: str, volume_name: str) -> None:
    """Finish the rename-restart stop phase and hand off to normal launch."""
    self.add_log(f"Renamed node container {container_name} stopped; launching again...", color="blue")
    self._end_lifecycle_operation(container_name)
    self.launch_container(volume_name)

  def _finalize_rename_restart_failure(self, container_name: str, error_msg: str) -> None:
    """Clear rename-restart UI state and report a terminal failure."""
    self.loading_indicator.stop()
    self.add_log(error_msg, color="red")
    self.toast.show_notification(NotificationType.ERROR, error_msg)
    self._end_lifecycle_operation(container_name)

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
        self.node_uptime.setText(f"{UPTIME_LABEL} {EMPTY_DASH_TEXT}")

    if hasattr(self, 'node_epoch'):
        self.node_epoch.setText(f"{EPOCH_LABEL} {EMPTY_DASH_TEXT}")

    if hasattr(self, 'node_epoch_avail'):
        self.node_epoch_avail.setText(f"{EPOCH_AVAIL_LABEL} {EMPTY_DASH_TEXT}")

    if hasattr(self, 'node_version'):
        self.node_version.setText(f"{NODE_VERSION_LABEL} {EMPTY_DASH_TEXT}")

    # Reset state variables
    if hasattr(self, '__display_uptime'):
        self.__display_uptime = None

    if hasattr(self, '__display_status_metadata'):
        self.__display_status_metadata = None
    
    if hasattr(self, '__current_node_uptime'):
        self.__current_node_uptime = -1
    
    if hasattr(self, '__current_node_epoch'):
        self.__current_node_epoch = -1
    
    if hasattr(self, '__current_node_epoch_avail'):
        self.__current_node_epoch_avail = -1
    
    if hasattr(self, '__current_node_ver'):
        self.__current_node_ver = -1
    
    self.__last_plot_data = None
    self.__last_plot_source = None
    self.node_telemetry_service.clear()
    
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
        self._update_node_runtime_policy_label(actual_container_name)
        self.add_log(f"Updated container name to: {actual_container_name}", debug=True)
        
        # Check if container exists in Docker
        container_exists = self.container_exists_in_docker(actual_container_name)
        
        # Get container config
        config_container = self.config_manager.get_container(actual_container_name)
        
        # If container doesn't exist in Docker but exists in config, show a message
        if not container_exists:
            if config_container:
                self._remember_container_running(actual_container_name, False)
                self.add_log(f"Container {actual_container_name} exists in config but not in Docker. It will be recreated when launched.", debug=True)

                self._display_cached_container_data(config_container)
                if config_container.node_address:
                    self.add_log(f"Displaying saved node address for {actual_container_name}", debug=True)
                if config_container.eth_address:
                    self.add_log(f"Displaying saved ETH address for {actual_container_name}", debug=True)
                if config_container.node_alias:
                    self.add_log(f"Displaying saved node alias for {actual_container_name}", debug=True)
                
                self.update_toggle_button_text(assume_running=False)
                return
        
        # Update UI elements
        self.update_toggle_button_text()
        
        # If container is running, update all information displays
        is_running = self.is_container_running()
        self.update_toggle_button_text(assume_running=is_running)
        if is_running:
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
    # Check RAM before showing the dialog
    existing_node_count = len(self._containers_for_current_environment(self.config_manager.get_all_containers()))
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
    # If recommended RAM capacity is reached, continue to the dialog with
    # explicit overcommit warning copy instead of silently blocking creation.
    elif not ram_check['can_add_node']:
        self.add_log(
            "Recommended node capacity reached. Showing overcommit warning before creating another node.",
            color="yellow",
        )

    # Generate the container name that would be used
    container_name = generate_container_name(self.container_name_prefix)
    volume_name = get_volume_name(container_name)

    dialog = AddNodeDialog(
        self,
        ram_check=ram_check,
        existing_node_count=existing_node_count,
        container_name=container_name,
        volume_name=volume_name,
        stylesheet=self._current_stylesheet,
        create_node=self._create_node_with_name,
        button_styler=self.apply_button_style,
    )

    dialog.exec_()

  def _create_node_with_name(self, container_name, volume_name, display_name, dialog):
    """Create a new node with the given name and close the dialog."""
    dialog.accept()
    self.add_new_node(container_name, volume_name, display_name)

  def add_new_node(self, container_name: str, volume_name: str, display_name: str = None):
    """Add a new node with the given container name and volume name,
       select it in the UI, and start it immediately."""
    try:
      if not self._try_begin_lifecycle_operation("add_node", container_name):
        return

      # Show the loading dialog - now with blue background
      self._lifecycle_dialogs.show_new_node_loading(display_name)
      
      # Add a small delay to ensure dialog is fully rendered
      QTimer.singleShot(100, lambda: self._perform_add_new_node(container_name, volume_name, display_name))

    except Exception as e:
      self.add_log(f"Failed to create new node: {str(e)}", color="red")
      self._end_lifecycle_operation(container_name)
      self._lifecycle_dialogs.schedule_safe_close_reference(
        "startup_dialog",
        close_delay_ms=0,
        clear_delay_ms=500,
      )

  def _perform_add_new_node(self, container_name, volume_name, display_name):
    """Perform the actual node creation after the dialog is shown."""
    try:
      if self._skip_lifecycle_callback_if_shutting_down("add-node continuation", container_name):
        return

      # Mark that user is intentionally starting a new container (clear stop flag)
      self.user_stopped_container = False
      self._register_and_select_new_node(container_name, volume_name, display_name)
      self.launch_container(volume_name)

      self.add_log(f"Successfully created and started new node: {container_name}", color="green")
      
      self.toast.show_notification(NotificationType.SUCCESS, new_node_success_notification(display_name))

    except Exception as e:
      self.add_log(f"Failed to create new node: {str(e)}", color="red")
      self._end_lifecycle_operation(container_name)
    finally:
      self._lifecycle_dialogs.schedule_safe_close_reference(
        "startup_dialog",
        close_delay_ms=0,
        clear_delay_ms=500,
      )

  def _register_and_select_new_node(self, container_name: str, volume_name: str, display_name: str = None) -> ContainerConfig:
    """Create config for a new node, refresh selection, and target Docker operations."""
    container_config = ContainerConfig(
      name=container_name,
      volume=volume_name,
      created_at=datetime.now().isoformat(),
      last_used=datetime.now().isoformat(),
      node_alias=display_name,
    )
    self.config_manager.add_container(container_config)
    self.refresh_container_list()
    self._select_container_by_name(container_name)
    self.docker_handler.set_container_name(container_name)
    self._update_node_runtime_policy_label(container_name)
    return container_config

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
    
    # Mark that user is intentionally launching the container (clear stop flag)
    self.user_stopped_container = False
    volume_name = self._resolve_launch_volume_name(container_name, volume_name)
    
    self.add_log(f'Launching container {container_name} with volume {volume_name}...')
    
    try:
        self._launch_with_dialog_handoff(container_name, volume_name)
            
    except Exception as e:
        self._finalize_launch_exception(container_name, e)

  def _resolve_launch_volume_name(self, container_name: str, volume_name: str = None) -> str:
    """Resolve and log the Docker volume used for a launch request."""
    if volume_name is None:
        container_config = self.config_manager.get_container(container_name)
        if container_config and container_config.volume:
            volume_name = container_config.volume
            self.add_log(f"Using existing volume name from config: {volume_name}", debug=True)
        else:
            volume_name = get_volume_name(container_name)
            self.add_log(f"Generated volume name: {volume_name}", debug=True)

    if not volume_name:
        self.add_log(f"Warning: No volume name provided for container {container_name}. Using default.", color="yellow")
        volume_name = get_volume_name(container_name)

    volume_exists = self.config_manager.volume_exists_in_docker(volume_name)
    if not volume_exists:
        self.add_log(f"Volume {volume_name} does not exist. It will be created automatically.", debug=True)
    else:
        self.add_log(f"Using existing volume: {volume_name}", debug=True)

    return volume_name

  def _launch_with_dialog_handoff(self, container_name: str, volume_name: str) -> None:
    """Show or reuse launch UI before continuing into Docker launch preparation."""
    startup_dialog_visible = self._lifecycle_dialogs.is_visible("startup_dialog")
    launcher_dialog_visible = self._lifecycle_dialogs.reference("launcher_dialog") is not None

    if not startup_dialog_visible and not launcher_dialog_visible:
        container_config = self.config_manager.get_container(container_name)
        node_alias = container_config.node_alias if container_config and container_config.node_alias else None
        self._lifecycle_dialogs.show_launch_loading(node_alias)
        QTimer.singleShot(100, lambda: self._perform_container_launch(container_name, volume_name))
        return

    self._lifecycle_dialogs.update_launch_progress("Launching Docker container...")
    self._perform_container_launch(container_name, volume_name)

  def _perform_container_launch(self, container_name, volume_name):
    """Perform the actual container launch operation after the dialog is shown."""
    try:
        if self._skip_lifecycle_callback_if_shutting_down("launch continuation", container_name):
            return

        # Clear info displays
        self._clear_info_display()
        self.loading_indicator.start()
        
        # Update loading dialog with progress
        self._lifecycle_dialogs.update_progress("launcher_dialog", "Preparing Docker command...")
        
        self.add_log(f"Preparing Docker launch for {container_name} with volume {volume_name}. Container cleanup and command preparation will run in the background.", color="blue")
        
        # Check if Docker pull is already in progress
        if self._docker_pull_in_progress():
            self._finalize_launch_skipped_for_active_pull(container_name)
            return
        
        self._start_docker_pull_for_launch(container_name, volume_name)
        # The live launch path resumes from _on_docker_pull_complete.
        return
        
    except Exception as e:
        self._finalize_launch_exception(container_name, e)

  def _start_docker_pull_for_launch(self, container_name: str, volume_name: str) -> None:
    """Start Docker image pull and wire it to the launch continuation."""
    self._start_docker_pull(container_name, volume_name)
    self.loading_indicator.stop()
    self._lifecycle_dialogs.schedule_safe_close_reference(
        "launcher_dialog",
        close_delay_ms=0,
        clear_delay_ms=500,
    )

    from widgets.DockerPullDialog import DockerPullDialog
    self.docker_pull_dialog = DockerPullDialog(
      self,
      is_dark=self._current_stylesheet == DARK_STYLESHEET,
    )
    self.docker_pull_dialog.pull_complete.connect(self._on_docker_pull_complete)
    self.docker_pull_dialog.show()

    on_pull_success, on_pull_error, on_pull_output = self._create_docker_pull_callbacks(
        container_name,
    )

    self.add_log("Pulling latest Docker image before container launch...", color="blue")
    self.docker_handler.pull_image(
      on_pull_success,
      on_pull_error,
      on_pull_output,
      container_name=container_name,
    )

  def _finalize_launch_skipped_for_active_pull(self, container_name: str) -> None:
    """Close launch UI after a stale launch continuation sees an active pull."""
    self.add_log(f"Docker pull already in progress, skipping launch of {container_name}", color="yellow")
    self._end_lifecycle_operation(container_name)
    self._lifecycle_dialogs.schedule_safe_close_launch_references()
    self.loading_indicator.stop()

  def _create_docker_pull_callbacks(self, container_name: str):
    """Create callbacks for Docker image pull progress and completion."""
    def on_pull_success(result):
        if self._skip_lifecycle_callback_if_shutting_down("Docker pull success", container_name):
            return

        _stdout, stderr, return_code = result
        if return_code == 0:
            self._lifecycle_dialogs.set_docker_pull_complete(True, "Docker image pulled successfully")
            return

        error_msg = f"Failed to pull Docker image: {stderr}"
        self.add_log(error_msg, color="red")
        self._lifecycle_dialogs.set_docker_pull_complete(False, error_msg)

    def on_pull_error(error_msg):
        if self._skip_lifecycle_callback_if_shutting_down("Docker pull error", container_name):
            return

        self.add_log(f"Error pulling Docker image: {error_msg}", color="red")
        self._lifecycle_dialogs.set_docker_pull_complete(False, error_msg)

    def on_pull_output(line):
        if self._is_shutting_down():
            return

        self._lifecycle_dialogs.update_docker_pull_progress(line)

    return on_pull_success, on_pull_error, on_pull_output

  def _on_docker_pull_complete(self, success, message):
    """Handle Docker pull completion.
    
    Args:
        success: Whether the pull was successful
        message: Success or error message
    """
    launch_context = self._pending_launch_context_object()
    if self._is_shutting_down():
        if launch_context:
            self._skip_lifecycle_callback_if_shutting_down(
                "Docker pull completion",
                launch_context.container_name,
            )
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
        
    # The dialog should already be closing itself via set_pull_complete, but make sure
    # the launcher reference is cleared immediately.
    self._lifecycle_dialogs.close_docker_pull_reference()
    
    self._queue_ui_refresh()
    
    # If pull was successful, continue with the launch target captured before the pull.
    if success:
        if launch_context:
            self._continue_launch_after_successful_pull(launch_context)
        else:
            self.add_log("Docker pull completed without a pending launch target", color="yellow")
            self._end_lifecycle_operation()
    else:
        # Show error notification
        if launch_context:
            self._end_lifecycle_operation(launch_context.container_name)
        self.toast.show_notification(NotificationType.ERROR, f"Failed to pull Docker image: {message}")

  def _continue_launch_after_successful_pull(self, launch_context: LaunchContext) -> None:
    """Restore the captured launch target and continue after Docker pull."""
    container_name = launch_context.container_name
    volume_name = launch_context.volume_name
    self.docker_handler.set_container_name(container_name)
    self._select_container_by_name(container_name)
    container_config = self.config_manager.get_container(container_name)
    node_alias = container_config.node_alias if container_config and container_config.node_alias else None
    self._lifecycle_dialogs.show_launch_loading(node_alias)

    # Continue with container launch after pull - use a short timer to ensure UI is updated first.
    QTimer.singleShot(100, lambda: self._perform_container_launch_after_pull(container_name, volume_name))

  def _finalize_launch_failure(self, container_name: str, error_msg: str) -> None:
    """Close launch UI state and report a terminal launch failure."""
    self.loading_indicator.stop()
    self._lifecycle_dialogs.update_launch_progress(f"Error: {error_msg}", process_events=False)

    self._lifecycle_dialogs.close_reference("launcher_dialog")
    self._lifecycle_dialogs.close_reference("startup_dialog")
    self.add_log(error_msg, color="red")
    self.toast.show_notification(NotificationType.ERROR, error_msg)
    self._end_lifecycle_operation(container_name)

  def _finalize_launch_exception(self, container_name: str, error: Exception) -> None:
    """Report an unexpected launch exception through the normal failure finalizer."""
    self._finalize_launch_failure(container_name, f"Failed to launch container: {str(error)}")

  def _finalize_launch_success(self, container_name: str, volume_name: str) -> None:
    """Persist launch state, refresh visible UI, and close launch dialogs."""
    self._lifecycle_dialogs.update_launch_progress("Container launched, updating configuration...")
    self._mark_container_startup_grace(container_name)

    self.config_manager.update_last_used(container_name, datetime.now().isoformat())

    container_config = self.config_manager.get_container(container_name)
    if container_config and not container_config.volume:
      self.config_manager.update_volume(container_name, volume_name)
      self.add_log(f"Updated volume name in config: {volume_name}", debug=True)

    self._lifecycle_dialogs.update_launch_progress("Updating user interface...")

    self.post_launch_setup()
    self.refresh_node_info()
    self.plot_data(assume_running=True)
    self.update_toggle_button_text(assume_running=True)

    self.loading_indicator.stop()
    self._lifecycle_dialogs.update_launch_progress("Container launched successfully!")
    self._lifecycle_dialogs.close_launch_references()

    container_config = self.config_manager.get_container(container_name)
    node_alias = container_config.node_alias if container_config and container_config.node_alias else None
    self.toast.show_notification(NotificationType.SUCCESS, launch_success_notification(node_alias))
    self._end_lifecycle_operation(container_name)

  def _retry_launch_after_container_conflict(
    self,
    container_name: str,
    volume_name: str,
    error_msg: str,
    on_launch_success,
    on_launch_error,
  ) -> bool:
    """Remove a conflicting container and retry launch for Docker name conflicts."""
    if "Conflict" not in error_msg or "is already in use" not in error_msg:
      return False

    self._lifecycle_dialogs.update_launch_progress(
      "Container name conflict detected. Trying again with container removal..."
    )

    try:
      container_id = extract_conflicting_container_id(error_msg)
      if not container_id:
        return False

      self.add_log(
        f"Attempting to forcefully remove container with ID: {container_id}",
        color="yellow",
      )

      def on_conflict_remove_success(result):
        if self._skip_lifecycle_callback_if_shutting_down("conflict container removal", container_name):
          return

        _stdout, stderr, return_code = result
        if return_code != 0:
          self._finalize_launch_failure(
            container_name,
            f"Failed to remove conflicting container: {stderr}",
          )
          return

        self.add_log("Successfully removed conflicting container, retrying launch", color="blue")
        QTimer.singleShot(
          1000,
          lambda: self.docker_handler.launch_container_threaded(
            volume_name,
            on_launch_success,
            on_launch_error,
          ),
        )

      self.docker_handler.remove_container_threaded(
        container_id,
        on_conflict_remove_success,
        on_launch_error,
        force=True,
      )
      return True
    except Exception as retry_err:
      self.add_log(f"Failed to resolve container conflict: {retry_err}", color="red")
      return False

  def _create_post_pull_launch_callbacks(self, container_name: str, volume_name: str):
    """Create callbacks for the Docker launch worker that runs after image pull."""
    def on_launch_success(result):
      if self._skip_lifecycle_callback_if_shutting_down("launch success", container_name):
        return

      _stdout, stderr, return_code = result
      if return_code != 0:
        self._finalize_launch_failure(
          container_name,
          f"Failed to launch container: {stderr}",
        )
        return

      self._finalize_launch_success(container_name, volume_name)

    def on_launch_error(error_msg):
      if self._skip_lifecycle_callback_if_shutting_down("launch error", container_name):
        return

      self.loading_indicator.stop()

      if self._retry_launch_after_container_conflict(
        container_name,
        volume_name,
        error_msg,
        on_launch_success,
        on_launch_error,
      ):
        return

      self._finalize_launch_failure(
        container_name,
        f"Failed to launch container: {error_msg}",
      )

    return on_launch_success, on_launch_error

  def _perform_container_launch_after_pull(self, container_name, volume_name):
    """Perform the container launch operation after Docker pull is complete."""
    try:
        if self._skip_lifecycle_callback_if_shutting_down("post-pull launch continuation", container_name):
            return

        self.docker_handler.set_container_name(container_name)

        # Start loading indicator
        self.loading_indicator.start()
        
        # Update loading dialog with progress
        self._lifecycle_dialogs.update_launch_progress("Launching Docker container...")
        on_launch_success, on_launch_error = self._create_post_pull_launch_callbacks(
            container_name,
            volume_name,
        )
        
        # Launch the container in a thread (without pulling again)
        self.docker_handler.launch_container_threaded(volume_name, on_launch_success, on_launch_error)
        
    except Exception as e:
        self._finalize_launch_exception(container_name, e)

  def _containers_for_current_environment(self, containers):
    """Return saved containers that belong to the active edge-node image network."""
    return [
      container
      for container in containers
      if is_container_name_for_config(
        container.name,
        self.edge_image_config,
        default_container_name=self.default_container_name,
      )
    ]
  
  def refresh_container_list(self):
    """Refresh the container list in the combo box."""
    # Store current selection
    current_index = self.container_combo.currentIndex()
    selected_container = self.container_combo.itemData(current_index) if current_index >= 0 else None
    
    # Clear the combo box
    self.container_combo.clear()
    
    # Get containers from config and keep the active network isolated.
    all_containers = self.config_manager.get_all_containers()
    containers = self._containers_for_current_environment(all_containers)
    
    # If no containers found for this network, create a default one.
    if not containers:
        default_container = ContainerConfig(
            name=self.default_container_name,
            volume=self.default_volume_name,
            node_alias=self.default_container_name
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
    self._sync_apps_target_nodes()

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
        self._remember_container_running(container_name, is_running)
        
        # Log status changes for debugging
        if hasattr(self, 'container_last_run_status') and self.container_last_run_status != is_running:
            self.add_log(f'Container {container_name} status changed: {self.container_last_run_status} -> {is_running}', debug=True)
            self.container_last_run_status = is_running
            
        return is_running
    except Exception as e:
        self.add_log(f"Error checking if container is running: {str(e)}", debug=True, color="red")
        return False

  def _sync_apps_target_nodes(self) -> None:
    if not hasattr(self, "apps_page"):
      return
    nodes = []
    for container in self._containers_for_current_environment(self.config_manager.get_all_containers()):
      node_address = getattr(container, "node_address", "") or ""
      if not node_address:
        continue
      label = getattr(container, "node_alias", "") or getattr(container, "name", "") or node_address
      nodes.append(
        {
          "label": label,
          "node_address": node_address,
          "container_name": getattr(container, "name", ""),
        }
      )
    self.apps_page.set_target_node_options(nodes)


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
    
    self._queue_ui_refresh()
    
    return


  def update_resources_display(self):
    """Update the system resources display with current information."""
    try:
        # Use the new mixin helper methods for cleaner, more maintainable code
        memory_info = self.get_formatted_memory_info(compact=True)
        cpu_info = self.get_formatted_cpu_info(compact=True)
        storage_info = self.get_formatted_storage_info(compact=True)
        
        # Update displays
        self.memoryDisplay.setText(f"{MEMORY_LABEL} {memory_info}")
        self.vcpusDisplay.setText(f"{VCPUS_LABEL} {cpu_info}")
        self.storageDisplay.setText(f"{STORAGE_LABEL} {storage_info}")
        
        self.add_log("Host resources display updated: memory, CPU, and storage", debug=True)

    except Exception as e:
        self.add_log(f"Error updating resources display: {str(e)}", debug=True)
        # Set fallback values on error
        self.memoryDisplay.setText(f"{MEMORY_LABEL} {MEMORY_NOT_AVAILABLE}")
        self.vcpusDisplay.setText(f"{VCPUS_LABEL} {VCPUS_NOT_AVAILABLE}")
        self.storageDisplay.setText(f"{STORAGE_LABEL} {STORAGE_NOT_AVAILABLE}")

  def check_for_updates(self, verbose=True):
    """Start a non-blocking update check and prevent duplicate dialogs."""
    if self.__update_in_progress or self.__update_dialog_shown:
        if verbose:
            self.add_log("Update check skipped - update already in progress or dialog is shown", debug=True)
        return
    
    self.__update_in_progress = True

    try:
        if verbose:
            self.add_log("Checking for launcher updates...")

        thread = self._create_update_check_thread()
        self.__update_check_thread = thread
        thread.update_check_finished.connect(
            lambda latest_version, download_urls, checked_verbose=verbose: self._handle_update_check_result(
                latest_version,
                download_urls,
                checked_verbose,
            )
        )
        thread.update_check_failed.connect(self._handle_update_check_error)
        thread.finished.connect(lambda checked_thread=thread: self._cleanup_update_check_thread(checked_thread))
        thread.start()
    except Exception as e:
        self._handle_update_check_error(str(e))

  def _create_update_check_thread(self):
    """Create the worker used for network-bound update checks."""
    return UpdateCheckThread(self.get_latest_release_version)

  def _cleanup_update_check_thread(self, thread):
    if self.__update_check_thread is thread:
      self.__update_check_thread = None
    try:
      thread.deleteLater()
    except RuntimeError:
      pass

  def _cancel_update_check_thread(self):
    thread = self.__update_check_thread
    if thread is None:
      return

    try:
      if hasattr(thread, "isRunning") and thread.isRunning():
        thread.requestInterruption()
        thread.wait(100)
      if not hasattr(thread, "isRunning") or not thread.isRunning():
        self._cleanup_update_check_thread(thread)
    except RuntimeError:
      self.__update_check_thread = None

  def _handle_update_check_error(self, error_message):
    self.add_log(f"Error during update check: {error_message}", color="red")
    self.__update_dialog_shown = False
    self.__update_in_progress = False

  def _handle_update_check_result(self, latest_version, download_urls, verbose=True):
    try:
      latest_version = latest_version.lstrip('v').strip().replace('"', '').replace("'", '')

      if verbose:
        self.add_log(f'Obtained latest version: {latest_version}')

      if self._compare_versions(CURRENT_VERSION, latest_version):
        if not self.__update_dialog_shown:
          self.__update_dialog_shown = True

          try:
            reply = QMessageBox.question(
              self, 'Update Available',
              f'A new version v{latest_version} is available (current v{CURRENT_VERSION}). Do you want to update?',
              QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
              self._proceed_with_update(latest_version, download_urls)
            else:
              self.add_log("Update declined by user")
          finally:
            self.__update_dialog_shown = False
        else:
          self.add_log("Update dialog already shown, skipping duplicate", debug=True)
      else:
        if verbose:
          self.add_log("You are already using the latest version. Current: {}, Online: {}".format(CURRENT_VERSION, latest_version))
    except Exception as e:
      self.add_log(f"Error during update check: {str(e)}", color="red")
      self.__update_dialog_shown = False
    finally:
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
