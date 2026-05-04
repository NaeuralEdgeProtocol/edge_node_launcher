from ver import __VER__

FULL_DEBUG = True


# ============================================================================
# URLs
# ============================================================================
GITHUB_API_URL = 'https://api.github.com/repos/Ratio1/edge_node_launcher/releases/latest'

# ============================================================================
# DIRECTORY AND FILE CONSTANTS
# ============================================================================
HOME_SUBFOLDER = ".ratio1"
CONFIG_DIR = ".ratio1/edge_node_launcher"
E2_PEM_FILE = 'e2.pem'

# ============================================================================
# DOCKER CONSTANTS
# ============================================================================
DOCKER_VOLUME = 'ratio1_vol'
DOCKER_IMAGE = 'ratio1/edge_node'
DOCKER_TAG = 'mainnet'
DOCKER_CONTAINER_NAME = 'r1node'
DOCKER_VOLUME_PATH = '/edge_node/_local_cache'

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
REFRESH_TIME = 20_000
MAX_HISTORY_QUEUE = 5 * 60 // 10  # 5 minutes @ 10 seconds each hb
AUTO_UPDATE_CHECK_INTERVAL = 3600 # 1 hour
DOCKER_IMAGE_AUTO_UPDATE_CHECK_INTERVAL = 300  # 5 minutes
MAX_ALIAS_LENGTH = 15  # Maximum length for aliases (node name and authorized addresses)
NODE_INFO_FAILURE_THRESHOLD = 5  # Number of consecutive get_node_info failures before container restart

# ============================================================================
# NODE REQUIREMENTS
# ============================================================================
MIN_NODE_RAM_GB = 16  # Minimum RAM requirement per node in GB

# ============================================================================
# UI TEXT CONSTANTS
# ============================================================================
# Window and titles
WINDOW_TITLE = f'Edge Node Manager v{__VER__}'

# Button texts
LAUNCH_CONTAINER_BUTTON_TEXT = 'Start Edge Node'
STOP_CONTAINER_BUTTON_TEXT = 'Stop Edge Node'
DAPP_BUTTON_TEXT = 'Launch dApp'
EXPLORER_BUTTON_TEXT = 'Ratio1 Explorer'
DELETE_AND_RESTART_BUTTON_TEXT = 'Reset Node Address'
REFRESH_LOCAL_ADDRESS_BUTTON_TEXT = 'Refresh Local Address'
COPY_ADDRESS_BUTTON_TEXT = 'Copy Address'
COPY_ETHEREUM_ADDRESS_BUTTON_TEXT = 'Copy Ethereum Address'
RENAME_NODE_BUTTON_TEXT = 'Change Node Alias'
LIGHT_DASHBOARD_BUTTON_TEXT = 'Switch to Light Theme'
DARK_DASHBOARD_BUTTON_TEXT = 'Switch to Dark Theme'
DOWNLOAD_DOCKER_BUTTON_TEXT = 'Download Docker'

# Label texts
LOCAL_NODE_ADDRESS_LABEL_TEXT = 'Local Node Address'
UPTIME_LABEL = 'Uptime:'
EPOCH_LABEL = 'Epoch:'
EPOCH_AVAIL_LABEL = 'Epoch availability:'
NODE_VERSION_LABEL = 'Version:'

# Resources box labels
RESOURCES_BOX_TITLE = 'System Resources'
MEMORY_LABEL = 'Memory:'
VCPUS_LABEL = 'vCPUs:'
STORAGE_LABEL = 'Storage:'
MEMORY_NOT_AVAILABLE = 'N/A'
VCPUS_NOT_AVAILABLE = 'N/A'
STORAGE_NOT_AVAILABLE = 'N/A'

