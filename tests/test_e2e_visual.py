import pytest

from tools import e2e_visual


def test_assert_title_bar_visible_accepts_missing_legacy_field():
    e2e_visual.assert_title_bar_visible({"title": "Legacy runner"})


def test_assert_title_bar_visible_rejects_hidden_title_bar():
    with pytest.raises(AssertionError, match="title bar is outside"):
        e2e_visual.assert_title_bar_visible(
            {
                "title": "Launcher",
                "title_bar_visible": False,
                "frame": {"x": 10, "y": 0, "w": 300, "h": 240},
                "available": {"x": 0, "y": 40, "w": 500, "h": 400},
            }
        )
