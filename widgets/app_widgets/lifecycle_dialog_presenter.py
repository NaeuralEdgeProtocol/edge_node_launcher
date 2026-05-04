from PyQt5 import sip
from PyQt5.QtCore import QTimer

from utils.lifecycle_copy import launch_dialog_copy, stop_dialog_copy
from widgets.LoadingDialog import LoadingDialog


LAUNCH_DIALOG_ATTRS = ("launcher_dialog", "startup_dialog")


class LifecycleDialogPresenter:
    """Owns lifecycle dialog references, progress routing, and safe cleanup."""

    def __init__(self, owner):
        self.owner = owner

    @staticmethod
    def qt_object_deleted(obj) -> bool:
        if obj is None:
            return True

        try:
            return sip.isdeleted(obj)
        except (RuntimeError, TypeError):
            return True

    def clear_reference(self, dialog_attr: str, dialog=None) -> None:
        """Clear a dialog attribute when it still points at the supplied dialog."""
        if not hasattr(self.owner, dialog_attr):
            return

        try:
            current_dialog = getattr(self.owner, dialog_attr)
        except RuntimeError:
            setattr(self.owner, dialog_attr, None)
            return

        if dialog is None or current_dialog is dialog:
            setattr(self.owner, dialog_attr, None)

    def reference(self, dialog_attr: str):
        """Return a live dialog reference or clear stale/deleted wrappers."""
        if not hasattr(self.owner, dialog_attr):
            return None

        try:
            dialog = getattr(self.owner, dialog_attr)
        except RuntimeError:
            setattr(self.owner, dialog_attr, None)
            return None

        if dialog is None:
            return None

        if self.qt_object_deleted(dialog):
            setattr(self.owner, dialog_attr, None)
            self.owner.add_log(f"Cleared deleted {dialog_attr}", debug=True)
            return None

        return dialog

    def is_visible(self, dialog_attr: str) -> bool:
        dialog = self.reference(dialog_attr)
        if dialog is None:
            return False

        try:
            return dialog.isVisible()
        except RuntimeError:
            self.clear_reference(dialog_attr, dialog)
            return False

    def update_progress(
        self,
        dialog_attr: str,
        message: str,
        *,
        require_visible: bool = False,
        process_events: bool = True,
    ) -> bool:
        dialog = self.reference(dialog_attr)
        if dialog is None:
            return False
        if require_visible and not self.is_visible(dialog_attr):
            return False

        try:
            dialog.update_progress(message, process_events=process_events)
            return True
        except TypeError:
            dialog.update_progress(message)
            return True
        except RuntimeError:
            self.clear_reference(dialog_attr, dialog)
            return False

    def update_launch_progress(self, message: str, *, process_events: bool = True) -> bool:
        if self.update_progress("launcher_dialog", message, process_events=process_events):
            return True
        return self.update_progress(
            "startup_dialog",
            message,
            require_visible=True,
            process_events=process_events,
        )

    def show_loading_reference(
        self,
        dialog_attr: str,
        *,
        title: str,
        message: str,
        progress_message: str = None,
    ):
        dialog = LoadingDialog(
            self.owner,
            title=title,
            message=message,
            size=50,
        )
        setattr(self.owner, dialog_attr, dialog)
        dialog.show()

        if progress_message:
            self.update_progress(dialog_attr, progress_message)

        self.owner._queue_ui_refresh(dialog)
        return dialog

    def show_launch_loading(self, node_alias: str = None):
        dialog_copy = launch_dialog_copy(node_alias)
        return self.show_loading_reference(
            "launcher_dialog",
            title=dialog_copy.title,
            message=dialog_copy.message,
            progress_message="Preparing to launch Docker container...",
        )

    def show_new_node_loading(self, display_name: str = None):
        dialog_copy = launch_dialog_copy(display_name, is_new_node=True)
        return self.show_loading_reference(
            "startup_dialog",
            title=dialog_copy.title,
            message=dialog_copy.message,
        )

    def show_stop_loading(self, node_alias: str = None):
        dialog_copy = stop_dialog_copy(node_alias)
        return self.show_loading_reference(
            "toggle_dialog",
            title=dialog_copy.title,
            message=dialog_copy.message,
            progress_message="Preparing to stop Docker container...",
        )

    def safe_close_reference(self, dialog_attr: str, dialog=None) -> bool:
        if dialog is None:
            dialog = self.reference(dialog_attr)
        if dialog is None:
            return False

        if self.reference(dialog_attr) is not dialog:
            return False

        try:
            if hasattr(dialog, "safe_close"):
                dialog.safe_close()
            else:
                dialog.close()
            return True
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                self.clear_reference(dialog_attr, dialog)
                self.owner.add_log(f"Cleared deleted {dialog_attr}", debug=True)
                return False
            self.owner.add_log(f"Error closing {dialog_attr}: {str(e)}", debug=True)
            return False

    def schedule_safe_close_reference(
        self,
        dialog_attr: str,
        *,
        close_delay_ms: int,
        clear_delay_ms: int,
    ) -> bool:
        """Close and clear a dialog later without clearing a newer replacement."""
        dialog = self.reference(dialog_attr)
        if dialog is None:
            return False

        QTimer.singleShot(
            close_delay_ms,
            lambda dialog=dialog: self.safe_close_reference(dialog_attr, dialog),
        )
        QTimer.singleShot(
            clear_delay_ms,
            lambda dialog=dialog: self.clear_reference(dialog_attr, dialog),
        )
        return True

    def schedule_safe_close_launch_references(
        self,
        *,
        close_delay_ms: int = 0,
        clear_delay_ms: int = 500,
    ) -> None:
        for dialog_attr in LAUNCH_DIALOG_ATTRS:
            self.schedule_safe_close_reference(
                dialog_attr,
                close_delay_ms=close_delay_ms,
                clear_delay_ms=clear_delay_ms,
            )

    def set_docker_pull_complete(self, success: bool, message: str) -> bool:
        dialog = self.reference("docker_pull_dialog")
        if dialog is None:
            return False

        try:
            dialog.set_pull_complete(success, message)
            return True
        except RuntimeError:
            self.clear_reference("docker_pull_dialog", dialog)
            return False

    def update_docker_pull_progress(self, line: str) -> bool:
        dialog = self.reference("docker_pull_dialog")
        if dialog is None:
            return False

        try:
            dialog.update_pull_progress(line)
            return True
        except RuntimeError:
            self.clear_reference("docker_pull_dialog", dialog)
            return False

    def close_docker_pull_reference(self) -> bool:
        dialog = self.reference("docker_pull_dialog")
        if dialog is None:
            return False

        closed = self.safe_close_reference("docker_pull_dialog", dialog)
        self.clear_reference("docker_pull_dialog", dialog)
        return closed

    def close_reference(self, dialog_attr: str) -> bool:
        """Close a stored dialog reference, tolerating already-deleted Qt wrappers."""
        dialog = self.reference(dialog_attr)
        if dialog is None:
            return False

        closed = self.safe_close_reference(dialog_attr, dialog)
        if closed:
            self.clear_reference(dialog_attr, dialog)
            self.owner.add_log(f"Closed {dialog_attr}", debug=True)
        return closed

    def close_launch_references(self) -> None:
        for dialog_attr in LAUNCH_DIALOG_ATTRS:
            self.close_reference(dialog_attr)