# Status texts
NO_CONTAINER_SELECTED_TEXT = 'Address: No container selected'
ETH_ADDRESS_NOT_AVAILABLE_TEXT = 'ETH Address: Not available'
NODE_NOT_RUNNING_TEXT = 'Address: Node not running'
ERROR_GETTING_NODE_INFO_TEXT = 'Address: Error getting node info'
NAME_PREFIX_TEXT = 'Name: '
ADDRESS_PREFIX_TEXT = 'Address: '
LOCAL_ADDRESS_PREFIX_TEXT = 'Local Address: '
ETH_ADDRESS_PREFIX_TEXT = 'ETH Address: '
UPTIME_PREFIX_TEXT = 'Uptime: '
EMPTY_DASH_TEXT = '-'

# Button states
NO_CONTAINER_FOUND_TEXT = 'No Container Found'
HOST_OFFLINE_TEXT = 'Host Offline'
CHECKING_HOST_TEXT = 'Checking Host...'
SSH_ERROR_TEXT = 'SSH Error'
DOCKER_NOT_FOUND_TEXT = 'Docker Not Found'
DOCKER_NOT_RUNNING_TEXT = 'Docker Not Running'
DOCKER_CHECK_FAILED_TEXT = 'Docker Check Failed'
CONTAINER_CHECK_FAILED_TEXT = 'Container Check Failed'
CONNECTION_FAILED_TEXT = 'Connection Failed'
SELECT_HOST_TEXT = 'Select Host...'

# Plot titles
CPU_LOAD_TITLE = 'CPU Load'
MEMORY_USAGE_TITLE = 'Memory Usage'
GPU_LOAD_TITLE = 'GPU Load'
GPU_MEMORY_LOAD_TITLE = 'GPU Memory Load'

# ============================================================================
# TOOLTIP TEXTS
# ============================================================================
ADD_NODE_TOOLTIP = 'Create another local edge node'
TOGGLE_NODE_TOOLTIP = 'Start or stop the selected edge node container'
DAPP_TOOLTIP = 'Open the Ratio1 dApp for the selected network'
EXPLORER_TOOLTIP = 'Ratio1 Explorer is not yet implemented'
REFRESH_NODE_INFO_TOOLTIP = 'Refresh node status, addresses, metrics, and resources'
RENAME_NODE_TOOLTIP = 'Rename the selected node alias shown in the launcher'
THEME_TOGGLE_TOOLTIP = 'Switch between dark and light themes'
FORCE_DEBUG_TOOLTIP = 'Run node containers with debug mode enabled'
DOCKER_DOWNLOAD_TOOLTIP = 'Ratio1 Edge Node requires Docker Desktop running in parallel'
COPY_ADDRESS_TOOLTIP = 'Copy address'
COPY_ETH_ADDRESS_TOOLTIP = 'Copy Ethereum address'

# ============================================================================
# DIALOG TEXTS
# ============================================================================
# Dialog titles
ADD_NEW_NODE_DIALOG_TITLE = 'Add New Node'
RENAME_NODE_DIALOG_TITLE = 'Rename Node'
EDIT_AUTHORIZED_ADDRESSES_DIALOG_TITLE = 'Edit Authorized Addresses'
VIEW_CONFIG_FILES_DIALOG_TITLE = 'View Configuration Files'
EDIT_ENV_FILE_DIALOG_TITLE = 'Edit .env File'

# Dialog messages
RESET_NODE_CONFIRMATION_TEXT = 'Are you sure you want to reset this node?'
ENTER_NODE_NAME_TEXT = 'Enter a friendly name for this node:'
RESETTING_NODE_ADDRESS_TEXT = 'Resetting node address...'

# RAM checking messages
INSUFFICIENT_RAM_TITLE = 'Cannot Add New Node'
INSUFFICIENT_RAM_MESSAGE = 'Cannot add a new node - maximum capacity reached.\n\nSystem Information:\n- Total RAM: {total_gb:.1f} GB\n- Maximum Nodes Supported: {max_nodes} ({total_gb:.1f} GB / {min_ram_gb} GB per node)\n- Current Nodes: {current_nodes}\n\nEach node requires {min_ram_gb} GB of RAM.'
RAM_CHECK_ERROR_TITLE = 'RAM Check Error'
RAM_CHECK_ERROR_MESSAGE = 'Unable to determine available system RAM.\n\nWould you like to proceed anyway?'

