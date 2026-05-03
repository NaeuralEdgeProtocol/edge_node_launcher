from utils.const import DARK_STYLESHEET, LIGHT_STYLESHEET


def test_stylesheets_do_not_use_unsupported_word_wrap_property():
    assert "word-wrap" not in DARK_STYLESHEET
    assert "word-wrap" not in LIGHT_STYLESHEET
