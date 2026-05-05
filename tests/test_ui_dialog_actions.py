from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTextEdit

import widgets.dialogs.DockerCheckDialog as docker_check_module
from ui.ProgressDialog import ImagePullProgressDialog
from utils import docker as docker_module
from utils.const import DARK_STYLESHEET, INSUFFICIENT_RAM_MESSAGE, LIGHT_STYLESHEET
from widgets.dialogs.AddNodeDialog import AddNodeDialog
from widgets.dialogs.AuthorizedAddressedDialog import AddressRow, AuthorizedAddressesDialog
from widgets.dialogs.RenameNodeDialog import RenameNodeDialog


def test_docker_check_dialog_buttons_are_clickable(qtbot, monkeypatch):
    opened_urls = []
    monkeypatch.setattr(docker_check_module.webbrowser, "open", opened_urls.append)

    download_dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(download_dialog)

    assert download_dialog.objectName() == "dockerCheckDialog"
    assert download_dialog.accessibleName() == "Docker Check"
    assert download_dialog.message.objectName() == "dockerCheckMessageLabel"
    assert download_dialog.message.accessibleName() == "Docker status message"
    assert download_dialog.message.wordWrap()
    assert download_dialog.button_row.objectName() == "dockerCheckButtonRow"
    assert download_dialog.button_row.accessibleName() == "Docker check actions"
    assert download_dialog.download_button.objectName() == "dockerCheckDownloadButton"
    assert download_dialog.download_button.accessibleName() == "Download Docker"
    assert download_dialog.download_button.toolTip() == "Open Docker Desktop download page"
    assert download_dialog.download_button.property("actionRole") == "primary"
    assert download_dialog.download_button.minimumHeight() >= 44
    qtbot.mouseClick(download_dialog.download_button, Qt.LeftButton)
    assert opened_urls == ["https://www.docker.com/products/docker-desktop"]

    retry_dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(retry_dialog)

    assert retry_dialog.retry_button.objectName() == "dockerCheckRetryButton"
    assert retry_dialog.retry_button.accessibleName() == "Try Docker check again"
    assert retry_dialog.retry_button.toolTip() == "Check Docker again"
    assert retry_dialog.retry_button.property("actionRole") == "secondary"
    with qtbot.waitSignal(retry_dialog.accepted):
        qtbot.mouseClick(retry_dialog.retry_button, Qt.LeftButton)

    quit_dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(quit_dialog)

    assert quit_dialog.quit_button.objectName() == "dockerCheckQuitButton"
    assert quit_dialog.quit_button.accessibleName() == "Quit launcher"
    assert quit_dialog.quit_button.toolTip() == "Close the launcher"
    assert quit_dialog.quit_button.property("actionRole") == "destructive"
    with qtbot.waitSignal(quit_dialog.rejected):
        qtbot.mouseClick(quit_dialog.quit_button, Qt.LeftButton)


def test_docker_check_quit_button_has_readable_yellow_contrast(qtbot):
    dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(dialog)

    stylesheet = dialog.styleSheet()

    assert "#1F2937" in stylesheet
    assert "#C4AC26" not in stylesheet
    assert 'border-radius: 8px' in stylesheet
    assert 'border-radius: 15px' not in stylesheet


def test_docker_check_dialog_centers_on_visible_parent(qtbot):
    parent = QDialog()
    parent.setGeometry(100, 120, 700, 500)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitUntil(parent.isVisible)

    dialog = docker_check_module.DockerCheckDialog(parent)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    parent_center = parent.frameGeometry().center()
    dialog_center = dialog.frameGeometry().center()

    assert abs(dialog_center.x() - parent_center.x()) <= 6
    assert abs(dialog_center.y() - parent_center.y()) <= 6