# Input placeholders
ENTER_NODE_NAME_PLACEHOLDER = 'Enter node name'
ENTER_FRIENDLY_NODE_NAME_PLACEHOLDER = 'Enter a friendly name for your node'
ENTER_ADDRESS_PLACEHOLDER = 'Enter address'
ENTER_ALIAS_PLACEHOLDER = 'Enter alias'

# ============================================================================
# LOG MESSAGES
# ============================================================================
SUCCESS_NODE_CREATION_LOG = 'Successfully created new node: {}'
FAILED_NODE_CREATION_LOG = 'Failed to create new node: {}'

# ============================================================================
# ENVIRONMENT SETTINGS
# ============================================================================
ENVIRONMENTS = {
    'mainnet': 'Mainnet',
    'testnet': 'Testnet',
    'devnet': 'Devnet'
}

DAPP_URLS = {
    'mainnet': 'https://app.ratio1.ai/',
    'testnet': 'https://testnet-app.ratio1.ai/',
    'devnet': 'https://devnet-app.ratio1.ai/'
}

DEFAULT_ENVIRONMENT = 'mainnet'

# ============================================================================
# TEMPLATES
# ============================================================================
ENV_TEMPLATE = '''
# LOCAL FILE TEMPLATE

# admin
EE_ID={}
EE_SUPERVISOR=false
EE_DEVICE=cuda:0


# MinIO / S3
EE_MINIO_ENDPOINT=endpoint
EE_MINIO_ACCESS_KEY=access_key
EE_MINIO_SECRET_KEY=secret_key
EE_MINIO_SECURE=false
EE_MINIO_UPLOAD_BUCKET=bucket


# MQTT
EE_MQTT_PORT=8883
EE_MQTT_SUBTOPIC=address
EE_MQTT_CERT=

EE_NGROK_AUTH_TOKEN=ngrok-auth-token
EE_NGROK_EDGE_LABEL=ngrok-edge-label

# Misc
EE_GITVER=token_for_accessing_private_repositories
EE_OPENAI=token_for_accessing_openai_api
EE_HF_TOKEN=token_for_accessing_huggingface_api
'''

# ============================================================================
# STYLESHEETS
# ============================================================================

# Common style properties that don't depend on theme
COMMON_STYLES = {
    "font_size": "14px",
    "border_radius": "15px",
    "progress_height": "30px",
    "button_padding": "10px 20px",
    "button_font_size": "16px",
    "button_margin": "4px 5px",
    "button_border_radius": "15px",
    "action_button_border_radius": "8px",
    "panel_border_radius": "8px",
    "combo_border_radius": "15px",
    "combo_padding": "4px",
    "combo_min_width": "100px",
    "combo_dropdown_width": "20px",
    "text_align_center": "center",
    "font_weight_normal": "normal",
    "font_weight_bold": "bold",
    "button_font_weight": "normal",
    "info_box_font_weight": "normal"
}

COMMON_COLORS = {
    "start_button_bg": "#00FF00",
    "stop_button_bg": "#F44336",
}

