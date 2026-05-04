from utils import docker_commands
from utils import docker as docker_utils
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

    def fake_execute(command, timeout=None):
        assert command[:3] == ["docker", "ps", "--format"]
        assert timeout == docker_commands.DOCKER_STATUS_TIMEOUT
        return "r1node\tUp 2 minutes\tabc123\nr1node2\tExited (0)\tdef456\n", "", 0

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    containers = handler.list_containers()

    assert containers == [
        {"name": "r1node", "status": "Up 2 minutes", "id": "abc123", "running": True},
        {"name": "r1node2", "status": "Exited (0)", "id": "def456", "running": False},
    ]


def test_execute_command_uses_timeout_and_hides_windows_console(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []
    create_no_window = 0x08000000

    class FakeResult:
        stdout = "ok"
        stderr = ""
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return FakeResult()

    monkeypatch.setattr(docker_commands.os, "name", "nt")
    monkeypatch.setattr(docker_commands.subprocess, "CREATE_NO_WINDOW", create_no_window, raising=False)
    monkeypatch.setattr(docker_commands.subprocess, "run", fake_run)

    assert handler.execute_command(["docker", "ps"], timeout=7) == ("ok", "", 0)

    assert calls == [
        (
            ["docker", "ps"],
            {
                "capture_output": True,
                "text": True,
                "timeout": 7,
                "creationflags": create_no_window,
            },
        )
    ]


def test_execute_command_returns_timeout_error(monkeypatch):
    handler = make_handler(monkeypatch)

    def fake_run(command, **kwargs):
        raise docker_commands.subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(docker_commands.subprocess, "run", fake_run)

    stdout, stderr, return_code = handler.execute_command(["docker", "ps"], timeout=3)

    assert stdout == ""
    assert stderr == "Command timed out after 3 seconds: docker ps"
    assert return_code == 124


def test_inspect_container_uses_short_status_timeout(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []

    def fake_execute(command, timeout=None):
        calls.append((command, timeout))
        return ('[{"State": {"Running": true}}]', "", 0)

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    assert handler.inspect_container("r1node") == {"State": {"Running": True}}
    assert calls == [
        (["docker", "inspect", "r1node"], docker_commands.DOCKER_STATUS_TIMEOUT)
    ]


def test_direct_command_thread_uses_remote_timeout_and_prefix(monkeypatch):
    calls = []

    class FakeResult:
        stdout = "started"
        stderr = ""
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return FakeResult()

    monkeypatch.setattr(docker_commands.os, "name", "posix")
    monkeypatch.setattr(docker_commands.subprocess, "run", fake_run)
    thread = docker_commands.DockerDirectCommandThread(
        ["docker", "container", "inspect", "r1node"],
        remote_ssh_command=["ssh", "ratio@192.0.2.10"],
    )

    thread.run()

    assert calls == [
        (
            ["ssh", "ratio@192.0.2.10", "docker", "container", "inspect", "r1node"],
            {
                "capture_output": True,
                "text": True,
                "timeout": docker_commands.REMOTE_TIMEOUT,
            },
        )
    ]
    assert thread.result_data == ("started", "", 0)
    assert thread.error_message is None


def test_direct_command_thread_reports_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise docker_commands.subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(docker_commands.subprocess, "run", fake_run)
    thread = docker_commands.DockerDirectCommandThread(["docker", "ps"])

    thread.run()

    assert thread.result_data is None
    assert thread.error_message == f"Command timed out after {docker_commands.DEFAULT_TIMEOUT} seconds: docker ps"


def test_remote_connection_preserves_quoted_ssh_args(monkeypatch):
    handler = make_handler(monkeypatch)

    handler.set_remote_connection(
        'ssh -o ProxyCommand="ssh -W %h:%p bastion" -i "C:/Users/vital/.ssh/edge key" ratio@192.0.2.10'
    )

    assert handler.remote_ssh_command == [
        "ssh",
        "-o",
        "ProxyCommand=ssh -W %h:%p bastion",
        "-i",
        "C:/Users/vital/.ssh/edge key",
        "ratio@192.0.2.10",
    ]


def test_docker_mixin_remote_connection_preserves_structured_ssh_args():
    class FakeHostConfig:
        ansible_host = "192.0.2.10"
        ansible_user = "ratio"
        ansible_become_password = None
        ansible_ssh_private_key_file = "C:/Users/vital/.ssh/edge key"
        ansible_ssh_common_args = '-o ProxyCommand="ssh -W %h:%p bastion"'

    class FakeHostsManager:
        def get_host(self, host_name):
            assert host_name == "edge-a"
            return FakeHostConfig()

    class FakeHostSelector:
        hosts_manager = FakeHostsManager()

        def get_current_host(self):
            return "edge-a"

    class FakeSSHService:
        def __init__(self):
            self.config = None

        def configure(self, config):
            self.config = config

    class FakeDockerCommands:
        def __init__(self):
            self.ssh_command = None

        def set_remote_connection(self, ssh_command):
            self.ssh_command = ssh_command

    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.host_selector = FakeHostSelector()
    launcher.ssh_service = FakeSSHService()
    launcher.docker_commands = FakeDockerCommands()
    launcher._DockerUtilsMixin__setup_docker_run = lambda: None

    launcher.set_remote_connection(
        'ssh -o ProxyCommand="ssh -W %h:%p bastion" -i "C:/Users/vital/.ssh/edge key" ratio@192.0.2.10'
    )

    assert launcher.is_remote is True
    assert launcher.ssh_service.config.ssh_args == [
        "-o",
        "ProxyCommand=ssh -W %h:%p bastion",
    ]
    assert launcher.remote_ssh_command == [
        "ssh",
        "-o",
        "ProxyCommand=ssh -W %h:%p bastion",
        "-i",
        "C:/Users/vital/.ssh/edge key",
        "ratio@192.0.2.10",
    ]
