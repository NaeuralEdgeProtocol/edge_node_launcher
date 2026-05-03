from utils.const import DARK_STYLESHEET, LIGHT_STYLESHEET


def test_stylesheets_do_not_use_unsupported_word_wrap_property():
    assert "word-wrap" not in DARK_STYLESHEET
    assert "word-wrap" not in LIGHT_STYLESHEET


def test_status_panels_are_styled_by_semantic_role():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QGroupBox[role="statusPanel"]' in stylesheet
        assert 'QGroupBox[role="resourcePanel"]' in stylesheet
        assert "border-radius: 8px;" in stylesheet
        assert "#infoBox {" not in stylesheet
        assert "#resourcesBox {" not in stylesheet


def test_sidebar_action_buttons_are_styled_by_hierarchy_role():
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        assert 'QPushButton[actionRole="primary"]' in stylesheet
        assert 'QPushButton[actionRole="secondary"]' in stylesheet
        assert 'QPushButton[actionRole="utility"]' in stylesheet
        assert "action_button_border_radius" not in stylesheet
