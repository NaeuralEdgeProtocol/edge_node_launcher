from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame,
    QScrollArea, QWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
import re
import logging
import hashlib


SIZE_PROGRESS_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*([KMG]?B)\s*/\s*(\d+(?:\.\d+)?)\s*([KMG]?B)",
    re.IGNORECASE,
)
SIZE_PROGRESS_NORMALIZER = re.compile(
    r"\d+(?:\.\d+)?\s*[KMG]?B\s*/\s*\d+(?:\.\d+)?\s*[KMG]?B",
    re.IGNORECASE,
)
PERCENT_PROGRESS_NORMALIZER = re.compile(r"\d+%")
SIZE_UNIT_BYTES = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 * 1024,
    "GB": 1024 * 1024 * 1024,
}
DOCKER_PULL_DIALOG_STYLE_COLORS = {
    True: {
        "dialog_bg": "#0F172A",
        "title_text": "#F8FAFC",
        "body_text": "#E2E8F0",
        "muted_text": "#CBD5E1",
        "panel_bg": "#1E293B",
        "scrollbar_track": "#334155",
        "scrollbar_handle": "#475569",
        "progress_bg": "#334155",
        "progress_border": "#475569",
        "progress_chunk": "#3B82F6",
        "overall_progress_bg": "#111827",
        "overall_progress_border": "#475569",
        "layer_accent": "#60A5FA",
    },
    False: {
        "dialog_bg": "#F8FAFC",
        "title_text": "#0F172A",
        "body_text": "#1E293B",
        "muted_text": "#64748B",
        "panel_bg": "#FFFFFF",
        "scrollbar_track": "#E2E8F0",
        "scrollbar_handle": "#CBD5E1",
        "progress_bg": "#E2E8F0",
        "progress_border": "#CBD5E1",
        "progress_chunk": "#2563EB",
        "overall_progress_bg": "#EEF2FF",
        "overall_progress_border": "#CBD5E1",
        "layer_accent": "#1D4ED8",
    },
}


