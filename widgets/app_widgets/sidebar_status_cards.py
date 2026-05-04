from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app_forms.frm_utils import LoadingIndicator
from utils.const import (
    COPY_ADDRESS_TOOLTIP,
    COPY_ETH_ADDRESS_TOOLTIP,
    EMPTY_DASH_TEXT,
    EPOCH_AVAIL_LABEL,
    EPOCH_LABEL,
    MEMORY_LABEL,
    MEMORY_NOT_AVAILABLE,
    NODE_VERSION_LABEL,
    STORAGE_LABEL,
    STORAGE_NOT_AVAILABLE,
    UPTIME_LABEL,
    VCPUS_LABEL,
    VCPUS_NOT_AVAILABLE,
)
from widgets.ElidedLabel import ElidedLabel


def _configure_sidebar_label(label: QLabel) -> QLabel:
    label.setWordWrap(False)
    label.setMinimumWidth(0)
    label.setMinimumHeight(20)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    return label


def _configure_status_field(
    label: QLabel,
    field_role: str,
    accessible_name: str,
    *,
    is_address: bool = False,
) -> QLabel:
    label.setProperty("statusField", field_role)
    label.setAccessibleName(accessible_name)
    label.setFont(QFont("Courier New" if is_address else "Segoe UI", 9))
    return _configure_sidebar_label(label)


def _configure_resource_field(label: QLabel, field_role: str, accessible_name: str) -> QLabel:
    label.setProperty("resourceField", field_role)
    label.setAccessibleName(accessible_name)
    label.setFont(QFont("Segoe UI", 9))
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return _configure_sidebar_label(label)


