from utils import docker_commands
from utils.const import DOCKER_VOLUME_PATH


class FakeRegistry:
    def remove_container(self, container_name):
        self.removed = container_name


def make_handler(monkeypatch, container_name="r1node"):
    monkeypatch.setattr(docker_commands, "ContainerRegistry", FakeRegistry)
    return docker_commands.DockerCommandHandler(container_name)


def test_launch_command_uses_expected_container_volume_and_image(monkeypatch):
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: False)
    monkeypatch.setattr(docker_commands.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")

    command = handler.get_launch_command("ratio1_vol")

    assert command[:2] == ["docker", "run"]
    assert "--gpus=all" not in command
    assert command[command.index("--name") + 1] == "r1node"
    assert command[command.index("-v") + 1] == f"ratio1_vol:{DOCKER_VOLUME_PATH}"
    assert command[-1] == docker_commands.DOCKER_IMAGE


def test_launch_command_adds_gpu_flag_when_available(monkeypatch):
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)
    monkeypatch.setattr(docker_commands.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")

    command = handler.get_launch_command("ratio1_vol")

    assert "--gpus=all" in command


def test_launch_command_can_target_captured_container_name(monkeypatch):
    handler = make_handler(monkeypatch, container_name="r1node")
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: False)
    monkeypatch.setattr(docker_commands.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")

    command = handler.get_launch_command("ratio1_vol", container_name="r1node2")

    assert command[command.index("--name") + 1] == "r1node2"
    assert handler.container_name == "r1node"


def test_launch_container_threaded_defers_launch_command_build_until_worker(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []

    def fail_if_called_on_inspect_callback(*args, **kwargs):
        raise AssertionError("get_launch_command should run inside the launch worker")

    def fake_execute_direct(command, callback=None, error_callback=None):
        calls.append(command)
        if command == ["docker", "container", "inspect", "r1node"]:
            callback(("", "not found", 1))

    monkeypatch.setattr(handler, "get_launch_command", fail_if_called_on_inspect_callback)
    monkeypatch.setattr(handler, "_execute_direct_threaded", fake_execute_direct)
    monkeypatch.setattr(handler, "_execute_launch_threaded", lambda volume_name, callback=None, error_callback=None: calls.append(("launch", volume_name)))

    handler.launch_container_threaded("ratio1_vol")

    assert calls == [
        ["docker", "container", "inspect", "r1node"],
        ("launch", "ratio1_vol"),
    ]


def test_list_containers_parses_docker_ps_output(monkeypatch):
    handler = make_handler(monkeypatch)

    def fake_execute(command):
        assert command[:3] == ["docker", "ps", "--format"]
        return "r1node\tUp 2 minutes\tabc123\nr1node2\tExited (0)\tdef456\n", "", 0

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    containers = handler.list_containers()

    assert containers == [
        {"name": "r1node", "status": "Up 2 minutes", "id": "abc123", "running": True},
        {"name": "r1node2", "status": "Exited (0)", "id": "def456", "running": False},
    ]
