from typing import Callable, Optional

from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


AliasValidator = Callable[[str], Optional[str]]
AliasSubmitter = Callable[[str, Callable[[], None]], bool]
ErrorReporter = Callable[[str], None]


class RenameNodeDialog(QDialog):
    """Dialog for changing the display alias of the selected node."""

    def __init__(
        self,
        parent=None,
        current_alias: str = "",
        max_length: int = 15,
        stylesheet: str = "",
        input_text_color: str = "black",
        validate_alias: Optional[AliasValidator] = None,
        submit_alias: Optional[AliasSubmitter] = None,
        show_error: Optional[ErrorReporter] = None,
    ):
        super().__init__(parent)
        self._validate_alias = validate_alias
        self._submit_alias = submit_alias
        self._show_error = show_error

        self.setWindowTitle("Rename Node")
        self.setObjectName("renameNodeDialog")
        self.setAccessibleName("Rename Node")
        self.setMinimumWidth(450)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        explanation = QLabel("Name this node for display in the launcher.")
        explanation.setObjectName("renameNodeExplanationLabel")
        explanation.setAccessibleName("Rename node explanation")
        layout.addWidget(explanation)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("renameNodeNameInput")
        self.name_input.setProperty("role", "dialogTextInput")
        self.name_input.setAccessibleName("Node display name")
        self.name_input.setText(current_alias)
        self.name_input.setMaxLength(max_length)
        self.name_input.setPlaceholderText("Node display name")
        self.name_input.setMinimumHeight(38)
        self.name_input.setStyleSheet(
            f"QLineEdit#renameNodeNameInput {{ color: {input_text_color}; }}"
        )
        layout.addWidget(self.name_input)

        restrictions_label = QLabel("Name restrictions:")
        restrictions_label.setObjectName("renameNodeRestrictionsLabel")
        restrictions_label.setAccessibleName("Name restrictions heading")
        restrictions_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(restrictions_label)

        restrictions_text = QLabel(
            "- Maximum 15 characters\n"
            "- Letters, numbers, hyphens, and underscores only\n"
            "- Cannot be empty"
        )
        restrictions_text.setObjectName("renameNodeRestrictionsText")
        restrictions_text.setAccessibleName("Name restrictions")
        restrictions_text.setStyleSheet("margin-left: 10px; margin-bottom: 10px;")
        restrictions_text.setWordWrap(True)
        layout.addWidget(restrictions_text)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("renameNodeSaveButton")
        self.save_button.setAccessibleName("Save node name")
        self.save_button.setProperty("type", "confirm")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("renameNodeCancelButton")
        self.cancel_button.setAccessibleName("Cancel node rename")
        self.cancel_button.setProperty("type", "cancel")

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setStyleSheet(stylesheet)

        self.save_button.clicked.connect(self._handle_save_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def reset_submit_controls(self):
        self.save_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.save_button.setText("Save")

    def _handle_save_clicked(self):
        if not self.save_button.isEnabled():
            return

        new_alias = self.name_input.text().strip()
        validation_error = self._validate_alias(new_alias) if self._validate_alias else None
        if validation_error:
            if self._show_error:
                self._show_error(validation_error)
            return

        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.save_button.setText("Saving...")

        submitted = self._submit_alias(new_alias, self.reset_submit_controls) if self._submit_alias else False
        if not submitted:
            self.reset_submit_controls()