class DockerPullDialog(QDialog):
    """Dialog for Docker image pull progress."""
    
    # Signal emitted when pull is complete
    pull_complete = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, parent=None, is_dark=None):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._is_dark = self._resolve_theme(parent, is_dark)
        self.setWindowTitle("Pulling Docker Image")
        self.setObjectName("dockerPullDialog")
        self.setAccessibleName("Pulling Docker Image")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        # Set up the dialog UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        self.title_label = QLabel("Pulling Docker Image")
        self.title_label.setObjectName("dockerPullTitleLabel")
        self.title_label.setAccessibleName("Docker pull title")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        # Info label
        self.info_label = QLabel("Preparing to pull Docker image...")
        self.info_label.setObjectName("dockerPullInfoLabel")
        self.info_label.setAccessibleName("Docker pull status")
        self.info_label.setWordWrap(True)
        
        # Overall progress
        self.overall_progress = QProgressBar()
        self.overall_progress.setObjectName("dockerPullOverallProgress")
        self.overall_progress.setAccessibleName("Docker pull overall progress")
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setMinimumHeight(25)
        
        # Layer progress section
        self.layer_frame = QFrame()
        self.layer_frame.setObjectName("dockerPullLayerFrame")
        self.layer_frame.setAccessibleName("Docker pull layer progress")
        self.layer_frame.setFrameShape(QFrame.StyledPanel)
        
        # Create a scroll area for layers
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("dockerPullLayerScrollArea")
        self.scroll_area.setAccessibleName("Docker pull layer list")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget for the scroll area
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("dockerPullLayerScrollContent")
        self.scroll_content.setAccessibleName("Docker pull layer list content")
        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(12, 12, 12, 12)
        
        # Layer label
        self.layer_header_label = QLabel("Layer Progress:")
        self.layer_header_label.setObjectName("dockerPullLayerHeaderLabel")
        self.layer_header_label.setAccessibleName("Layer progress heading")
        scroll_layout.addWidget(self.layer_header_label)
        
        # Layer progress container
        self.layer_layout = QVBoxLayout()
        self.layer_layout.setSpacing(10)
        self.empty_layer_label = QLabel("Waiting for Docker layer output...")
        self.empty_layer_label.setObjectName("dockerPullLayerEmptyState")
        self.empty_layer_label.setAccessibleName("Docker pull waiting state")
        self.empty_layer_label.setAlignment(Qt.AlignCenter)
        self.empty_layer_label.setWordWrap(True)
        self.layer_layout.addWidget(self.empty_layer_label)
        scroll_layout.addLayout(self.layer_layout)
        scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        
        # Add scroll area to layer frame
        layer_frame_layout = QVBoxLayout(self.layer_frame)
        layer_frame_layout.setContentsMargins(0, 0, 0, 0)
        layer_frame_layout.addWidget(self.scroll_area)
        
        # Add widgets to layout
        layout.addWidget(self.title_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.overall_progress)
        layout.addWidget(self.layer_frame, 1)  # Give the layer frame stretch factor
        
        self.setLayout(layout)
        
        # Initialize layer tracking
        self.layers = {}
        self.layer_widgets = {}
        self.total_layers = 0
        self.apply_theme(self._is_dark)

    @staticmethod
    def _resolve_theme(parent, is_dark):
        if is_dark is not None:
            return bool(is_dark)

        parent_stylesheet = getattr(parent, "_current_stylesheet", "")
        if parent_stylesheet:
            dark_markers = ("#0F1117", "#272727", "#1E1E1E")
            return any(marker in parent_stylesheet for marker in dark_markers)

        return True

    def apply_theme(self, is_dark):
        self._is_dark = bool(is_dark)
        colors = DOCKER_PULL_DIALOG_STYLE_COLORS[self._is_dark]
        self.setStyleSheet(
            f"""
            QDialog#dockerPullDialog {{
                background-color: {colors["dialog_bg"]};
                color: {colors["body_text"]};
            }}
            """
        )
        self.title_label.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {colors['title_text']};"
        )
        self.info_label.setStyleSheet(
            f"font-size: 14px; color: {colors['body_text']};"
        )
        self.overall_progress.setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid {colors["overall_progress_border"]};
                border-radius: 6px;
                text-align: center;
                height: 25px;
                background-color: {colors["overall_progress_bg"]};
                color: {colors["body_text"]};
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {colors["progress_chunk"]};
                border-radius: 6px;
            }}
            """
        )
        self.layer_frame.setStyleSheet(
            f"""
            QFrame#dockerPullLayerFrame {{
                background-color: {colors["panel_bg"]};
                border-radius: 8px;
            }}
            """
        )
        self.scroll_area.setStyleSheet(
            f"""
            QScrollArea#dockerPullLayerScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background-color: {colors["scrollbar_track"]};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {colors["scrollbar_handle"]};
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )
        self.layer_header_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {colors['title_text']};"
        )
        self.empty_layer_label.setStyleSheet(
            f"color: {colors['muted_text']}; font-size: 13px;"
        )
        for widgets in self.layer_widgets.values():
            self._apply_layer_row_theme(widgets)

    @staticmethod
    def _layer_object_suffix(layer_id):
        safe_layer_id = re.sub(r"[^A-Za-z0-9_]", "_", layer_id)
        return safe_layer_id[:48]

    @staticmethod
    def _synthetic_layer_id(line):
        normalized = SIZE_PROGRESS_NORMALIZER.sub("<size-progress>", line.strip())
        normalized = PERCENT_PROGRESS_NORMALIZER.sub("<percent>", normalized)
        normalized = normalized.encode("utf-8")
        return hashlib.sha1(normalized).hexdigest()[:12]

    @staticmethod
    def _size_to_bytes(value, unit):
        return float(value) * SIZE_UNIT_BYTES.get(unit.upper(), 1)

    @classmethod
    def _progress_from_size_status(cls, status):
        progress_match = SIZE_PROGRESS_PATTERN.search(status)
        if not progress_match:
            return None

        current_value, current_unit, total_value, total_unit = progress_match.groups()
        current_bytes = cls._size_to_bytes(current_value, current_unit)
        total_bytes = cls._size_to_bytes(total_value, total_unit)
        if total_bytes <= 0:
            return None

        progress = int((current_bytes / total_bytes) * 100)
        return max(0, min(100, progress))

    def _create_layer_row(self, layer_id, label_text, status, accessible_name):
        layer_layout = QHBoxLayout()
        layer_layout.setSpacing(12)
        object_suffix = self._layer_object_suffix(layer_id)

        layer_label = QLabel(label_text)
        layer_label.setObjectName(f"dockerPullLayerLabel_{object_suffix}")
        layer_label.setAccessibleName(accessible_name)
        layer_label.setToolTip(layer_id)
        layer_label.setMinimumWidth(76)
        layer_label.setMaximumWidth(112)
        layer_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        status_label = QLabel(status)
        status_label.setObjectName(f"dockerPullLayerStatus_{object_suffix}")
        status_label.setAccessibleName(f"{accessible_name} status")
        status_label.setToolTip(status)
        status_label.setWordWrap(True)
        status_label.setMinimumWidth(120)
        status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layer_progress = QProgressBar()
        layer_progress.setObjectName(f"dockerPullLayerProgress_{object_suffix}")
        layer_progress.setAccessibleName(f"{accessible_name} progress")
        layer_progress.setRange(0, 100)
        layer_progress.setValue(0)
        layer_progress.setMinimumHeight(20)
        layer_progress.setMinimumWidth(140)
        layer_progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layer_layout.addWidget(layer_label)
        layer_layout.addWidget(layer_progress, 1)
        layer_layout.addWidget(status_label, 1)

        widgets = {
            'layout': layer_layout,
            'label': layer_label,
            'progress': layer_progress,
            'status': status_label
        }
        self.layer_layout.addLayout(layer_layout)
        self._apply_layer_row_theme(widgets)
        return widgets

    def _apply_layer_row_theme(self, widgets):
        colors = DOCKER_PULL_DIALOG_STYLE_COLORS[self._is_dark]
        widgets['label'].setStyleSheet(
            f"color: {colors['layer_accent']}; font-weight: bold; font-family: monospace; font-size: 13px;"
        )
        widgets['status'].setStyleSheet(
            f"color: {colors['body_text']}; font-family: monospace; font-size: 13px;"
        )
        widgets['progress'].setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid {colors["progress_border"]};
                border-radius: 5px;
                text-align: center;
                height: 20px;
                background-color: {colors["progress_bg"]};
                color: {colors["body_text"]};
                font-size: 12px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {colors["progress_chunk"]};
                border-radius: 5px;
            }}
            """
        )
    
    @pyqtSlot(str)
    def update_pull_progress(self, line):
        """Update the pull progress based on Docker output.
        
        Args:
            line: Line of Docker pull output
        """
        # Log the raw Docker pull output
        logging.info(f"Docker pull output: {line.strip()}")
        
        # Process the line to extract layer information
        if "Pulling from" in line:
            repo_info = line.strip()
            logging.info(f"Pulling Docker image repository: {repo_info}")
            self.info_label.setText(f"Pulling image: {line}")
            return
            
        # Match layer ID - handle both old and new Docker output formats
        layer_match = re.search(r'([a-f0-9]{12}): (.*)', line)
        digest_match = re.search(r'(sha256:[a-f0-9]{64}): (.*)', line)
        
        if layer_match or digest_match:
            match = layer_match or digest_match
            layer_id = match.group(1)
            status = match.group(2)
            
            # Initialize layer if not seen before
            if layer_id not in self.layers:
                self.empty_layer_label.hide()
                self.layers[layer_id] = {
                    'id': layer_id,
                    'status': status,
                    'progress': 0
                }
                self.total_layers += 1
                logging.info(f"New layer detected: {layer_id} - Total layers: {self.total_layers}")
                
                self.layer_widgets[layer_id] = self._create_layer_row(
                    layer_id,
                    f"{layer_id[:8]}...",
                    status,
                    f"Docker layer {layer_id[:8]}",
                )
            
            # Update layer status
            self.layers[layer_id]['status'] = status
            
            # Update status label if it exists
            if layer_id in self.layer_widgets and 'status' in self.layer_widgets[layer_id]:
                self.layer_widgets[layer_id]['status'].setText(status)
                self.layer_widgets[layer_id]['status'].setToolTip(status)
            
            # Check for progress information or completion status
            progress_match = re.search(r'(\d+)%', status)
            if progress_match:
                progress = int(progress_match.group(1))
                self.layers[layer_id]['progress'] = progress
                
                # Log progress updates at 25% intervals to avoid excessive logging
                prev_progress = getattr(self, f"_prev_progress_{layer_id}", -25)
                if progress >= prev_progress + 25 or progress == 100:
                    logging.info(f"Layer {layer_id}: {progress}% complete - Status: {status}")
                    setattr(self, f"_prev_progress_{layer_id}", progress - (progress % 25))
                
                # Update progress bar
                if layer_id in self.layer_widgets:
                    self.layer_widgets[layer_id]['progress'].setValue(progress)
            elif "Download complete" in status or "Pull complete" in status or "Already exists" in status:
                # Set to 100% when complete
                self.layers[layer_id]['progress'] = 100
                if layer_id in self.layer_widgets:
                    self.layer_widgets[layer_id]['progress'].setValue(100)
                logging.info(f"Layer {layer_id} completed: {status}")
            else:
                # Log status updates without progress percentage
                logging.info(f"Layer {layer_id} status update: {status}")
            
            # Update overall progress
            self._update_overall_progress()
            
        # Handle newer Docker output format with direct status updates
        elif "Downloading" in line or "Extracting" in line or "Download complete" in line or "Pull complete" in line:
            # For newer Docker output that doesn't always include layer IDs
            # Create a stable synthetic layer ID based on the line content
            line_hash = self._synthetic_layer_id(line)
            status = line.strip()
            
            # Initialize layer if not seen before
            if line_hash not in self.layers:
                self.empty_layer_label.hide()
                self.layers[line_hash] = {
                    'id': line_hash,
                    'status': status,
                    'progress': 0
                }
                self.total_layers += 1
                logging.info(f"New status line detected: {status} - Total layers: {self.total_layers}")
                
                self.layer_widgets[line_hash] = self._create_layer_row(
                    line_hash,
                    "Layer",
                    status,
                    "Docker layer",
                )
            
            # Update layer status
            self.layers[line_hash]['status'] = status
            
            # Update status label if it exists
            if line_hash in self.layer_widgets and 'status' in self.layer_widgets[line_hash]:
                self.layer_widgets[line_hash]['status'].setText(status)
                self.layer_widgets[line_hash]['status'].setToolTip(status)
            
            # Check for progress information in newer format
            progress = self._progress_from_size_status(status)
            if progress is not None:
                self.layers[line_hash]['progress'] = progress

                # Update progress bar
                if line_hash in self.layer_widgets:
                    self.layer_widgets[line_hash]['progress'].setValue(progress)
            elif "Download complete" in status or "Pull complete" in status or "Already exists" in status:
                # Set to 100% when complete
                self.layers[line_hash]['progress'] = 100
                if line_hash in self.layer_widgets:
                    self.layer_widgets[line_hash]['progress'].setValue(100)
                logging.info(f"Layer {line_hash} completed: {status}")
            
            # Update overall progress
            self._update_overall_progress()
            

    
    def _update_overall_progress(self):
        """Update the overall progress based on layer progress."""
        if not self.total_layers:
            return
            
        total_progress = sum(layer['progress'] for layer in self.layers.values())
        overall_percent = int(total_progress / self.total_layers)
        
        # Log overall progress at 10% intervals to avoid excessive logging
        prev_overall_progress = getattr(self, "_prev_overall_progress", -10)
        if overall_percent >= prev_overall_progress + 10 or overall_percent == 100:
            logging.info(f"Docker pull overall progress: {overall_percent}% complete ({self.total_layers} layers)")
            setattr(self, "_prev_overall_progress", overall_percent - (overall_percent % 10))
        
        self.overall_progress.setValue(overall_percent)
    
    @pyqtSlot(str)
    def set_message(self, message):
        """Update the dialog message.
        
        Args:
            message: New message to display
        """
        if hasattr(self, 'info_label'):
            self.info_label.setText(message)

    
    def closeEvent(self, event):
        """Handle the dialog close event."""
        event.accept()
    
    @pyqtSlot()
    def safe_close(self):
        """Safely close the dialog with a timer to prevent direct deletion."""
        # Close immediately and then use a timer to ensure proper cleanup
        self.close()
        # Use a short timer to ensure proper cleanup
        QTimer.singleShot(100, self.deleteLater)

    def set_pull_complete(self, success, message):
        """Handle pull completion.
        
        Args:
            success: Whether the pull was successful
            message: Success or error message
        """
        # Update UI to show completion status
        if success:
            self.set_message("Docker image pull completed successfully!")
            # Set overall progress to 100%
            self.overall_progress.setValue(100)
        else:
            self.set_message(f"Docker image pull failed: {message}")
        
        
        # Emit the signal to notify the parent
        self.pull_complete.emit(success, message)
        
        # Close the dialog automatically after a short delay
        QTimer.singleShot(100, self.safe_close)
