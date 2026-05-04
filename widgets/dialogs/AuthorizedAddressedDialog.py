from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QScrollArea, QWidget, QApplication,
                             QMessageBox, QSizePolicy)
from PyQt5.QtCore import Qt

from widgets.ToastWidget import ToastWidget, NotificationType
from utils.const import DARK_STYLESHEET


_ROW_BUTTON_HEIGHT = 44
_FOOTER_BUTTON_HEIGHT = 52
_BUTTON_VERTICAL_PADDING = 7
_BUTTON_BORDER = 1
_ROW_BUTTON_CONTENT_HEIGHT = _ROW_BUTTON_HEIGHT - (_BUTTON_VERTICAL_PADDING * 2) - (_BUTTON_BORDER * 2)
_FOOTER_BUTTON_CONTENT_HEIGHT = _FOOTER_BUTTON_HEIGHT - (_BUTTON_VERTICAL_PADDING * 2) - (_BUTTON_BORDER * 2)

_AUTHORIZED_ADDRESSES_STYLE = f"""
QWidget#authorizedAddressRow QPushButton {{
    margin: 0px;
    padding: {_BUTTON_VERTICAL_PADDING}px 10px;
    border-width: {_BUTTON_BORDER}px;
    border-radius: 8px;
    min-height: {_ROW_BUTTON_CONTENT_HEIGHT}px;
    max-height: {_ROW_BUTTON_CONTENT_HEIGHT}px;
    font-size: 13px;
}}
QWidget#authorizedAddressButtonRow QPushButton {{
    margin: 0px;
    padding: {_BUTTON_VERTICAL_PADDING}px 14px;
    border-width: {_BUTTON_BORDER}px;
    border-radius: 8px;
    min-height: {_FOOTER_BUTTON_CONTENT_HEIGHT}px;
    max-height: {_FOOTER_BUTTON_CONTENT_HEIGHT}px;
}}
QWidget#authorizedAddressRow QPushButton[actionRole="destructive"] {{
    background-color: #DC2626;
    color: #FFFFFF;
    border: 1px solid #B91C1C;
}}
QWidget#authorizedAddressRow QPushButton[actionRole="destructive"]:hover {{
    background-color: #B91C1C;
}}
QScrollArea#authorizedAddressScrollArea {{
    border-radius: 8px;
}}
"""


