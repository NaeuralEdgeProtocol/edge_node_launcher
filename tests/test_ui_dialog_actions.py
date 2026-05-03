from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QPushButton

import widgets.dialogs.DockerCheckDialog as docker_check_module
from ui.ProgressDialog import ImagePullProgressDialog
from widgets.dialogs.AuthorizedAddressedDialog import AddressRow, AuthorizedAddressesDialog


def test_docker_check_dialog_buttons_are_clickable(qtbot, monkeypatch):
    opened_urls = []
    monkeypatch.setattr(docker_check_module.webbrowser, "open", opened_urls.append)

    download_dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(download_dialog)

    assert download_dialog.download_button.objectName() == "dockerCheckDownloadButton"
    qtbot.mouseClick(download_dialog.download_button, Qt.LeftButton)
    assert opened_urls == ["https://www.docker.com/products/docker-desktop"]

    retry_dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(retry_dialog)

    assert retry_dialog.retry_button.objectName() == "dockerCheckRetryButton"
    with qtbot.waitSignal(retry_dialog.accepted):
        qtbot.mouseClick(retry_dialog.retry_button, Qt.LeftButton)

    quit_dialog = docker_check_module.DockerCheckDialog()
    qtbot.addWidget(quit_dialog)

    assert quit_dialog.quit_button.objectName() == "dockerCheckQuitButton"
    with qtbot.waitSignal(quit_dialog.rejected):
        qtbot.mouseClick(quit_dialog.quit_button, Qt.LeftButton)


def test_image_pull_cancel_button_rejects_dialog(qtbot):
    dialog = ImagePullProgressDialog()
    qtbot.addWidget(dialog)

    assert dialog.cancel_button.objectName() == "imagePullCancelButton"

    with qtbot.waitSignal(dialog.rejected):
        qtbot.mouseClick(dialog.cancel_button, Qt.LeftButton)


def test_authorized_address_row_buttons_copy_and_delete(qtbot):
    deleted_rows = []
    row = AddressRow(address="0xabc123", alias="alpha", on_delete=deleted_rows.append)
    qtbot.addWidget(row)

    assert row.copy_addr_btn.objectName() == "authorizedAddressCopyAddressButton"
    assert row.copy_alias_btn.objectName() == "authorizedAddressCopyAliasButton"
    assert row.delete_btn.objectName() == "authorizedAddressDeleteButton"

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

    assert add_button is not None
    assert save_button is not None
    assert close_button is not None

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