# Color definitions for dark theme
DARK_COLORS = {
    "text_color": "white",
    "bg_color": "#2b2b2b",
    "border_color": "#555555",
    "hover_color": "#3b3b3b",
    "button_bg": "#0071EA",
    "button_border": "transparent",
    "button_hover": "#0679F3",
    "primary_action_bg": "#1B47F7",
    "primary_action_hover": "#4458FF",
    "primary_action_text": "#FFFFFF",
    "primary_action_border": "transparent",
    "secondary_action_bg": "#243447",
    "secondary_action_hover": "#2E465E",
    "secondary_action_text": "#E8EEF8",
    "secondary_action_border": "#40607A",
    "utility_action_bg": "transparent",
    "utility_action_hover": "#263241",
    "utility_action_text": "#C7D4E8",
    "utility_action_border": "#395069",
    "progress_border": "#1E90FF",
    "progress_chunk": "#1E90FF",
    "widget_bg": "#000C29",
    "debug_checkbox_color": "white",  # Orange for dark theme debug checkbox
    
    # Log view specific colors
    "log_view_bg": "#04254F",
    "log_view_text": "white",
    "log_view_border": "#1E90FF",
    
    # Info box specific colors
    "info_box_bg": "#04254F",
    "info_box_text": "white",
    "info_box_border": "#1E90FF",
    
    # Graph specific colors
    "graph_bg": "#001A3A",
    "graph_border": "#10386A",
    "graph_text": "white",
    "graph_cpu_color": "#1E90FF",
    "graph_memory_color": "#4CAF50",
    "graph_gpu_color": "#FFD700",
    "graph_gpu_memory_color": "#FF6B6B",
    
    "text_edit_bg": "#FFFFFF",
    "text_edit_border": "#D3D3D3",
    "plot_bg": "#FFFFFF",
    "plot_border": "#A9A9A9",
    "green_highlight": "red",
    "button_copy_address_bg": "transparent",
    "add_node_button_bg": "#0071EA",
    "add_node_button_border": "transparent",
    "add_node_button_hover": "#0679F3",
    "add_node_button_hover_text": "#FFFFFF",
    "confirm_button_bg": "#1B47F7",
    "confirm_button_border": "#45A049",
    "confirm_button_hover": "#45A049",
    "cancel_button_bg": "#F44336",
    "cancel_button_border": "#D32F2F",
    "cancel_button_hover": "#D32F2F",
    
    # Toggle button states
    "toggle_button_start_bg": "#1B47F7",
    "toggle_button_start_hover": "#4458FF",
    "toggle_button_start_border": "transparent",
    "toggle_button_start_text": "white",
    "toggle_button_stop_bg": "#FADC33",
    "toggle_button_stop_hover": "#FFE138",
    "toggle_button_stop_border": "transparent",
    "toggle_button_stop_text": "#1F2937",
    "toggle_button_disabled_bg": "gray",
    "toggle_button_disabled_hover": "darkgray",
    "toggle_button_disabled_border": "darkgray",
    "toggle_button_disabled_text": "black",
    "toggle_button_border": "#87CEEB",

    # ComboBox popup specific colors
    "combo_bg": "#F9F9F9",
    "combo_border": "#10386A",
    "combo_hover_bg": "#F0F7FF",
    "combo_hover_border": "#0071EA",
    "combo_arrow_color": "transparent",
    "combo_dropdown_bg": "#FFFFFF",
    "combo_dropdown_select_bg": "red",
    "combo_dropdown_select_color": "black",
    "combobox_popup_border_color": "#1E90FF",
    "combobox_popup_bg_color": "#04254F",
    "combobox_popup_item_hover_bg": "transparent",
    "combobox_popup_item_selected_bg": "#1B47F7",
    "combobox_popup_item_selected_text": "white",
    "combobox_text_color": "#333333",
    "combo_rectangle_text_color": "white",
    "section_label_text": "#9DB6D8",
    "section_label_border": "#10386A",
}

