from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


_CONFIG_EDITOR_STYLE_COLORS = {
    False: {
        "page": "#F8FAFC",
        "surface": "#FFFFFF",
        "border": "#CBD5E1",
        "border_active": "#1B47F7",
        "text": "#1F2937",
        "muted": "#64748B",
        "editor_bg": "#FFFFFF",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
        "secondary": "#F7F9FC",
        "secondary_hover": "#EEF4FF",
    },
    True: {
        "page": "#0B1626",
        "surface": "#122033",
        "border": "#3E5876",
        "border_active": "#7DA2D6",
        "text": "#E8EEF8",
        "muted": "#93A4B8",
        "editor_bg": "#0F1B2B",
        "primary": "#1B47F7",
        "primary_hover": "#4458FF",
        "primary_text": "#FFFFFF",
        "secondary": "#243447",
        "secondary_hover": "#2E465E",
    },
}


_CONFIG_EDITOR_WIDGET_STYLE_TEMPLATE = """
QWidget#configEditorWidget {{
    background: transparent;
    color: {text};
}}
"""


_CONFIG_EDITOR_DIALOG_STYLE_TEMPLATE = """
QDialog#configEditorDialog {{
    background-color: {page};
    color: {text};
}}
"""

class ConfigEditorWidget(QWidget):
    """
    Widget for editing configuration files
    """
    # Signals
    config_saved = pyqtSignal(dict)  # Emitted when configuration is saved
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("configEditorWidget")
        self.setAccessibleName("Configuration editor")
        self._is_dark_theme = False
        
        # Initialize UI components
        self.btn_edit_config = QPushButton("Edit Configuration")
        self.btn_edit_config.setObjectName("configEditorEditButton")
        self.btn_edit_config.setAccessibleName("Edit configuration")
        self.btn_edit_config.setProperty("actionRole", "primary")
        self.btn_edit_config.setToolTip("Edit configuration")
        self.btn_edit_config.setMinimumHeight(36)
        self.btn_edit_config.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Setup UI layout
        self.init_ui()
        self.apply_theme(False)
        
        # Connect signals
        self.connect_signals()
    
    def init_ui(self):
        """Initialize the UI components and layout"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)

        self.config_group = QGroupBox("Configuration Files")
        self.config_group.setObjectName("configEditorGroup")
        self.config_group.setAccessibleName("Configuration files")
        self.config_group.setProperty("role", "configEditorPanel")
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(12, 16, 12, 12)
        group_layout.setSpacing(8)
        
        # Add edit config button
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_edit_config)
        group_layout.addLayout(button_layout)
        self.config_group.setLayout(group_layout)
        layout.addWidget(self.config_group)
        
        # Set layout
        self.setLayout(layout)
    
    def connect_signals(self):
        """Connect widget signals to slots"""
        self.btn_edit_config.clicked.connect(self.open_config_editor)

    def apply_theme(self, is_dark):
        """Apply compact component styling for standalone or embedded use."""
        self._is_dark_theme = bool(is_dark)
        colors = _CONFIG_EDITOR_STYLE_COLORS[self._is_dark_theme]
        self.setStyleSheet(_CONFIG_EDITOR_WIDGET_STYLE_TEMPLATE.format(**colors))
        self._apply_panel_styles()
    
    def open_config_editor(self, startup_config=None, app_config=None):
        """
        Open the configuration editor dialog
        
        Args:
            startup_config: Startup configuration text
            app_config: App configuration text
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Configuration Files")
        dialog.setObjectName("configEditorDialog")
        dialog.setAccessibleName("Edit Configuration Files")
        dialog.setMinimumSize(720, 520)
        dialog.resize(760, 560)
        dialog.setWindowModality(Qt.ApplicationModal)
        
        # Create tab widget
        tab_widget = QTabWidget()
        tab_widget.setObjectName("configEditorTabs")
        tab_widget.setAccessibleName("Configuration tabs")
        tab_widget.setDocumentMode(True)
        tab_widget.setStyleSheet(self._tab_stylesheet())
        
        startup_tab, startup_text_edit = self._create_config_tab(
            tab_object_name="startupConfigTab",
            tab_accessible_name="Startup configuration tab",
            label_text="Startup Configuration:",
            label_object_name="startupConfigLabel",
            label_accessible_name="Startup configuration label",
            editor_object_name="startupConfigText",
            editor_accessible_name="Startup configuration text",
            placeholder="Startup configuration is empty",
            value=startup_config,
        )
        app_tab, app_text_edit = self._create_config_tab(
            tab_object_name="appConfigTab",
            tab_accessible_name="App configuration tab",
            label_text="App Configuration:",
            label_object_name="appConfigLabel",
            label_accessible_name="App configuration label",
            editor_object_name="appConfigText",
            editor_accessible_name="App configuration text",
            placeholder="App configuration is empty",
            value=app_config,
        )
        
        # Add tabs to tab widget
        tab_widget.addTab(startup_tab, "Startup Config")
        tab_widget.addTab(app_tab, "App Config")
        
        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.setObjectName("configEditorDialogButtons")
        button_box.setAccessibleName("Configuration editor actions")
        save_button = button_box.button(QDialogButtonBox.Ok)
        save_button.setText("Save")
        save_button.setObjectName("configEditorSaveButton")
        save_button.setAccessibleName("Save configuration")
        save_button.setProperty("actionRole", "primary")
        save_button.setToolTip("Save configuration")
        save_button.setDefault(True)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setObjectName("configEditorCancelButton")
        cancel_button.setAccessibleName("Cancel configuration editing")
        cancel_button.setProperty("actionRole", "secondary")
        cancel_button.setToolTip("Cancel configuration editing")
        self._apply_dialog_action_styles(save_button, cancel_button)
        button_box.accepted.connect(lambda: self._save_config(startup_text_edit, app_text_edit, dialog))
        button_box.rejected.connect(dialog.reject)
        
        # Create dialog layout
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(16, 16, 16, 16)
        dialog_layout.setSpacing(12)
        dialog_layout.addWidget(tab_widget)
        dialog_layout.addWidget(button_box)
        dialog.setLayout(dialog_layout)
        dialog.setStyleSheet(self._dialog_stylesheet())
        
        # Show dialog
        return dialog.exec_()

    def _create_config_tab(
        self,
        tab_object_name,
        tab_accessible_name,
        label_text,
        label_object_name,
        label_accessible_name,
        editor_object_name,
        editor_accessible_name,
        placeholder,
        value,
    ):
        tab = QWidget()
        tab.setObjectName(tab_object_name)
        tab.setAccessibleName(tab_accessible_name)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName(label_object_name)
        label.setAccessibleName(label_accessible_name)
        label.setProperty("role", "configEditorLabel")

        text_edit = QTextEdit()
        text_edit.setObjectName(editor_object_name)
        text_edit.setAccessibleName(editor_accessible_name)
        text_edit.setProperty("role", "configEditorText")
        text_edit.setAcceptRichText(False)
        text_edit.setLineWrapMode(QTextEdit.NoWrap)
        text_edit.setPlaceholderText(placeholder)
        text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        text_edit.setTabStopDistance(text_edit.fontMetrics().horizontalAdvance("    "))
        if value:
            text_edit.setPlainText(value)

        layout.addWidget(label)
        layout.addWidget(text_edit)
        tab.setLayout(layout)
        self._apply_tab_page_styles(tab, label, text_edit)
        return tab, text_edit

    def _dialog_stylesheet(self):
        colors = _CONFIG_EDITOR_STYLE_COLORS[self._is_dark_theme]
        return _CONFIG_EDITOR_DIALOG_STYLE_TEMPLATE.format(**colors)

    def _apply_panel_styles(self):
        colors = _CONFIG_EDITOR_STYLE_COLORS[self._is_dark_theme]
        if not hasattr(self, "config_group"):
            return

        self.config_group.setStyleSheet(f"""
QGroupBox#configEditorGroup {{
    background-color: {colors["surface"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    margin-top: 16px;
    font-weight: 600;
}}
QGroupBox#configEditorGroup::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: 2px;
    padding: 0px 4px;
}}
""")
        self.btn_edit_config.setStyleSheet(f"""
QPushButton#configEditorEditButton {{
    background-color: {colors["primary"]};
    color: {colors["primary_text"]};
    border: 1px solid {colors["primary"]};
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 34px;
    font-weight: 600;
}}
QPushButton#configEditorEditButton:hover {{
    background-color: {colors["primary_hover"]};
    border-color: {colors["primary_hover"]};
}}
""")

    def _tab_stylesheet(self):
        colors = _CONFIG_EDITOR_STYLE_COLORS[self._is_dark_theme]
        return f"""
QTabWidget#configEditorTabs::pane {{
    background-color: {colors["surface"]};
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    top: -1px;
}}
QTabWidget#configEditorTabs QTabBar::tab {{
    background-color: {colors["secondary"]};
    color: {colors["muted"]};
    border: 1px solid {colors["border"]};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 14px;
    min-width: 120px;
    font-weight: 600;
}}
QTabWidget#configEditorTabs QTabBar::tab:selected {{
    background-color: {colors["surface"]};
    color: {colors["text"]};
    border-color: {colors["border_active"]};
}}
"""

    def _apply_tab_page_styles(self, tab, label, text_edit):
        colors = _CONFIG_EDITOR_STYLE_COLORS[self._is_dark_theme]
        tab.setStyleSheet(f"""
QWidget#{tab.objectName()} {{
    background-color: {colors["surface"]};
}}
""")
        label.setStyleSheet(f"""
QLabel {{
    color: {colors["muted"]};
    font-size: 10pt;
    font-weight: 600;
    background: transparent;
}}
""")
        text_edit.setStyleSheet(f"""
QTextEdit {{
    background-color: {colors["editor_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    padding: 10px;
    font-family: "Courier New";
    font-size: 9pt;
    selection-background-color: {colors["primary"]};
    selection-color: {colors["primary_text"]};
}}
QTextEdit:focus {{
    border-color: {colors["border_active"]};
}}
""")

    def _apply_dialog_action_styles(self, save_button, cancel_button):
        colors = _CONFIG_EDITOR_STYLE_COLORS[self._is_dark_theme]
        save_button.setStyleSheet(f"""
QPushButton {{
    background-color: {colors["primary"]};
    color: {colors["primary_text"]};
    border: 1px solid {colors["primary"]};
    border-radius: 8px;
    padding: 8px 14px;
    min-width: 82px;
    min-height: 32px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {colors["primary_hover"]};
    border-color: {colors["primary_hover"]};
}}
""")
        cancel_button.setStyleSheet(f"""
QPushButton {{
    background-color: {colors["secondary"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    padding: 8px 14px;
    min-width: 82px;
    min-height: 32px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {colors["secondary_hover"]};
    border-color: {colors["border_active"]};
}}
""")
    
    def _save_config(self, startup_text_edit, app_text_edit, dialog):
        """
        Save the edited configurations
        
        Args:
            startup_text_edit: QTextEdit containing startup config
            app_text_edit: QTextEdit containing app config
            dialog: Parent dialog
        """
        # Get config text
        startup_config = startup_text_edit.toPlainText()
        app_config = app_text_edit.toPlainText()
        
        # Emit signal with configs
        self.config_saved.emit({
            'startup_config': startup_config,
            'app_config': app_config
        })

        # Close dialog
        dialog.accept()
    
    def load_config(self, startup_config, app_config):
        """
        Load config text and open the editor
        
        Args:
            startup_config: Startup configuration text
            app_config: App configuration text
        """
        self.open_config_editor(startup_config, app_config)
