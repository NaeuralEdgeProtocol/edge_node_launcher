from typing import Callable, Optional

from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


CreateNodeCallback = Callable[[str, str, Optional[str], QDialog], None]
ButtonStyler = Callable[[QPushButton, str], None]


class AddNodeDialog(QDialog):
    """Confirmation dialog for creating and launching another local node."""

    def __init__(
        self,
        parent=None,
        ram_check: Optional[dict] = None,
        existing_node_count: int = 0,
        container_name: str = "",
        volume_name: str = "",
        stylesheet: str = "",
        create_node: Optional[CreateNodeCallback] = None,
        button_styler: Optional[ButtonStyler] = None,
    ):
        super().__init__(parent)
        self._container_name = container_name
        self._volume_name = volume_name
        self._create_node = create_node
        self._is_overcommit = not bool((ram_check or {}).get("can_add_node", True))

        self.setWindowTitle("Add New Node")
        self.setObjectName("addNodeDialog")
        self.setAccessibleName("Add New Node")
        self.setMinimumWidth(420)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.info_label = QLabel(self._capacity_copy(ram_check or {}, existing_node_count))
        self.info_label.setObjectName("createNodeCapacityLabel")
        self.info_label.setAccessibleName("Node capacity summary")
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumWidth(360)
        layout.addWidget(self.info_label)

        self.button_row = QWidget()
        self.button_row.setObjectName("createNodeButtonRow")
        self.button_row.setAccessibleName("Create node actions")
        button_layout = QHBoxLayout(self.button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)
        self.create_button = QPushButton("Create Anyway" if self._is_overcommit else "Create Node")
        self.create_button.setObjectName("createNodeConfirmButton")
        self.create_button.setAccessibleName("Create node")
        self.create_button.setToolTip(
            "Create and launch with resource overcommit"
            if self._is_overcommit
            else "Create and launch another local node"
        )
        self.create_button.setProperty("actionRole", "primary")
        self._prepare_button(self.create_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("createNodeCancelButton")
        self.cancel_button.setAccessibleName("Cancel node creation")
        self.cancel_button.setToolTip("Cancel node creation")
        self.cancel_button.setProperty("actionRole", "secondary")
        self._prepare_button(self.cancel_button)

        if button_styler:
            button_styler(self.create_button, "start")
            button_styler(self.cancel_button, "stop")

        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)
        layout.addWidget(self.button_row)

        self.setLayout(layout)
        self.setStyleSheet(stylesheet)

        self.create_button.clicked.connect(self._handle_create_clicked)
        self.cancel_button.clicked.connect(self.reject)

    @staticmethod
    def _prepare_button(button: QPushButton):
        button.setMinimumHeight(44)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    @staticmethod
    def _capacity_copy(ram_check: dict, existing_node_count: int) -> str:
        if "error" in ram_check:
            return "This action will create a new Edge Node. \n\nDo you want to proceed?"

        capacity_copy = (
            "This action will create a new Edge Node.\n\n"
            "System Capacity:\n"
            f"- Total RAM: {ram_check['total_ram_gb']:.1f} GB\n"
            f"- RAM per node: {ram_check['min_required_gb']} GB\n"
            f"- Max nodes supported: {ram_check['max_nodes_supported']}\n"
            f"- Current nodes: {existing_node_count}\n"
        )

        if not ram_check.get("can_add_node", True):
            return (
                capacity_copy
                + "\nResource Warning:\n"
                "- Recommended capacity is already reached\n"
                "- Creating another node may overcommit CPU/RAM\n"
                "- Existing node volumes and data will remain untouched\n\n"
                "Create anyway?"
            )

        return capacity_copy + "\nDo you want to proceed?"

    def _handle_create_clicked(self):
        if not self.create_button.isEnabled():
            return

        self.create_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.create_button.setText("Creating...")

        if self._create_node:
            self._create_node(self._container_name, self._volume_name, None, self)
