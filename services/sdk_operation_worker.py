from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QThread, pyqtSignal


class SdkOperationThread(QThread):
    """Run one SDK operation away from the Qt UI thread."""

    operation_finished = pyqtSignal(str, object)
    operation_failed = pyqtSignal(str, str)

    def __init__(self, operation_name: str, operation: Callable[[], object], parent=None):
        super().__init__(parent)
        self.operation_name = operation_name
        self.operation = operation

    def run(self):
        try:
            self.operation_finished.emit(self.operation_name, self.operation())
        except Exception as exc:
            self.operation_failed.emit(self.operation_name, str(exc))
