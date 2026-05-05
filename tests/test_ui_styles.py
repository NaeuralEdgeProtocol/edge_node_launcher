from utils.const import DARK_COLORS, DARK_STYLESHEET, LIGHT_COLORS, LIGHT_STYLESHEET


def test_stylesheets_do_not_use_unsupported_word_wrap_property():
    assert "word-wrap" not in DARK_STYLESHEET
    assert "word-wrap" not in LIGHT_STYLESHEET


def test_status_panels_are_styled_by_semantic_role():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QGroupBox[role="statusPanel"]' in stylesheet
        assert 'QGroupBox[role="resourcePanel"]' in stylesheet
        assert 'QLabel[role="sidebarCardTitle"]' in stylesheet
        assert 'QLabel[role="edgeImageBadge"]' in stylesheet
        assert 'QLabel[role="nodeLifecycleState"]' in stylesheet
        assert 'QLabel[role="nodeRuntimePolicy"]' in stylesheet
        assert "border-radius: 8px;" in stylesheet
        assert "#infoBox {" not in stylesheet
        assert "#resourcesBox {" not in stylesheet


def test_sidebar_action_buttons_are_styled_by_hierarchy_role():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QPushButton[actionRole="primary"]' in stylesheet
        assert 'QPushButton[actionRole="secondary"]' in stylesheet
        assert 'QPushButton[actionRole="utility"]' in stylesheet
        assert "action_button_border_radius" not in stylesheet


def test_sidebar_section_labels_use_ui_typography():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QLabel[role="sidebarSection"]' in stylesheet
        assert 'QLabel[role="sidebarMutedText"]' in stylesheet
        assert 'font-family: "Segoe UI";' in stylesheet
        assert "font-size: 9pt;" in stylesheet


def test_settings_toggle_checkbox_uses_semantic_ui_styles():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QCheckBox[role="settingsToggle"]' in stylesheet
        assert 'QCheckBox[role="settingsToggle"]::indicator' in stylesheet
        assert 'font-family: "Segoe UI";' in stylesheet
        assert "font-weight: 500;" in stylesheet
        assert "image: url(:/icons/check.png)" not in stylesheet


def test_dashboard_activity_log_panel_uses_semantic_styles():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QWidget[role="activityLogPanel"]' in stylesheet
        assert 'QWidget[role="activityLogHeader"]' in stylesheet
        assert 'QLabel[role="dashboardSectionTitle"]' in stylesheet
        assert 'QToolButton[role="activityLogToolButton"]' in stylesheet
        assert "QTextEdit#logView QScrollBar:vertical" in stylesheet
        assert "QTextEdit#logView QScrollBar::handle:vertical" in stylesheet
        assert "QTextEdit#logView QScrollBar:horizontal" not in stylesheet
        assert "QTextEdit#logView QScrollBar::handle:horizontal" not in stylesheet
        assert 'font-family: "Segoe UI";' in stylesheet


def test_dialog_text_inputs_use_semantic_styles():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QLineEdit[role="dialogTextInput"]' in stylesheet
        assert 'QLineEdit[role="dialogTextInput"]:focus' in stylesheet
        assert "selection-background-color:" in stylesheet


def test_apps_page_controls_use_semantic_styles():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QWidget[role="appsWorkspace"]' in stylesheet
        assert 'QWidget[role="appActionBar"]' in stylesheet
        assert 'QWidget[role="appDeploymentPanel"]' in stylesheet
        assert 'QWidget[role="appAdvancedOptionsPanel"]' in stylesheet
        assert 'QWidget[role="appsDetailPanel"]' in stylesheet
        assert 'QTextBrowser[role="appsDetailText"]' in stylesheet
        assert "QScrollArea#appsWorkspaceScrollArea" in stylesheet
        assert "QScrollArea#appsWorkspaceScrollArea QScrollBar:vertical" in stylesheet
        assert 'QLineEdit[role="appTextInput"]' in stylesheet
        assert 'QPlainTextEdit[role="appTextInput"]' in stylesheet
        assert 'QComboBox[role="appCombo"]' in stylesheet
        assert 'QToolButton[role="appDisclosureButton"]' in stylesheet
        assert 'QLabel[role="appFormLabel"]' in stylesheet
        assert 'QLabel[role="appValidationMessage"]' in stylesheet
        assert "QTableWidget#appsTable" in stylesheet


def test_stop_button_text_uses_readable_dark_color_on_yellow():
    for colors in (DARK_COLORS, LIGHT_COLORS):
        assert colors["toggle_button_stop_text"] == "#1F2937"
        assert colors["toggle_button_stop_text"] != "#C4AC26"


def test_dark_theme_uses_neutral_surfaces_with_blue_as_accent():
    assert DARK_COLORS["widget_bg"] == "#0F1117"
    assert DARK_COLORS["graph_bg"] == "#14171F"
    assert DARK_COLORS["log_view_bg"] == "#151A23"
    assert DARK_COLORS["info_box_bg"] == "#151A23"
    assert DARK_COLORS["graph_border"] == "#2F3A4A"
    assert DARK_COLORS["graph_cpu_color"] == "#4EA3FF"
    assert DARK_COLORS["widget_bg"] not in {
        DARK_COLORS["graph_bg"],
        DARK_COLORS["log_view_bg"],
        DARK_COLORS["info_box_bg"],
    }
