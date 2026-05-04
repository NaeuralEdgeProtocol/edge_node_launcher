import pytest
from PyQt5.QtWidgets import QComboBox, QPushButton, QWidget

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


def test_lifecycle_controls_snapshot_and_busy_assertion(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)

    parent.add_node_button = QPushButton("Add New Node", parent)
    parent.renameNodeButton = QPushButton("Change Node Alias", parent)
    parent.toggleButton = QPushButton("Starting...", parent)
    parent.refreshButton = QPushButton("Refresh Node Info", parent)
    parent.container_combo = QComboBox(parent)
    parent.themeToggleButton = QPushButton("Switch to Light Theme", parent)

    for widget in (
        parent.add_node_button,
        parent.renameNodeButton,
        parent.toggleButton,
        parent.refreshButton,
        parent.container_combo,
    ):
        widget.setEnabled(False)
    parent.themeToggleButton.setEnabled(True)

    snapshot = e2e_visual.lifecycle_controls_snapshot(parent)

    e2e_visual.assert_lifecycle_controls_busy(snapshot, expected_toggle_text="Starting...")


def test_lifecycle_controls_busy_assertion_rejects_enabled_lifecycle_button(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)

    parent.add_node_button = QPushButton("Add New Node", parent)
    parent.renameNodeButton = QPushButton("Change Node Alias", parent)
    parent.toggleButton = QPushButton("Starting...", parent)
    parent.refreshButton = QPushButton("Refresh Node Info", parent)
    parent.container_combo = QComboBox(parent)
    parent.themeToggleButton = QPushButton("Switch to Light Theme", parent)

    for widget in (
        parent.add_node_button,
        parent.renameNodeButton,
        parent.refreshButton,
        parent.container_combo,
    ):
        widget.setEnabled(False)
    parent.toggleButton.setEnabled(True)

    snapshot = e2e_visual.lifecycle_controls_snapshot(parent)

    with pytest.raises(AssertionError, match="expected lifecycle controls to be disabled"):
        e2e_visual.assert_lifecycle_controls_busy(snapshot, expected_toggle_text="Starting...")