class AddressRow(QWidget):
    def __init__(self, parent=None, address="", alias="", on_delete=None, input_text_color="black"):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setObjectName("authorizedAddressRow")
        self.setAccessibleName("Authorized address row")

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 4, 0, 4)
        self.layout.setSpacing(10)

        # Address input container
        self.address_container = QWidget()
        self.address_container.setObjectName("authorizedAddressInputContainer")
        self.address_container.setAccessibleName("Authorized address input group")
        self.address_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        address_layout = QHBoxLayout(self.address_container)
        address_layout.setContentsMargins(0, 0, 0, 0)
        address_layout.setSpacing(6)

        self.address_input = QLineEdit(parent=self)
        self.address_input.setObjectName("authorizedAddressInput")
        self.address_input.setProperty("role", "dialogTextInput")
        self.address_input.setAccessibleName("Authorized address")
        self.address_input.setText(str(address) if address else "")
        self.address_input.setCursorPosition(0)
        self.address_input.setPlaceholderText("Enter address")
        self.address_input.setMinimumWidth(180)
        self.address_input.setMinimumHeight(38)
        self.address_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.address_input.setStyleSheet(
            f"QLineEdit#authorizedAddressInput {{ color: {input_text_color}; }}"
        )

        self.copy_addr_btn = QPushButton("Copy", parent=self)
        self.copy_addr_btn.setObjectName("authorizedAddressCopyAddressButton")
        self.copy_addr_btn.setAccessibleName("Copy authorized address")
        self.copy_addr_btn.setToolTip("Copy authorized address")
        self.copy_addr_btn.setProperty("actionRole", "utility")
        self.copy_addr_btn.setFixedSize(84, _ROW_BUTTON_HEIGHT)
        self.copy_addr_btn.clicked.connect(self.copy_address)

        address_layout.addWidget(self.address_input)
        address_layout.addWidget(self.copy_addr_btn)

        # Alias input container
        self.alias_container = QWidget()
        self.alias_container.setObjectName("authorizedAliasInputContainer")
        self.alias_container.setAccessibleName("Authorized alias input group")
        self.alias_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        alias_layout = QHBoxLayout(self.alias_container)
        alias_layout.setContentsMargins(0, 0, 0, 0)
        alias_layout.setSpacing(6)

        self.alias_input = QLineEdit(parent=self)
        self.alias_input.setObjectName("authorizedAliasInput")
        self.alias_input.setProperty("role", "dialogTextInput")
        self.alias_input.setAccessibleName("Authorized address alias")
        self.alias_input.setText(str(alias) if alias else "")
        self.alias_input.setPlaceholderText("Enter alias")
        self.alias_input.setMinimumWidth(120)
        self.alias_input.setMinimumHeight(38)
        self.alias_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.alias_input.setStyleSheet(
            f"QLineEdit#authorizedAliasInput {{ color: {input_text_color}; }}"
        )

        self.copy_alias_btn = QPushButton("Copy", parent=self)
        self.copy_alias_btn.setObjectName("authorizedAddressCopyAliasButton")
        self.copy_alias_btn.setAccessibleName("Copy authorized address alias")
        self.copy_alias_btn.setToolTip("Copy authorized address alias")
        self.copy_alias_btn.setProperty("actionRole", "utility")
        self.copy_alias_btn.setFixedSize(84, _ROW_BUTTON_HEIGHT)
        self.copy_alias_btn.clicked.connect(self.copy_alias)

        alias_layout.addWidget(self.alias_input)
        alias_layout.addWidget(self.copy_alias_btn)

        # Delete button
        self.delete_btn = QPushButton("Remove", parent=self)
        self.delete_btn.setObjectName("authorizedAddressDeleteButton")
        self.delete_btn.setAccessibleName("Remove authorized address")
        self.delete_btn.setToolTip("Remove authorized address")
        self.delete_btn.setProperty("actionRole", "destructive")
        self.delete_btn.setFixedSize(100, _ROW_BUTTON_HEIGHT)
        self.delete_btn.clicked.connect(lambda: on_delete(self) if on_delete else None)

        self.layout.addWidget(self.address_container, 5)
        self.layout.addWidget(self.alias_container, 3)
        self.layout.addWidget(self.delete_btn)

        self.setLayout(self.layout)

    def copy_address(self):
        clipboard = QApplication.clipboard()
        text = self.address_input.text()
        clipboard.setText(text)
        if hasattr(self.parent_dialog, 'toast'):
            self.parent_dialog.toast.show_notification(
                NotificationType.SUCCESS,
                f"Address copied: {self._clipboard_preview(text)}",
            )

    def copy_alias(self):
        clipboard = QApplication.clipboard()
        text = self.alias_input.text()
        clipboard.setText(text)
        if hasattr(self.parent_dialog, 'toast'):
            self.parent_dialog.toast.show_notification(NotificationType.SUCCESS, f"Alias copied: {text}")

    def get_data(self):
        return {
            'address': self.address_input.text(),
            'alias': self.alias_input.text()
        }

    def is_valid(self):
        return bool(self.address_input.text().strip())

    @staticmethod
    def _clipboard_preview(text):
        if len(text) <= 18:
            return text
        return f"{text[:8]}...{text[-8:]}"


