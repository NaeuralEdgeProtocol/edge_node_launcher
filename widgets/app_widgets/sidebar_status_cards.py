from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

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
from widgets.loading_indicator import LoadingIndicator


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
        self.edgeImageBadge = QLabel("")
        self.edgeImageBadge.setObjectName("edgeImageBadge")
        self.edgeImageBadge.setProperty("role", "edgeImageBadge")
        self.edgeImageBadge.setAccessibleName("Edge Node Docker image")
        self.edgeImageBadge.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        self.edgeImageBadge.setAlignment(Qt.AlignCenter)
        self.edgeImageBadge.setMinimumHeight(22)
        self.edgeImageBadge.setWordWrap(False)
        self.edgeImageBadge.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.edgeImageBadge.hide()

        self.node_lifecycle_state = ElidedLabel("Status: Stopped")
        self.node_lifecycle_state.setObjectName("nodeLifecycleStatus")
        self.node_lifecycle_state.setAccessibleName("Node lifecycle status")
        self.node_lifecycle_state.setProperty("statusField", "metadata")
        self.node_lifecycle_state.setProperty("role", "nodeLifecycleState")
        self.node_lifecycle_state.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        _configure_sidebar_label(self.node_lifecycle_state)

        self.node_runtime_policy = ElidedLabel("Runtime: GPU eligible")
        self.node_runtime_policy.setObjectName("nodeRuntimePolicy")
        self.node_runtime_policy.setAccessibleName("Node runtime policy")
        self.node_runtime_policy.setProperty("statusField", "metadata")
        self.node_runtime_policy.setProperty("role", "nodeRuntimePolicy")
        self.node_runtime_policy.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        _configure_sidebar_label(self.node_runtime_policy)

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
        button.setFixedSize(24, 24)
        button.hide()
        return button

    def _init_layout(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        layout.addWidget(self.node_status_title)
        layout.addWidget(self.edgeImageBadge)
        layout.addWidget(self.node_lifecycle_state)
        layout.addWidget(self.node_runtime_policy)

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
        layout.addLayout(self._create_metadata_grid())
        self.setLayout(layout)

    def set_edge_image_badge(self, text: str, tooltip: str = "", visible: bool = True) -> None:
        self.edgeImageBadge.setText(text)
        self.edgeImageBadge.setToolTip(tooltip)
        self.edgeImageBadge.setVisible(bool(visible and text))

    def _create_address_row(self, label: QLabel, button: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(label, 1)
        row.addWidget(button)
        return row

    def _create_metadata_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setObjectName("nodeMetadataGrid")
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(1)
        grid.addWidget(self.node_uptime, 0, 0)
        grid.addWidget(self.node_epoch, 0, 1)
        grid.addWidget(self.node_epoch_avail, 1, 0)
        grid.addWidget(self.node_version, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return grid


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