def test_docker_check_dialog_centers_on_hidden_parent_screen_geometry(qtbot, monkeypatch):
    parent = QDialog()
    qtbot.addWidget(parent)
    screen_geometry = QRect(40, 60, 900, 700)
    used_widgets = []

    def fake_available_screen_geometry(widget):
        used_widgets.append(widget)
        return QRect(screen_geometry)

    monkeypatch.setattr(
        docker_check_module,
        "available_screen_geometry",
        fake_available_screen_geometry,
    )

    dialog = docker_check_module.DockerCheckDialog(parent)
    qtbot.addWidget(dialog)
    dialog._center_on_parent_or_screen()

    dialog_center = dialog.frameGeometry().center()

    assert used_widgets
    assert used_widgets[-1] is parent
    assert abs(dialog_center.x() - screen_geometry.center().x()) <= 6
    assert abs(dialog_center.y() - screen_geometry.center().y()) <= 6


def test_progress_bar_window_centers_on_screen_geometry(qtbot, monkeypatch):
    screen_geometry = QRect(120, 160, 1000, 760)
    used_widgets = []

    class Sender:
        _current_stylesheet = ""

    def fake_screen_geometry(widget):
        used_widgets.append(widget)
        return QRect(screen_geometry)

    monkeypatch.setattr(docker_module, "screen_geometry", fake_screen_geometry)

    window = docker_module.ProgressBarWindow("Pulling image", QIcon(), Sender())
    qtbot.addWidget(window)

    window_center = window.frameGeometry().center()

    assert used_widgets == [window]
    assert abs(window_center.x() - screen_geometry.center().x()) <= 6
    assert abs(window_center.y() - screen_geometry.center().y()) <= 6


def test_progress_bar_window_exposes_stable_visual_contract(qtbot):
    class Sender:
        _current_stylesheet = ""

        def __init__(self):
            self.logs = []

        def add_log(self, message):
            self.logs.append(message)

    window = docker_module.ProgressBarWindow(
        "Pulling Docker image with a long command that should wrap cleanly instead of forcing a wider dialog",
        QIcon(),
        Sender(),
    )
    qtbot.addWidget(window)

    assert window.objectName() == "legacyDockerPullProgressDialog"
    assert window.accessibleName() == "Docker pull progress"
    assert window.minimumWidth() >= 560
    assert window.minimumHeight() >= 360
    assert window.label.objectName() == "legacyDockerPullProgressMessage"
    assert window.label.accessibleName() == "Docker pull progress message"
    assert window.label.wordWrap()
    assert window.output_edit.objectName() == "legacyDockerPullOutput"
    assert window.output_edit.accessibleName() == "Docker pull output"
    assert window.output_edit.isReadOnly()
    assert window.output_edit.lineWrapMode() == QTextEdit.WidgetWidth
    assert window.output_edit.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert window.output_edit.sizePolicy().verticalPolicy() == QSizePolicy.Expanding
    assert window.progress_bar.objectName() == "legacyDockerPullProgressBar"
    assert window.progress_bar.accessibleName() == "Docker pull progress"
    assert window.progress_bar.minimum() == 0
    assert window.progress_bar.maximum() == 100
    assert window.progress_bar.minimumHeight() >= 24

    window.update_progress("Layer output line", 160)

    assert "Layer output line" in window.output_edit.toPlainText()
    assert window.progress_bar.value() == 100


def test_image_pull_cancel_button_rejects_dialog(qtbot):
    dialog = ImagePullProgressDialog()
    qtbot.addWidget(dialog)

    assert dialog.cancel_button.objectName() == "imagePullCancelButton"

    with qtbot.waitSignal(dialog.rejected):
        qtbot.mouseClick(dialog.cancel_button, Qt.LeftButton)


