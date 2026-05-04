from utils.const import DARK_COLORS, DARK_STYLESHEET, LIGHT_COLORS, LIGHT_STYLESHEET


def test_stylesheets_do_not_use_unsupported_word_wrap_property():
    assert "word-wrap" not in DARK_STYLESHEET
    assert "word-wrap" not in LIGHT_STYLESHEET


def test_status_panels_are_styled_by_semantic_role():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QGroupBox[role="statusPanel"]' in stylesheet
        assert 'QGroupBox[role="resourcePanel"]' in stylesheet
        assert 'QLabel[role="sidebarCardTitle"]' in stylesheet
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
        assert 'font-family: "Segoe UI";' in stylesheet
        assert "font-size: 9pt;" in stylesheet


def test_settings_toggle_checkbox_uses_semantic_ui_styles():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QCheckBox[role="settingsToggle"]' in stylesheet
        assert 'QCheckBox[role="settingsToggle"]::indicator' in stylesheet
        assert 'font-family: "Segoe UI";' in stylesheet
        assert "font-weight: 500;" in stylesheet
        assert "image: url(:/icons/check.png)" not in stylesheet


def test_stop_button_text_uses_readable_dark_color_on_yellow():
    for colors in (DARK_COLORS, LIGHT_COLORS):
        assert colors["toggle_button_stop_text"] == "#1F2937"
        assert colors["toggle_button_stop_text"] != "#C4AC26"