def _create_card_title(text: str, object_name: str, accessible_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setProperty("role", "sidebarCardTitle")
    label.setAccessibleName(accessible_name)
    label.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
    label.setMinimumHeight(24)
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return label


class NodeStatusPanel(QGroupBox):
    """Sidebar node-details card with stable launcher aliases."""

    def __init__(self, copy_address_handler, copy_eth_handler, parent=None):
        super().__init__(parent)
        self.setObjectName("infoBox")
        self.setProperty("role", "statusPanel")
        self.setContentsMargins(5, 0, 5, 0)

        self.node_status_title = _create_card_title(
            "Node Details",
            "nodeStatusCardTitle",
            "Node details card",
        )
        self.loading_indicator = LoadingIndicator(size=30)
        self.loading_indicator.hide()

        self.addressDisplay = ElidedLabel(
            "",
            elide_mode=Qt.ElideMiddle,
            compact_prefix=("Address: ", "Addr: "),
        )
        self.addressDisplay.setObjectName("nodeAddressDisplay")
        _configure_status_field(
            self.addressDisplay,
            "address",
            "Node address",
            is_address=True,
        )

        self.copyAddrButton = self._create_copy_button(
            "copyAddrButton",
            "Copy node address",
            COPY_ADDRESS_TOOLTIP,
            copy_address_handler,
        )

        self.ethAddressDisplay = ElidedLabel(
            "",
            elide_mode=Qt.ElideMiddle,
            compact_prefix=("ETH Address: ", "ETH: "),
        )
        self.ethAddressDisplay.setObjectName("nodeEthAddressDisplay")
        _configure_status_field(
            self.ethAddressDisplay,
            "address",
            "ETH address",
            is_address=True,
        )

        self.copyEthButton = self._create_copy_button(
            "copyEthButton",
            "Copy ETH address",
            COPY_ETH_ADDRESS_TOOLTIP,
            copy_eth_handler,
        )

        self.nameDisplay = ElidedLabel("")
        self.nameDisplay.setObjectName("nodeNameDisplay")
        _configure_status_field(self.nameDisplay, "metadata", "Node name")

        self.node_uptime = ElidedLabel(f"{UPTIME_LABEL} {EMPTY_DASH_TEXT}")
        self.node_uptime.setObjectName("nodeUptimeDisplay")
        _configure_status_field(self.node_uptime, "metadata", "Node uptime")

        self.node_epoch = ElidedLabel(f"{EPOCH_LABEL} {EMPTY_DASH_TEXT}")
        self.node_epoch.setObjectName("nodeEpochDisplay")
        _configure_status_field(self.node_epoch, "metadata", "Node epoch")

        self.node_epoch_avail = ElidedLabel(
            f"{EPOCH_AVAIL_LABEL} {EMPTY_DASH_TEXT}",
            compact_prefix=(f"{EPOCH_AVAIL_LABEL} ", "Epoch avail: "),
        )
        self.node_epoch_avail.setObjectName("nodeEpochAvailabilityDisplay")
        _configure_status_field(self.node_epoch_avail, "metadata", "Node epoch availability")

        self.node_version = ElidedLabel(f"{NODE_VERSION_LABEL} {EMPTY_DASH_TEXT}")
        self.node_version.setObjectName("nodeVersionDisplay")
        _configure_status_field(self.node_version, "metadata", "Node version")

        self._init_layout()

    def _create_copy_button(
        self,
        object_name: str,
        accessible_name: str,
        tooltip: str,
        handler,
    ) -> QPushButton:
        button = QPushButton()
        button.setObjectName(object_name)
        button.setAccessibleName(accessible_name)
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        button.setFixedSize(28, 28)
        button.hide()
        return button

    def _init_layout(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 6, 5, 6)
        layout.setSpacing(3)
        layout.addWidget(self.node_status_title)

        loading_layout = QHBoxLayout()
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(0)
        loading_layout.addStretch()
        loading_layout.addWidget(self.loading_indicator)
        loading_layout.addStretch()
        layout.addLayout(loading_layout)

        layout.addLayout(self._create_address_row(self.addressDisplay, self.copyAddrButton))
        layout.addLayout(self._create_address_row(self.ethAddressDisplay, self.copyEthButton))
        layout.addWidget(self.nameDisplay)
        layout.addWidget(self.node_uptime)
        layout.addWidget(self.node_epoch)
        layout.addWidget(self.node_epoch_avail)
        layout.addWidget(self.node_version)
        self.setLayout(layout)

    def _create_address_row(self, label: QLabel, button: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(label, 1)
        row.addWidget(button)
        return row


class ResourceStatusPanel(QGroupBox):
    """Sidebar host-resource card with stable launcher aliases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("resourcesBox")
        self.setProperty("role", "resourcePanel")
        self.setContentsMargins(5, 0, 5, 0)

        self.resource_status_title = _create_card_title(
            "Host Resources",
            "resourceStatusCardTitle",
            "Host resources card",
        )
        self.memoryDisplay = ElidedLabel(
            f"{MEMORY_LABEL} {MEMORY_NOT_AVAILABLE}",
            compact_prefix=(f"{MEMORY_LABEL} ", "Mem: "),
        )
        self.memoryDisplay.setObjectName("memoryResourceDisplay")
        _configure_resource_field(self.memoryDisplay, "memory", "Memory usage")

        self.vcpusDisplay = ElidedLabel(
            f"{VCPUS_LABEL} {VCPUS_NOT_AVAILABLE}",
            compact_prefix=(f"{VCPUS_LABEL} ", "CPU: "),
        )
        self.vcpusDisplay.setObjectName("cpuResourceDisplay")
        _configure_resource_field(self.vcpusDisplay, "cpu", "CPU usage")

        self.storageDisplay = ElidedLabel(
            f"{STORAGE_LABEL} {STORAGE_NOT_AVAILABLE}",
            compact_prefix=(f"{STORAGE_LABEL} ", "Disk: "),
        )
        self.storageDisplay.setObjectName("storageResourceDisplay")
        _configure_resource_field(self.storageDisplay, "storage", "Storage usage")

        self._init_layout()

    def _init_layout(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 6, 5, 6)
        layout.setSpacing(3)
        layout.addWidget(self.resource_status_title)
        layout.addWidget(self.memoryDisplay)
        layout.addWidget(self.vcpusDisplay)
        layout.addWidget(self.storageDisplay)
        self.setLayout(layout)