def test_rename_node_dialog_preserves_submit_guard(qtbot):
    submitted = []
    errors = []
    dialog = RenameNodeDialog(
        current_alias="alpha",
        validate_alias=lambda value: None,
        submit_alias=lambda value, on_error: submitted.append(value) or True,
        show_error=errors.append,
    )
    qtbot.addWidget(dialog)

    name_input = dialog.findChild(QLineEdit, "renameNodeNameInput")
    explanation = dialog.findChild(QLabel, "renameNodeExplanationLabel")
    restrictions_label = dialog.findChild(QLabel, "renameNodeRestrictionsLabel")
    restrictions_text = dialog.findChild(QLabel, "renameNodeRestrictionsText")
    save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
    cancel_button = dialog.findChild(QPushButton, "renameNodeCancelButton")

    assert dialog.objectName() == "renameNodeDialog"
    assert dialog.accessibleName() == "Rename Node"
    assert dialog.windowTitle() == "Rename Node"
    assert name_input.text() == "alpha"
    assert name_input.accessibleName() == "Node display name"
    assert name_input.property("role") == "dialogTextInput"
    assert name_input.placeholderText() == "Node display name"
    assert name_input.maxLength() == 15
    assert name_input.minimumHeight() == 38
    assert "color: black" in name_input.styleSheet()
    assert explanation.accessibleName() == "Rename node explanation"
    assert restrictions_label.accessibleName() == "Name restrictions heading"
    assert restrictions_text.accessibleName() == "Name restrictions"
    assert dialog.button_row.objectName() == "renameNodeButtonRow"
    assert dialog.button_row.accessibleName() == "Rename node actions"
    assert save_button.accessibleName() == "Save node name"
    assert save_button.toolTip() == "Save node display name"
    assert save_button.property("actionRole") == "primary"
    assert save_button.minimumHeight() == 52
    assert save_button.maximumHeight() == 52
    assert save_button.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert "QPushButton#renameNodeSaveButton" in dialog.styleSheet()
    assert cancel_button.accessibleName() == "Cancel node rename"
    assert cancel_button.toolTip() == "Cancel node rename"
    assert cancel_button.property("actionRole") == "secondary"
    assert cancel_button.minimumHeight() == 52
    assert cancel_button.maximumHeight() == 52

    name_input.setText("beta")
    qtbot.mouseClick(save_button, Qt.LeftButton)

    assert submitted == ["beta"]
    assert errors == []
    assert not save_button.isEnabled()
    assert not cancel_button.isEnabled()
    assert save_button.text() == "Saving..."


def test_rename_node_dialog_action_buttons_render_evenly_with_themes(qtbot):
    for stylesheet in (DARK_STYLESHEET, LIGHT_STYLESHEET):
        dialog = RenameNodeDialog(current_alias="alpha", stylesheet=stylesheet)
        qtbot.addWidget(dialog)

        dialog.show()
        qtbot.waitUntil(dialog.isVisible)

        save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
        cancel_button = dialog.findChild(QPushButton, "renameNodeCancelButton")

        assert save_button.height() == cancel_button.height() == 52
        assert save_button.y() == cancel_button.y()
        dialog.close()


def test_rename_node_dialog_validation_keeps_controls_enabled(qtbot):
    submitted = []
    errors = []
    dialog = RenameNodeDialog(
        current_alias="alpha",
        validate_alias=lambda value: "Invalid alias",
        submit_alias=lambda value, on_error: submitted.append(value) or True,
        show_error=errors.append,
    )
    qtbot.addWidget(dialog)

    save_button = dialog.findChild(QPushButton, "renameNodeSaveButton")
    cancel_button = dialog.findChild(QPushButton, "renameNodeCancelButton")

    qtbot.mouseClick(save_button, Qt.LeftButton)

    assert submitted == []
    assert errors == ["Invalid alias"]
    assert save_button.isEnabled()
    assert cancel_button.isEnabled()
    assert save_button.text() == "Save"