# Color definitions for light theme
LIGHT_COLORS = {
    "text_color": "white",
    "bg_color": "white",
    "border_color": "#cccccc",
    "hover_color": "#f5f5f5",
    "button_bg": "#0071EA",
    "button_border": "transparent",
    "button_hover": "#0679F3",
    "primary_action_bg": "#1B47F7",
    "primary_action_hover": "#4458FF",
    "primary_action_text": "#FFFFFF",
    "primary_action_border": "transparent",
    "secondary_action_bg": "#F7F9FC",
    "secondary_action_hover": "#EEF4FF",
    "secondary_action_text": "#1F2937",
    "secondary_action_border": "#CBD5E1",
    "utility_action_bg": "transparent",
    "utility_action_hover": "#F1F5F9",
    "utility_action_text": "#334155",
    "utility_action_border": "#CBD5E1",
    "progress_border": "#D3D3D3",
    "progress_chunk": "#D3D3D3",
    "widget_bg": "#E6E6EA",
    "debug_checkbox_color": "black",  # Blue for light theme debug checkbox
    
    # Log view specific colors
    "log_view_bg": "#FFFFFF",
    "log_view_text": "black",
    "log_view_border": "#D3D3D3",
    
    # Info box specific colors
    "info_box_bg": "#FFFFFF",
    "info_box_text": "black",
    "info_box_border": "#D3D3D3",
    
    # Graph specific colors
    "graph_bg": "#F4F4F8",
    "graph_border": "#D3D3D3",
    "graph_text": "black",
    "graph_cpu_color": "#0066CC",
    "graph_memory_color": "#2E8B57",
    "graph_gpu_color": "#DAA520",
    "graph_gpu_memory_color": "#CD5C5C",
    
    "text_edit_bg": "#FFFFFF",
    "text_edit_border": "#D3D3D3",
    "plot_bg": "#FFFFFF",
    "plot_border": "#A9A9A9",
    "green_highlight": "red",
    "button_copy_address_bg": "transparent",
    "add_node_button_bg": "#0071EA",
    "add_node_button_border": "transparent",
    "add_node_button_hover": "#0679F3",
    "add_node_button_hover_text": "#FFFFFF",
    "confirm_button_bg": "#1B47F7",
    "confirm_button_border": "#45A049",
    "confirm_button_hover": "#45A049",
    "cancel_button_bg": "#F44336",
    "cancel_button_border": "#D32F2F",
    "cancel_button_hover": "#D32F2F",
    
    # Toggle button states
    "toggle_button_start_bg": "#1B47F7",
    "toggle_button_start_hover": "#4458FF",
    "toggle_button_start_border": "transparent",
    "toggle_button_start_text": "white",
    "toggle_button_stop_bg": "#FADC33",
    "toggle_button_stop_hover": "#FFE138",
    "toggle_button_stop_border": "transparent",
    "toggle_button_stop_text": "#1F2937",
    "toggle_button_disabled_bg": "gray",
    "toggle_button_disabled_hover": "darkgray",
    "toggle_button_disabled_border": "darkgray",
    "toggle_button_disabled_text": "black",
    "toggle_button_border": "#87CEEB",

    # ComboBox popup specific colors
    "combo_bg": "#F9F9F9",
    "combo_border": "#D0D0D0",
    "combo_hover_bg": "#F0F7FF",
    "combo_hover_border": "#1B47F7",
    "combo_arrow_color": "transparent",
    "combo_dropdown_bg": "#FFFFFF",
    "combo_dropdown_select_bg": "red",
    "combo_dropdown_select_color": "black",
    "combobox_popup_border_color": "#D0D0D0",
    "combobox_popup_bg_color": "#F4F4F8",
    "combobox_popup_item_hover_bg": "transparent",
    "combobox_popup_item_selected_bg": "#1B47F7",
    "combobox_popup_item_selected_text": "white",
    "combobox_text_color": "#333333",
    "combo_rectangle_text_color": "#1B47F7",
    "section_label_text": "#5F6B7A",
    "section_label_border": "#D8DEE8",
}

# Merge common styles with theme-specific colors
DARK_THEME = {**COMMON_STYLES, **DARK_COLORS}
LIGHT_THEME = {**COMMON_STYLES, **LIGHT_COLORS}