class AuthorizedAddressesDialog(QDialog):
    def __init__(self, parent=None, on_save_callback=None):
        super().__init__(parent)
        self.toast = ToastWidget(self, bottom_margin=80)  # Position above buttons

        self.on_save_callback = on_save_callback
        self.setWindowTitle("Edit Authorized Addresses")
        self.setObjectName("authorizedAddressesDialog")
        self.setAccessibleName("Edit Authorized Addresses")
        self.setMinimumWidth(820)
        self.setMinimumHeight(600)
        self.setStyleSheet((parent._current_stylesheet if parent else "") + _AUTHORIZED_ADDRESSES_STYLE)
        self._input_text_color = (
            "white"
            if parent and getattr(parent, "_current_stylesheet", None) == DARK_STYLESHEET
            else "black"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Add note about max length
        note_label = QLabel("Note: Maximum alias length is 15 characters")
        note_label.setObjectName("authorizedAddressNoteLabel")
        note_label.setAccessibleName("Authorized address note")
        note_label.setStyleSheet("color: gray; font-style: italic;")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        # Headers
        self.header_row = QWidget()
        self.header_row.setObjectName("authorizedAddressHeaderRow")
        self.header_row.setAccessibleName("Authorized address headers")
        header_layout = QHBoxLayout(self.header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        address_header = QLabel("Address")
        address_header.setObjectName("authorizedAddressHeaderLabel")
        address_header.setAccessibleName("Authorized address header")
        alias_header = QLabel("Alias")
        alias_header.setObjectName("authorizedAliasHeaderLabel")
        alias_header.setAccessibleName("Authorized alias header")
        actions_header = QLabel("Actions")
        actions_header.setObjectName("authorizedAddressActionsHeaderLabel")
        actions_header.setAccessibleName("Authorized address actions header")
        actions_header.setAlignment(Qt.AlignCenter)
        actions_header.setFixedWidth(100)
        header_layout.addWidget(address_header, 5)
        header_layout.addWidget(alias_header, 3)
        header_layout.addWidget(actions_header)
        layout.addWidget(self.header_row)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setObjectName("authorizedAddressScrollArea")
        self.scroll.setAccessibleName("Authorized address rows")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("authorizedAddressScrollContent")
        self.scroll_content.setAccessibleName("Authorized address row content")
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 4, 0, 4)
        self.rows_layout.setSpacing(8)
        self.rows_layout.setAlignment(Qt.AlignTop)
        self.scroll_content.setLayout(self.rows_layout)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)

        # Bottom buttons
        self.button_row = QWidget()
        self.button_row.setObjectName("authorizedAddressButtonRow")
        self.button_row.setAccessibleName("Authorized address actions")
        bottom_layout = QHBoxLayout(self.button_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)
        self.add_btn = QPushButton("Add New Address")
        self.add_btn.setObjectName("authorizedAddressAddButton")
        self.add_btn.setAccessibleName("Add authorized address")
        self.add_btn.setToolTip("Add another authorized address")
        self.add_btn.setProperty("actionRole", "secondary")
        self._prepare_footer_button(self.add_btn, minimum_width=170)
        self.add_btn.clicked.connect(self.add_row)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("authorizedAddressSaveButton")
        self.save_btn.setAccessibleName("Save authorized addresses")
        self.save_btn.setToolTip("Save authorized address changes")
        self.save_btn.setProperty("actionRole", "primary")
        self._prepare_footer_button(self.save_btn)
        self.save_btn.clicked.connect(self.save_changes)
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("authorizedAddressCloseButton")
        self.close_btn.setAccessibleName("Close authorized addresses")
        self.close_btn.setToolTip("Close without saving")
        self.close_btn.setProperty("actionRole", "secondary")
        self._prepare_footer_button(self.close_btn)
        self.close_btn.clicked.connect(self.reject)

        bottom_layout.addWidget(self.add_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.close_btn)
        layout.addWidget(self.button_row)

        self.setLayout(layout)
        self.rows = []

    @staticmethod
    def _prepare_footer_button(button, minimum_width=120):
        button.setFixedHeight(_FOOTER_BUTTON_HEIGHT)
        button.setMinimumWidth(minimum_width)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def validate_data(self):
        valid = True
        empty_rows = []

        for row in self.rows:
            address = row.address_input.text().strip()
            if not address:
                empty_rows.append(row)
                valid = False

        if not valid:
            QMessageBox.warning(self, "Validation Error",
                                "Node address cannot be empty. Please fill in all addresses or remove empty rows.")
        return valid

    def save_changes(self):
        if not self.validate_data():
            self.toast.show_notification(NotificationType.ERROR, "Please fill in all addresses")
            return

        if self.on_save_callback:
            data = self.get_data()
            processed_data = "\n".join(f"{item['address']} {item['alias']}" for item in data)
            try:
                self.on_save_callback(processed_data)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save changes: {str(e)}")
        else:
            self.accept()


    def edit_addrs(self):
        def save_callback(data):
            with open(self.addrs_file, 'w') as file:
                for item in data:
                    file.write(f"{item['address']},{item['alias']}\n")

        dialog = AuthorizedAddressesDialog(self, on_save_callback=save_callback)

        # Load existing data
        current_data = []
        try:
            with open(self.addrs_file, 'r') as file:
                lines = file.readlines()
                for line in lines:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        current_data.append({
                            'address': parts[0],
                            'alias': parts[1]
                        })
        except FileNotFoundError:
            pass

        dialog.load_data(current_data)
        dialog.exec_()

    def add_row(self, address="", alias=""):
        row = AddressRow(
            parent=self,
            address=address,
            alias=alias,
            on_delete=self.delete_row,
            input_text_color=self._input_text_color,
        )
        self.rows.append(row)
        self.rows_layout.addWidget(row)

    def delete_row(self, row):
        if row not in self.rows:
            return
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()

    def load_data(self, data):
        # Clear existing rows
        for row in self.rows:
            row.deleteLater()
        self.rows.clear()

        # Add rows for existing data
        for addr_data in data:
            self.add_row(addr_data['address'], addr_data['alias'])

        if not self.rows:
            self.add_row()  # Add empty row if no data

    def get_data(self):
        return [row.get_data() for row in self.rows if row.is_valid()]

    def save_and_close(self):
        self.accept()
