from services.docker_runtime_service import DockerRuntimeService


class FakeDockerCommands:
    def __init__(self):
        self.container_name = "r1node"
        self.calls = []

    def set_container_name(self, container_name):
        self.calls.append(("set_container_name", container_name))
        self.container_name = container_name

    def is_container_running(self, container_name=None):
        self.calls.append(("is_container_running", container_name))
        return True

    def execute_command(self, command, timeout=None):
        self.calls.append(("execute_command", command, timeout))
        return "stdout", "", 0

    def launch_container_threaded(self, volume_name=None, callback=None, error_callback=None):
        self.calls.append(("launch_container_threaded", volume_name))
        if callback:
            callback(("", "", 0))

    def pull_image(self, callback, error_callback, output_callback=None, container_name=None):
        self.calls.append(("pull_image", container_name))
        callback(("", "", 0))

    def custom_method(self):
        self.calls.append(("custom_method",))
        return "custom"


def test_docker_runtime_service_delegates_container_identity():
    commands = FakeDockerCommands()
    service = DockerRuntimeService(commands)

    assert service.container_name == "r1node"

    service.set_container_name("r1node2")

    assert service.container_name == "r1node2"
    assert commands.calls == [("set_container_name", "r1node2")]


def test_docker_runtime_service_delegates_common_runtime_calls():
    commands = FakeDockerCommands()
    service = DockerRuntimeService(commands)
    results = []

    assert service.is_container_running("r1node")
    assert service.execute_command(["docker", "ps"], timeout=7) == ("stdout", "", 0)
    service.launch_container_threaded("r1vol", results.append, None)

    assert commands.calls == [
        ("is_container_running", "r1node"),
        ("execute_command", ["docker", "ps"], 7),
        ("launch_container_threaded", "r1vol"),
    ]
    assert results == [("", "", 0)]


def test_docker_runtime_service_keeps_transition_access_to_unwrapped_methods():
    commands = FakeDockerCommands()
    service = DockerRuntimeService(commands)

    assert service.custom_method() == "custom"
    assert commands.calls == [("custom_method",)]


def test_docker_runtime_service_forwards_pull_target_when_supported():
    commands = FakeDockerCommands()
    service = DockerRuntimeService(commands)
    results = []

    service.pull_image(results.append, None, container_name="r1node2")

    assert commands.calls == [("pull_image", "r1node2")]
    assert results == [("", "", 0)]


def test_docker_runtime_service_supports_legacy_pull_handlers():
    class LegacyPullCommands(FakeDockerCommands):
        def pull_image(self, callback, error_callback, output_callback=None):
            self.calls.append(("legacy_pull_image",))
            callback(("", "", 0))

    commands = LegacyPullCommands()
    service = DockerRuntimeService(commands)
    results = []

    service.pull_image(results.append, None, container_name="r1node2")

    assert commands.calls == [("legacy_pull_image",)]
    assert results == [("", "", 0)]