# Common stylesheet template with placeholders for theme-specific values
COMMON_STYLESHEET_TEMPLATE = """
  QLabel {{
    font-size: {font_size};
    color: {text_color};
  }}
  QProgressBar {{
    border: 1px solid {progress_border};
    border-radius: {border_radius};
    text-align: {text_align_center};
    height: {progress_height};
    color: {text_color};
  }}
  QProgressBar::chunk {{
    background-color: {progress_chunk};
  }}
  QDialog, QWidget {{
    background-color: {widget_bg};
  }}
  QTextEdit {{
    background-color: {log_view_bg};
    color: {log_view_text};
    font-size: {font_size};
    border: 1px solid {log_view_border};
    border-radius: {border_radius};
    padding: 8px;
    margin-bottom: 6px;
  }}
  PlotWidget, QWidget[class="plot-container"] {{
    background-color: {graph_bg};
    border: 1px solid {graph_border};
    border-radius: {border_radius};
    padding: 0px;
  }}
  QLabel[role="metricPlotTitle"] {{
    color: {graph_text};
    background-color: transparent;
    font-size: 13px;
    font-weight: bold;
    padding: 0px;
  }}
  QLabel[role="metricPlotEmptyState"] {{
    color: {graph_text};
    background-color: transparent;
    font-size: 12px;
    padding: 0px 0px 4px 0px;
  }}
  PlotWidget > * {{
    background-color: transparent;
  }}
  PlotWidget LabelItem {{
    color: {graph_text};
  }}
  QComboBox {{
    color: {text_color};
    background-color: {combo_bg};
    border: 1px solid {combo_border};
    border-radius: {combo_border_radius};
    padding: 0px;
    margin-left: 6px;
    margin-right: 6px;
    min-width: {combo_min_width};
    min-height: 32px;
    max-height: 32px;
    font-family: "Courier New";
    font-size: 10pt;
    text-align: center;
  }}
  QComboBox:hover {{
    background-color: {combo_hover_bg};
    border: 1px solid {combo_hover_border};
  }}
  QComboBox:focus {{
    border: 1px solid {combo_hover_border};
  }}
  QComboBox::drop-down {{
    border: none;
    width: 0px;
  }}
  QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
  }}
  QComboBox QAbstractItemView {{
    background-color: {combo_dropdown_bg};
    color: {text_color};
    selection-background-color: {combo_dropdown_select_bg};
    selection-color: {combo_dropdown_select_color};
    border: 1px solid {combo_border};
    border-radius: {border_radius};
    padding: 5px;
    min-width: 190px;
  }}
  QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 3px 5px;
    text-align: center;
  }}
  QComboBox QAbstractItemView::item:hover {{
    background-color: {combo_hover_bg};
  }}
  QComboBox QAbstractItemView::item:selected {{
    background-color: {combo_dropdown_select_bg};
  }}
  QLabel[role="sidebarSection"] {{
    color: {section_label_text};
    background-color: transparent;
    border-bottom: 1px solid {section_label_border};
    font-family: "Segoe UI";
    font-size: 9pt;
    font-weight: 600;
    padding: 12px 8px 4px 8px;
    margin: 10px 6px 2px 6px;
  }}
  QScrollArea#sidebarScrollArea {{
    background-color: transparent;
    border: none;
  }}
  QScrollArea#sidebarScrollArea QWidget#sidebarPanel {{
    background-color: transparent;
  }}
  QScrollArea#sidebarScrollArea QScrollBar:vertical {{
    background-color: transparent;
    border: none;
    width: 10px;
    margin: 4px 2px 4px 0px;
  }}
  QScrollArea#sidebarScrollArea QScrollBar::handle:vertical {{
    background-color: {section_label_border};
    border-radius: 4px;
    min-height: 32px;
  }}
  QScrollArea#sidebarScrollArea QScrollBar::handle:vertical:hover {{
    background-color: {combo_hover_border};
  }}
  QScrollArea#sidebarScrollArea QScrollBar::add-line:vertical,
  QScrollArea#sidebarScrollArea QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
    background: transparent;
  }}
  QScrollArea#sidebarScrollArea QScrollBar::add-page:vertical,
  QScrollArea#sidebarScrollArea QScrollBar::sub-page:vertical {{
    background: transparent;
  }}
  QPushButton {{
    background-color: {button_bg}; 
    color: {text_color}; 
    border: 1px solid {button_border}; 
    padding: {button_padding}; 
    font-size: {button_font_size};
    font-weight: {button_font_weight}; 
    margin: {button_margin};
    margin-left: 6px;
    margin-right: 6px;
    border-radius: {button_border_radius};
  }}
  QPushButton:hover {{
    background-color: {button_hover};
  }}
  QPushButton[actionRole="primary"] {{
    background-color: {primary_action_bg};
    color: {primary_action_text};
    border: 1px solid {primary_action_border};
    border-radius: {action_button_border_radius};
    padding: 8px 12px;
    min-height: 38px;
    font-size: {button_font_size};
    font-weight: bold;
  }}
  QPushButton[actionRole="primary"]:hover {{
    background-color: {primary_action_hover};
  }}
  QPushButton[actionRole="secondary"] {{
    background-color: {secondary_action_bg};
    color: {secondary_action_text};
    border: 1px solid {secondary_action_border};
    border-radius: {action_button_border_radius};
    padding: 7px 12px;
    min-height: 34px;
    font-size: {button_font_size};
    font-weight: {button_font_weight};
  }}
  QPushButton[actionRole="secondary"]:hover {{
    background-color: {secondary_action_hover};
  }}
  QPushButton[actionRole="utility"] {{
    background-color: {utility_action_bg};
    color: {utility_action_text};
    border: 1px solid {utility_action_border};
    border-radius: {action_button_border_radius};
    padding: 7px 12px;
    min-height: 32px;
    font-size: {button_font_size};
    font-weight: {button_font_weight};
  }}
  QPushButton[actionRole="utility"]:hover {{
    background-color: {utility_action_hover};
  }}
  QCheckBox[role="settingsToggle"] {{
    color: {utility_action_text};
    background-color: transparent;
    border-radius: 6px;
    font-family: "Segoe UI";
    font-size: 9pt;
    font-weight: 500;
    spacing: 8px;
    padding: 6px 8px;
    margin: 4px 6px 0px 6px;
    min-height: 28px;
  }}
  QCheckBox[role="settingsToggle"]:hover {{
    background-color: {utility_action_hover};
  }}
  QCheckBox[role="settingsToggle"]::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {utility_action_border};
    background-color: {secondary_action_bg};
  }}
  QCheckBox[role="settingsToggle"]::indicator:unchecked:hover {{
    border-color: {combo_hover_border};
  }}
  QCheckBox[role="settingsToggle"]::indicator:checked {{
    background-color: {primary_action_bg};
    border-color: {primary_action_bg};
  }}
  QCheckBox[role="settingsToggle"]::indicator:checked:hover {{
    background-color: {primary_action_hover};
    border-color: {primary_action_hover};
  }}
  QPushButton[type="confirm"] {{
    background-color: {confirm_button_bg};
    border: 1px solid {confirm_button_border};
  }}
  QPushButton[type="confirm"]:hover {{
    background-color: {confirm_button_hover};
  }}
  QPushButton[type="cancel"] {{
    background-color: {cancel_button_bg};
    border: 1px solid {cancel_button_border};
  }}
  QPushButton[type="cancel"]:hover {{
    background-color: {cancel_button_hover};
  }}
  #copyAddrButton, #copyEthButton {{
    background-color: {button_copy_address_bg};
    border: none;
    padding: 2px;
    margin: 2px;
    margin-left: 2px;
    margin-right: 2px;
    icon-size: 20px;
    min-width: 28px;
    min-height: 28px;
  }}
  #copyAddrButton:hover, #copyEthButton:hover {{
    background-color: rgba(128, 128, 128, 0.2);
    border-radius: 4px;
  }}
  #startNodeButton {{
    min-height: 40px;
  }}
  #addNodeButton {{
    min-height: 32px;
  }}
  #toggleContainerButton {{
    min-height: 40px;
    max-height: 40px;
  }}
  QGroupBox[role="statusPanel"],
  QGroupBox[role="resourcePanel"] {{
    background-color: {info_box_bg};
    border: 1px solid {info_box_border};
    border-radius: {panel_border_radius};
    margin: 6px;
    margin-left: 5px;
    margin-right: 5px;
    padding: 8px;
    color: {info_box_text};
  }}
  QGroupBox[role="resourcePanel"] {{
    min-height: 60px;
  }}
  QGroupBox[role="statusPanel"] QLabel,
  QGroupBox[role="resourcePanel"] QLabel {{
    color: {info_box_text};
    font-family: "Segoe UI";
    font-size: 10pt;
    font-weight: {info_box_font_weight};
    margin: 2px;
    background-color: transparent;
  }}
  QGroupBox[role="statusPanel"] QLabel[role="sidebarCardTitle"],
  QGroupBox[role="resourcePanel"] QLabel[role="sidebarCardTitle"] {{
    color: {section_label_text};
    border-bottom: 1px solid {section_label_border};
    font-family: "Segoe UI";
    font-size: 9pt;
    font-weight: 600;
    padding: 0px 4px 6px 4px;
    margin: 0px 2px 4px 2px;
  }}
  QGroupBox[role="statusPanel"] QLabel[statusField="address"] {{
    font-family: "Courier New";
  }}
  QGroupBox[role="statusPanel"] QLabel[statusField="metadata"] {{
    font-family: "Segoe UI";
  }}
  QGroupBox[role="resourcePanel"] QLabel {{
    padding: 2px 4px;
  }}
  QGroupBox[role="resourcePanel"] QLabel[resourceField="memory"],
  QGroupBox[role="resourcePanel"] QLabel[resourceField="cpu"],
  QGroupBox[role="resourcePanel"] QLabel[resourceField="storage"] {{
    font-family: "Segoe UI";
  }}
  QGroupBox[role="statusPanel"] QPushButton {{
    background-color: {button_copy_address_bg};
    border: none;
    padding: 0px;
    margin: 0px;
    margin-left: 0px;
    margin-right: 0px;
    color: {text_color};
  }}

"""