def test_add_node_dialog_capacity_copy_and_create_guard(qtbot):
    created = []
    styled = []
    dialog = AddNodeDialog(
        ram_check={
            "can_add_node": True,
            "total_ram_gb": 32.0,
            "max_nodes_supported": 4,
            "current_node_count": 1,
            "min_required_gb": 16,
        },
        existing_node_count=1,
        container_name="r1node2",
        volume_name="r1vol2",
        create_node=lambda container, volume, display, owner: created.append(
            (container, volume, display, owner)
        ),
        button_styler=lambda button, style: styled.append((button.objectName(), style)),
    )
    qtbot.addWidget(dialog)

    label_copy = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    create_button = dialog.findChild(QPushButton, "createNodeConfirmButton")
    cancel_button = dialog.findChild(QPushButton, "createNodeCancelButton")

    assert dialog.objectName() == "addNodeDialog"
    assert dialog.accessibleName() == "Add New Node"
    assert dialog.windowTitle() == "Add New Node"
    assert dialog.minimumWidth() == 420
    assert dialog.info_label.objectName() == "createNodeCapacityLabel"
    assert dialog.info_label.accessibleName() == "Node capacity summary"
    assert dialog.info_label.wordWrap()
    assert dialog.info_label.minimumWidth() == 360
    assert dialog.button_row.objectName() == "createNodeButtonRow"
    assert dialog.button_row.accessibleName() == "Create node actions"
    assert "System Capacity:" in label_copy
    assert "- Total RAM: 32.0 GB" in label_copy
    assert "- RAM per node: 16 GB" in label_copy
    assert create_button.accessibleName() == "Create node"
    assert create_button.toolTip() == "Create and launch another local node"
    assert create_button.property("actionRole") == "primary"
    assert create_button.minimumHeight() >= 44
    assert create_button.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert cancel_button.accessibleName() == "Cancel node creation"
    assert cancel_button.toolTip() == "Cancel node creation"
    assert cancel_button.property("actionRole") == "secondary"
    assert cancel_button.minimumHeight() >= 44
    assert styled == [
        ("createNodeConfirmButton", "start"),
        ("createNodeCancelButton", "stop"),
    ]

    qtbot.mouseClick(create_button, Qt.LeftButton)
    qtbot.mouseClick(create_button, Qt.LeftButton)

    assert created == [("r1node2", "r1vol2", None, dialog)]
    assert not create_button.isEnabled()
    assert not cancel_button.isEnabled()
    assert create_button.text() == "Creating..."


def test_add_node_dialog_overcommit_copy_is_explicit_and_createable(qtbot):
    created = []
    dialog = AddNodeDialog(
        ram_check={
            "can_add_node": False,
            "total_ram_gb": 32.0,
            "max_nodes_supported": 2,
            "current_node_count": 2,
            "min_required_gb": 16,
            "available_for_next_node_gb": 0.0,
            "near_boundary_warning": False,
        },
        existing_node_count=2,
        container_name="r1node3",
        volume_name="r1vol3",
        create_node=lambda container, volume, display, owner: created.append(
            (container, volume, display, owner)
        ),
    )
    qtbot.addWidget(dialog)

    label_copy = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    create_button = dialog.findChild(QPushButton, "createNodeConfirmButton")

    assert "Resource Warning:" in label_copy
    assert "- Recommended capacity is already reached" in label_copy
    assert "- Creating another node may overcommit CPU/RAM" in label_copy
    assert "- Existing node volumes and data will remain untouched" in label_copy
    assert "Create anyway?" in label_copy
    assert create_button.text() == "Create Anyway"
    assert create_button.toolTip() == "Create and launch with resource overcommit"

    qtbot.mouseClick(create_button, Qt.LeftButton)

    assert created == [("r1node3", "r1vol3", None, dialog)]


def test_insufficient_ram_copy_uses_ascii_bullets():
    copy = INSUFFICIENT_RAM_MESSAGE.format(
        total_gb=32.0,
        max_nodes=2,
        current_nodes=2,
        min_ram_gb=16,
    )

    assert "- Total RAM: 32.0 GB" in copy
    assert "- Maximum Nodes Supported: 2" in copy
    assert "- Current Nodes: 2" in copy
    assert "•" not in copy
    assert "Ã" not in copy
    assert "â" not in copy


