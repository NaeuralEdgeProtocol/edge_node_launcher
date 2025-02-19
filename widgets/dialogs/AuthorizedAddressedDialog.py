from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QScrollArea, QWidget, QApplication, QMessageBox)
from PyQt5.QtCore import Qt

from widgets.ToastWidget import ToastWidget, NotificationType


class AddressRow(QWidget):
    def __init__(self, parent=None, address="", alias="", on_delete=None):
        super().__init__(parent)
        self.parent_dialog = parent

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 5, 0, 5)

        # Address input container
        address_container = QWidget()
        address_layout = QHBoxLayout(address_container)
        address_layout.setContentsMargins(0, 0, 0, 0)
        address_layout.setSpacing(2)

        self.address_input = QLineEdit(parent=self)
        self.address_input.setText(str(address) if address else "")
        self.address_input.setPlaceholderText("Enter address")
        self.address_input.setMinimumWidth(300)
        self.address_input.setMinimumHeight(35)
        self.address_input.setStyleSheet("QLineEdit { color: white; }")

        self.copy_addr_btn = QPushButton("📋", parent=self)
        self.copy_addr_btn.setFixedSize(30, 50)
        self.copy_addr_btn.clicked.connect(self.copy_address)

        address_layout.addWidget(self.address_input)
        address_layout.addWidget(self.copy_addr_btn)

        # Alias input container
        alias_container = QWidget()
        alias_layout = QHBoxLayout(alias_container)
        alias_layout.setContentsMargins(0, 0, 0, 0)
        alias_layout.setSpacing(2)

        self.alias_input = QLineEdit(parent=self)
        self.alias_input.setText(str(alias) if alias else "")
        self.alias_input.setPlaceholderText("Enter alias")
        self.alias_input.setMinimumWidth(200)
        self.alias_input.setMinimumHeight(50)
        self.alias_input.setStyleSheet("QLineEdit { color: white; }")

        self.copy_alias_btn = QPushButton("📋", parent=self)
        self.copy_alias_btn.setFixedSize(30, 50)
        self.copy_alias_btn.clicked.connect(self.copy_alias)

        alias_layout.addWidget(self.alias_input)
        alias_layout.addWidget(self.copy_alias_btn)

        # Delete button
        self.delete_btn = QPushButton("🗑", parent=self)
        self.delete_btn.setFixedSize(30, 50)
        self.delete_btn.clicked.connect(lambda: on_delete(self) if on_delete else None)

        self.layout.addWidget(address_container)
        self.layout.addWidget(alias_container)
        self.layout.addWidget(self.delete_btn)

        self.setLayout(self.layout)

    def copy_address(self):
        clipboard = QApplication.clipboard()
        text = self.address_input.text()
        clipboard.setText(text)
        if hasattr(self.parent_dialog, 'toast'):
            self.parent_dialog.toast.show_notification(NotificationType.SUCCESS,
                                                       f"Address copied: {text[:8]}...{text[-8:]}")

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


class AuthorizedAddressesDialog(QDialog):
    def __init__(self, parent=None, on_save_callback=None):
        super().__init__(parent)
        self.toast = ToastWidget(self, bottom_margin=80)  # Position above buttons

        self.on_save_callback = on_save_callback
        self.setWindowTitle("Edit Authorized Addresses")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setStyleSheet(parent._current_stylesheet if parent else "")

        layout = QVBoxLayout()

        # Add note about max length
        note_label = QLabel("Note: Maximum alias length is 15 characters")
        note_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(note_label)

        # Headers
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Address"))
        header_layout.addWidget(QLabel("Alias"))
        header_layout.addSpacing(80)
        layout.addLayout(header_layout)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setAlignment(Qt.AlignTop)
        self.scroll_content.setLayout(self.rows_layout)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        add_btn = QPushButton("Add New Address")
        add_btn.clicked.connect(self.add_row)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_changes)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        bottom_layout.addWidget(add_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(save_btn)
        bottom_layout.addWidget(close_btn)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)
        self.rows = []

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
        row = AddressRow(parent=self, address=address, alias=alias, on_delete=self.delete_row)
        self.rows.append(row)
        self.rows_layout.addWidget(row)

    def delete_row(self, row):
        self.rows.remove(row)
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