ADDITIONAL_STYLES = ""

# Apply the common template with dark theme values
DARK_STYLESHEET = COMMON_STYLESHEET_TEMPLATE.format(**DARK_THEME) + ADDITIONAL_STYLES + """
  QDialog QLabel {
    color: white;
  }
"""

# Apply the common template with light theme values, with additional light-specific styles
LIGHT_STYLESHEET = COMMON_STYLESHEET_TEMPLATE.format(**LIGHT_THEME) + ADDITIONAL_STYLES + """
  QDialog QLabel {
    color: black;
  }
  
"""

# Notification messages
NOTIFICATION_TITLE_STRINGS_ENUM = {
    'success': 'Success',
    'error': 'Error',
    'warning': 'Warning',
    'info': 'Information'
}
NOTIFICATION_ADDRESS_COPIED = "Address {address} copied to clipboard"
NOTIFICATION_ADDRESS_COPY_FAILED = "No address available to copy. Try again after launching the Edge Node."

# Add specific button selectors with 5px left and right margins
#addNodeButton, #toggleContainerButton, #launchDAppButton, #explorerButton, #renameButton, #themeToggleButton {{
#    margin-left: 5px;
#    margin-right: 5px;
#}}
#
#infoBox {{
#    margin-left: 5px;
#    margin-right: 5px;
#}}