def test_authorized_address_row_buttons_copy_and_delete(qtbot):
    deleted_rows = []
    row = AddressRow(address="0xabc123", alias="alpha", on_delete=deleted_rows.append)
    qtbot.addWidget(row)

    assert row.objectName() == "authorizedAddressRow"
    assert row.accessibleName() == "Authorized address row"
    assert row.address_input.objectName() == "authorizedAddressInput"
    assert row.address_input.accessibleName() == "Authorized address"
    assert row.address_input.property("role") == "dialogTextInput"
    assert row.address_input.minimumHeight() == 38
    assert row.address_input.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert row.address_input.cursorPosition() == 0
    assert "color: black" in row.address_input.styleSheet()
    assert row.address_container.objectName() == "authorizedAddressInputContainer"
    assert row.address_container.accessibleName() == "Authorized address input group"
    assert row.alias_input.objectName() == "authorizedAliasInput"
    assert row.alias_input.accessibleName() == "Authorized address alias"
    assert row.alias_input.property("role") == "dialogTextInput"
    assert row.alias_input.minimumHeight() == 38
    assert row.alias_input.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert "color: black" in row.alias_input.styleSheet()
    assert row.alias_container.objectName() == "authorizedAliasInputContainer"
    assert row.alias_container.accessibleName() == "Authorized alias input group"
    assert row.copy_addr_btn.objectName() == "authorizedAddressCopyAddressButton"
    assert row.copy_addr_btn.text() == "Copy"
    assert row.copy_addr_btn.accessibleName() == "Copy authorized address"
    assert row.copy_addr_btn.toolTip() == "Copy authorized address"
    assert row.copy_addr_btn.property("actionRole") == "utility"
    assert row.copy_addr_btn.width() == 84
    assert row.copy_addr_btn.height() == 44
    assert row.copy_alias_btn.objectName() == "authorizedAddressCopyAliasButton"
    assert row.copy_alias_btn.text() == "Copy"
    assert row.copy_alias_btn.accessibleName() == "Copy authorized address alias"
    assert row.copy_alias_btn.toolTip() == "Copy authorized address alias"
    assert row.copy_alias_btn.property("actionRole") == "utility"
    assert row.copy_alias_btn.width() == 84
    assert row.copy_alias_btn.height() == 44
    assert row.delete_btn.objectName() == "authorizedAddressDeleteButton"
    assert row.delete_btn.text() == "Remove"
    assert row.delete_btn.accessibleName() == "Remove authorized address"
    assert row.delete_btn.toolTip() == "Remove authorized address"
    assert row.delete_btn.property("actionRole") == "destructive"
    assert row.delete_btn.width() == 100
    assert row.delete_btn.height() == 44

    qtbot.mouseClick(row.copy_addr_btn, Qt.LeftButton)
    assert QApplication.clipboard().text() == "0xabc123"

    qtbot.mouseClick(row.copy_alias_btn, Qt.LeftButton)
    assert QApplication.clipboard().text() == "alpha"

    qtbot.mouseClick(row.delete_btn, Qt.LeftButton)
    assert deleted_rows == [row]


