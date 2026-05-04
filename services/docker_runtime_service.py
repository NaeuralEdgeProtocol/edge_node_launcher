import inspect


class DockerRuntimeService:
    """Transitional boundary around Docker command execution.

    The launcher still uses the existing DockerCommandHandler implementation,
    but the main form now talks to this runtime service. Future Phase 2 slices
    can move lifecycle policy here without changing every UI call site again.
    """

    def __init__(self, command_handler):
        self._command_handler = command_handler

    @property
    def container_name(self):
        return self._command_handler.container_name

    @container_name.setter
    def container_name(self, value):
        self._command_handler.container_name = value

    @property
    def command_handler(self):
        return self._command_handler

    def set_container_name(self, container_name):
        return self._command_handler.set_container_name(container_name)

    def is_container_running(self, container_name=None):
        method = self._command_handler.is_container_running
        if container_name is None or len(inspect.signature(method).parameters) == 0:
            return method()
        return method(container_name)

    def set_debug_mode(self, enabled):
        return self._command_handler.set_debug_mode(enabled)

    def execute_command(self, command, timeout=None):
        if timeout is None:
            return self._command_handler.execute_command(command)
        return self._command_handler.execute_command(command, timeout=timeout)

    def get_node_info(self, callback, error_callback):
        return self._command_handler.get_node_info(callback, error_callback)

    def get_node_history(self, callback, error_callback):
        return self._command_handler.get_node_history(callback, error_callback)

    def get_container_stats(self, callback, error_callback):
        return self._command_handler.get_container_stats(callback, error_callback)

    def pull_image(self, callback, error_callback, output_callback=None):
        return self._command_handler.pull_image(callback, error_callback, output_callback)

    def launch_container_threaded(self, volume_name=None, callback=None, error_callback=None):
        return self._command_handler.launch_container_threaded(volume_name, callback, error_callback)

    def stop_container_threaded(self, container_name, callback, error_callback):
        return self._command_handler.stop_container_threaded(container_name, callback, error_callback)

    def remove_container_threaded(self, container_name, callback, error_callback, force=True):
        return self._command_handler.remove_container_threaded(container_name, callback, error_callback, force=force)

    def update_node_name(self, new_name, on_success, on_error):
        return self._command_handler.update_node_name(new_name, on_success, on_error)

    def __getattr__(self, name):
        return getattr(self._command_handler, name)