def test_authorized_addresses_dialog_add_save_and_close_actions(qtbot):
    saved_payloads = []
    dialog = AuthorizedAddressesDialog(on_save_callback=saved_payloads.append)
    qtbot.addWidget(dialog)

    add_button = dialog.findChild(QPushButton, "authorizedAddressAddButton")
    save_button = dialog.findChild(QPushButton, "authorizedAddressSaveButton")
    close_button = dialog.findChild(QPushButton, "authorizedAddressCloseButton")
    note_label = dialog.findChild(QLabel, "authorizedAddressNoteLabel")
    address_header = dialog.findChild(QLabel, "authorizedAddressHeaderLabel")
    alias_header = dialog.findChild(QLabel, "authorizedAliasHeaderLabel")
    actions_header = dialog.findChild(QLabel, "authorizedAddressActionsHeaderLabel")
    scroll_area = dialog.findChild(QScrollArea, "authorizedAddressScrollArea")

    assert dialog.objectName() == "authorizedAddressesDialog"
    assert dialog.accessibleName() == "Edit Authorized Addresses"
    assert dialog.minimumWidth() == 820
    assert dialog.button_row.objectName() == "authorizedAddressButtonRow"
    assert dialog.button_row.accessibleName() == "Authorized address actions"
    assert dialog.header_row.objectName() == "authorizedAddressHeaderRow"
    assert dialog.header_row.accessibleName() == "Authorized address headers"
    assert add_button is not None
    assert add_button.accessibleName() == "Add authorized address"
    assert add_button.toolTip() == "Add another authorized address"
    assert add_button.property("actionRole") == "secondary"
    assert add_button.minimumWidth() == 170
    assert add_button.minimumHeight() == 52
    assert add_button.maximumHeight() == 52
    assert save_button is not None
    assert save_button.accessibleName() == "Save authorized addresses"
    assert save_button.toolTip() == "Save authorized address changes"
    assert save_button.property("actionRole") == "primary"
    assert save_button.minimumHeight() == 52
    assert save_button.maximumHeight() == 52
    assert close_button is not None
    assert close_button.accessibleName() == "Close authorized addresses"
    assert close_button.toolTip() == "Close without saving"
    assert close_button.property("actionRole") == "secondary"
    assert close_button.minimumHeight() == 52
    assert close_button.maximumHeight() == 52
    assert note_label.accessibleName() == "Authorized address note"
    assert note_label.wordWrap()
    assert address_header.accessibleName() == "Authorized address header"
    assert alias_header.accessibleName() == "Authorized alias header"
    assert actions_header.accessibleName() == "Authorized address actions header"
    assert actions_header.width() == 100
    assert scroll_area.accessibleName() == "Authorized address rows"
    assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert dialog.scroll_content.objectName() == "authorizedAddressScrollContent"
    assert dialog.scroll_content.accessibleName() == "Authorized address row content"
    assert "QWidget#authorizedAddressButtonRow QPushButton" in dialog.styleSheet()

    qtbot.mouseClick(add_button, Qt.LeftButton)
    assert len(dialog.rows) == 1

    dialog.rows[0].address_input.setText("0xdef456")
    dialog.rows[0].alias_input.setText("beta")

    with qtbot.waitSignal(dialog.accepted):
        qtbot.mouseClick(save_button, Qt.LeftButton)

    assert saved_payloads == ["0xdef456 beta"]

    close_dialog = AuthorizedAddressesDialog()
    qtbot.addWidget(close_dialog)
    close_button = close_dialog.findChild(QPushButton, "authorizedAddressCloseButton")

    with qtbot.waitSignal(close_dialog.rejected):
        qtbot.mouseClick(close_button, Qt.LeftButton)


def test_authorized_addresses_dialog_uses_theme_text_color(qtbot):
    parent = QDialog()
    parent._current_stylesheet = DARK_STYLESHEET
    dialog = AuthorizedAddressesDialog(parent)
    qtbot.addWidget(parent)

    dialog.load_data([{"address": "0xabc123", "alias": "alpha"}])

    row = dialog.rows[0]
    assert "color: white" in row.address_input.styleSheet()
    assert "color: white" in row.alias_input.styleSheet()


def test_authorized_addresses_dialog_rows_render_without_horizontal_clipping(qtbot):
    parent = QDialog()
    parent._current_stylesheet = DARK_STYLESHEET
    dialog = AuthorizedAddressesDialog(parent)
    qtbot.addWidget(parent)
    dialog.load_data(
        [
            {
                "address": "0x1234567890abcdef1234567890abcdef12345678",
                "alias": "validator-one",
            }
        ]
    )

    dialog.resize(820, 520)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    row = dialog.rows[0]
    buttons = [row.copy_addr_btn, row.copy_alias_btn, row.delete_btn]
    footer_buttons = [dialog.add_btn, dialog.save_btn, dialog.close_btn]

    assert dialog.scroll_content.width() <= dialog.scroll.viewport().width()
    assert row.width() <= dialog.scroll.viewport().width()
    assert all(button.height() == 44 for button in buttons)
    assert all(button.height() == 52 for button in footer_buttons)
