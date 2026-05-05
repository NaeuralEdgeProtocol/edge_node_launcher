from utils import docker_commands
from utils import docker as docker_utils
from utils.const import DOCKER_VOLUME_PATH
from utils.edge_image_config import DEVNET_EDGE_NODE_IMAGE, GPU_PRODUCTION_EDGE_NODE_IMAGE, configure_edge_node_image


class FakeRegistry:
    def remove_container(self, container_name):
        self.removed = container_name


def make_handler(monkeypatch, container_name="r1node"):
    monkeypatch.setattr(docker_commands, "ContainerRegistry", FakeRegistry)
    return docker_commands.DockerCommandHandler(container_name)


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeStreamingThread:
    def __init__(self, command):
        self.command = command
        self.output_received = FakeSignal()
        self.finished = FakeSignal()
        self.error_message = None
        self.result_data = ("", "", 0)
        self.started = False

    def start(self):
        self.started = True


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


def test_launch_command_uses_configured_devnet_image(monkeypatch):
    configure_edge_node_image(cli_image="devnet", environ={}, production_mode=False)
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: False)
    monkeypatch.setattr(docker_commands.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")

    command = handler.get_launch_command("ratio1_vol")

    assert command[-1] == DEVNET_EDGE_NODE_IMAGE


def test_launch_command_adds_gpu_flag_when_available(monkeypatch):
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)
    monkeypatch.setattr(docker_commands.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")

    command = handler.get_launch_command("ratio1_vol")

    assert "--gpus=all" in command
    assert command[-1] == GPU_PRODUCTION_EDGE_NODE_IMAGE


def test_launch_command_does_not_attach_gpu_to_secondary_node(monkeypatch):
    handler = make_handler(monkeypatch, container_name="r1node2")
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)
    monkeypatch.setattr(docker_commands.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")

    command = handler.get_launch_command("ratio1_vol")

    assert "--gpus=all" not in command
    assert command[-1] == docker_commands.DOCKER_IMAGE


def test_required_image_uses_gpu_image_for_primary_when_available(monkeypatch):
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)

    assert handler.get_required_image("r1node") == GPU_PRODUCTION_EDGE_NODE_IMAGE


def test_required_image_uses_cpu_image_for_secondary_when_gpu_available(monkeypatch):
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)

    assert handler.get_required_image("r1node2") == docker_commands.DOCKER_IMAGE


def test_ensure_image_exists_checks_runtime_plan_image(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)

    def fake_execute(command, timeout=None):
        calls.append((command, timeout))
        return "image-id", "", 0

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    assert handler._ensure_image_exists("r1node") is True
    assert calls == [
        (
            ["docker", "images", "-q", GPU_PRODUCTION_EDGE_NODE_IMAGE],
            docker_commands.DOCKER_STATUS_TIMEOUT,
        )
    ]


def test_pull_image_uses_runtime_plan_image(monkeypatch):
    created_threads = []
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)

    def fake_thread_factory(command):
        thread = FakeStreamingThread(command)
        created_threads.append(thread)
        return thread

    monkeypatch.setattr(docker_commands, "DockerStreamingCommandThread", fake_thread_factory)

    handler.pull_image(lambda result: None, lambda error: None, container_name="r1node")

    assert created_threads[0].command == ["docker", "pull", GPU_PRODUCTION_EDGE_NODE_IMAGE]
    assert created_threads[0].started is True


def test_pull_image_can_target_secondary_cpu_image(monkeypatch):
    created_threads = []
    handler = make_handler(monkeypatch)
    monkeypatch.setattr(handler, "check_nvidia_gpu_available", lambda: True)

    def fake_thread_factory(command):
        thread = FakeStreamingThread(command)
        created_threads.append(thread)
        return thread

    monkeypatch.setattr(docker_commands, "DockerStreamingCommandThread", fake_thread_factory)

    handler.pull_image(lambda result: None, lambda error: None, container_name="r1node2")

    assert created_threads[0].command == ["docker", "pull", docker_commands.DOCKER_IMAGE]


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
        assert command[command.index("-f") + 1] == "name=r1node"
        assert timeout == docker_commands.DOCKER_STATUS_TIMEOUT
        return "r1node\tUp 2 minutes\tabc123\nr1node2\tExited (0)\tdef456\n", "", 0

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    containers = handler.list_containers()

    assert containers == [
        {"name": "r1node", "status": "Up 2 minutes", "id": "abc123", "running": True},
        {"name": "r1node2", "status": "Exited (0)", "id": "def456", "running": False},
    ]


def test_list_containers_uses_active_devnet_filter(monkeypatch):
    configure_edge_node_image(cli_image="devnet", environ={}, production_mode=False)
    handler = make_handler(monkeypatch)

    def fake_execute(command, timeout=None):
        assert command[command.index("-f") + 1] == "name=r1devnode"
        return "r1devnode\tUp 2 minutes\tabc123\n", "", 0

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    containers = handler.list_containers()

    assert containers == [
        {"name": "r1devnode", "status": "Up 2 minutes", "id": "abc123", "running": True},
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


def test_get_node_history_uses_short_telemetry_timeout(monkeypatch):
    handler = make_handler(monkeypatch, container_name="r1devnode")
    calls = []

    def fake_execute_threaded(command, callback, error_callback, input_data=None, timeout=None):
        calls.append((command, input_data, timeout))

    monkeypatch.setattr(handler, "_execute_threaded", fake_execute_threaded)

    handler.get_node_history(lambda history: None, lambda error: None)

    assert calls == [
        (
            "get_node_history",
            None,
            docker_commands.NODE_HISTORY_TIMEOUT,
        )
    ]


def test_get_node_info_uses_short_telemetry_timeout(monkeypatch):
    handler = make_handler(monkeypatch, container_name="r1devnode")
    calls = []

    def fake_execute_threaded(command, callback, error_callback, input_data=None, timeout=None):
        calls.append((command, input_data, timeout))

    monkeypatch.setattr(handler, "_execute_threaded", fake_execute_threaded)

    handler.get_node_info(lambda info: None, lambda error: None)

    assert calls == [
        (
            "get_node_info",
            None,
            docker_commands.NODE_INFO_TIMEOUT,
        )
    ]


def test_docker_command_thread_uses_custom_timeout(monkeypatch):
    calls = []
    thread = docker_commands.DockerCommandThread("r1node", "get_node_history", timeout=7)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

        class Result:
            returncode = 0
            stdout = "{}"
            stderr = ""

        return Result()

    monkeypatch.setattr(docker_commands.subprocess, "run", fake_run)
    monkeypatch.setattr(docker_commands.os, "name", "posix")

    thread.run()

    assert calls[0][1]["timeout"] == 7


def test_get_container_stats_uses_bounded_docker_stats_worker(monkeypatch):
    handler = make_handler(monkeypatch, container_name="r1devnode")
    calls = []
    received = []
    errors = []

    def fake_execute_direct(command, callback=None, error_callback=None, timeout=None):
        calls.append((command, timeout))
        callback(
            (
                '{"Container":"abc123","Name":"r1devnode","CPUPerc":"56.48%","MemUsage":"1.746GiB / 15.62GiB","MemPerc":"11.18%","NetIO":"151MB / 5.32MB","BlockIO":"0B / 0B","PIDs":"162"}',
                "",
                0,
            )
        )

    monkeypatch.setattr(handler, "_execute_direct_threaded", fake_execute_direct)

    handler.get_container_stats(received.append, errors.append)

    assert errors == []
    assert calls == [
        (
            ["docker", "stats", "r1devnode", "--no-stream", "--format", "{{json .}}"],
            docker_commands.DOCKER_STATUS_TIMEOUT,
        )
    ]
    assert received[0].cpu_percent == 56.48
    assert received[0].memory_used_gib == 1.746


def test_active_gpu_probe_uses_bounded_executor(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []

    def fake_execute(command, timeout=None):
        calls.append((command, timeout))
        if command == ["where", "nvidia-smi"]:
            return "C:\\Program Files\\NVIDIA\\nvidia-smi.exe", "", 0
        return "GPU 0: Test GPU", "", 0

    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Windows")
    monkeypatch.setattr(handler, "execute_command", fake_execute)

    assert handler.check_nvidia_gpu_available() is True
    assert calls == [
        (["where", "nvidia-smi"], docker_commands.GPU_CHECK_TIMEOUT),
        (["nvidia-smi", "-L"], docker_commands.GPU_CHECK_TIMEOUT),
    ]


def test_active_gpu_probe_returns_false_after_lookup_timeout(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []

    def fake_execute(command, timeout=None):
        calls.append((command, timeout))
        return "", "Command timed out", 124

    monkeypatch.setattr(docker_commands.platform, "system", lambda: "Linux")
    monkeypatch.setattr(handler, "execute_command", fake_execute)

    assert handler.check_nvidia_gpu_available() is False
    assert calls == [(["which", "nvidia-smi"], docker_commands.GPU_CHECK_TIMEOUT)]


def test_allowed_addresses_uses_bounded_executor(monkeypatch):
    handler = make_handler(monkeypatch)
    calls = []
    results = []

    def fake_execute(command, timeout=None):
        calls.append((command, timeout))
        return "0xabc Alice\n0xdef Bob\n", "", 0

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    handler.get_allowed_addresses(results.append, lambda error: results.append({"error": error}))

    assert calls == [
        (
            ["docker", "exec", "r1node", "get_allowed"],
            docker_commands.DEFAULT_TIMEOUT,
        )
    ]
    assert results == [{"0xabc": "Alice", "0xdef": "Bob"}]


def test_allowed_addresses_reports_executor_timeout(monkeypatch):
    handler = make_handler(monkeypatch)
    errors = []

    def fake_execute(command, timeout=None):
        return "", "Command timed out after 90 seconds: docker exec r1node get_allowed", 124

    monkeypatch.setattr(handler, "execute_command", fake_execute)

    handler.get_allowed_addresses(lambda result: None, errors.append)

    assert errors == [
        "Command failed: Command timed out after 90 seconds: docker exec r1node get_allowed"
    ]


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


def test_direct_command_thread_uses_default_timeout(monkeypatch):
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
    thread = docker_commands.DockerDirectCommandThread(["docker", "container", "inspect", "r1node"])

    thread.run()

    assert calls == [
        (
            ["docker", "container", "inspect", "r1node"],
            {
                "capture_output": True,
                "text": True,
                "timeout": docker_commands.DEFAULT_TIMEOUT,
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


def test_legacy_check_output_helper_uses_timeout_and_hidden_windows(monkeypatch):
    calls = []
    create_no_window = 0x08000000

    def fake_check_output(command, **kwargs):
        calls.append((command, kwargs))
        return "ok"

    monkeypatch.setattr(docker_utils.os, "name", "nt")
    monkeypatch.setattr(docker_utils.subprocess, "CREATE_NO_WINDOW", create_no_window, raising=False)
    monkeypatch.setattr(docker_utils.subprocess, "check_output", fake_check_output)

    assert docker_utils.check_output_no_window(["docker", "info"], timeout=11) == "ok"
    assert calls == [
        (
            ["docker", "info"],
            {
                "stderr": docker_utils.subprocess.STDOUT,
                "universal_newlines": True,
                "timeout": 11,
                "creationflags": create_no_window,
            },
        )
    ]


def test_legacy_check_docker_uses_bounded_status_checks(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.add_log = lambda *args, **kwargs: None
    calls = []

    def fake_check_output(command, timeout):
        calls.append((command, timeout))
        return "Docker version 1.0" if command == ["docker", "--version"] else "daemon ok"

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)

    assert launcher.check_docker() == (True, True, None)
    assert calls == [
        (["docker", "--version"], docker_utils.DOCKER_CHECK_TIMEOUT_SECONDS),
        (["docker", "info"], docker_utils.DOCKER_CHECK_TIMEOUT_SECONDS),
    ]


def test_legacy_check_docker_reports_daemon_timeout(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.add_log = lambda *args, **kwargs: None

    def fake_check_output(command, timeout):
        if command == ["docker", "info"]:
            raise docker_utils.subprocess.TimeoutExpired(command, timeout)
        return "Docker version 1.0"

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)

    assert launcher.check_docker() == (
        True,
        False,
        f"Docker daemon check timed out after {docker_utils.DOCKER_CHECK_TIMEOUT_SECONDS} seconds",
    )


def test_legacy_gpu_probe_uses_short_timeout(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    logs = []
    launcher.add_log = lambda *args, **kwargs: logs.append(args[0])
    calls = []

    def fake_check_output(command, timeout):
        calls.append((command, timeout))
        return "GPU 0: Test"

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)

    assert launcher.check_nvidia_gpu_available() is True
    assert calls == [(["nvidia-smi", "-L"], docker_utils.GPU_CHECK_TIMEOUT_SECONDS)]
    assert "NVIDIA GPU available: True" in logs[0]


def test_legacy_container_running_check_uses_bounded_inspect(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.container_last_run_status = False
    launcher.get_inspect_command = lambda: ["docker", "inspect", "r1node"]
    launcher.add_log = lambda *args, **kwargs: None
    post_launch_calls = []
    launcher.post_launch_setup = lambda: post_launch_calls.append("post-launch")
    calls = []

    def fake_check_output(command, timeout):
        calls.append((command, timeout))
        return "true\n"

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)

    assert launcher.is_container_running() is True
    assert calls == [
        (["docker", "inspect", "r1node"], docker_utils.DOCKER_CHECK_TIMEOUT_SECONDS)
    ]
    assert post_launch_calls == ["post-launch"]


def test_legacy_local_launch_stops_when_docker_is_not_ready(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.check_docker = lambda: (True, False, "Docker daemon is not running")
    logs = []
    warnings = []
    launcher.add_log = lambda message, *args, **kwargs: logs.append(message)
    setattr(
        launcher,
        "_DockerUtilsMixin__check_env_keys",
        lambda: (_ for _ in ()).throw(AssertionError("env check should not run")),
    )

    monkeypatch.setattr(
        docker_utils.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    launcher.launch_container()

    assert logs == ["Docker is not ready: Docker daemon is not running"]
    assert warnings == [("Docker Status", "Docker daemon is not running")]


def test_legacy_local_launch_uses_bounded_cleanup_and_run(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.check_docker = lambda: (True, True, None)
    launcher.add_log = lambda *args, **kwargs: None
    setattr(launcher, "_DockerUtilsMixin__check_env_keys", lambda: True)
    pull_calls = []
    setattr(launcher, "_DockerUtilsMixin__maybe_docker_pull", lambda: pull_calls.append("pull"))
    launcher.get_clean_cmd = lambda: ["docker", "rm", "r1node"]
    launcher.get_cmd = lambda: ["docker", "run", "-d", "ratio1/edge_node:devnet"]
    post_launch_calls = []
    launcher.post_launch_setup = lambda: post_launch_calls.append("post-launch")
    command_calls = []
    messages = []

    def fake_check_output(command, timeout):
        command_calls.append((command, timeout))
        return "ok"

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)
    monkeypatch.setattr(
        docker_utils.QMessageBox,
        "information",
        lambda parent, title, message: messages.append((title, message)),
    )

    launcher.launch_container()

    assert pull_calls == ["pull"]
    assert command_calls == [
        (["docker", "rm", "r1node"], docker_utils.DOCKER_CLEANUP_TIMEOUT_SECONDS),
        (
            ["docker", "run", "-d", "ratio1/edge_node:devnet"],
            docker_utils.DOCKER_LAUNCH_TIMEOUT_SECONDS,
        ),
    ]
    assert messages == [("Container Launch", "Container launched successfully.")]
    assert post_launch_calls == ["post-launch"]


def test_legacy_local_launch_reports_run_timeout(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.check_docker = lambda: (True, True, None)
    logs = []
    launcher.add_log = lambda message, *args, **kwargs: logs.append(message)
    setattr(launcher, "_DockerUtilsMixin__check_env_keys", lambda: True)
    setattr(launcher, "_DockerUtilsMixin__maybe_docker_pull", lambda: None)
    launcher.get_clean_cmd = lambda: ["docker", "rm", "r1node"]
    launcher.get_cmd = lambda: ["docker", "run", "-d", "ratio1/edge_node:devnet"]
    post_launch_calls = []
    launcher.post_launch_setup = lambda: post_launch_calls.append("post-launch")
    warnings = []

    def fake_check_output(command, timeout):
        if command[:2] == ["docker", "run"]:
            raise docker_utils.subprocess.TimeoutExpired(command, timeout)
        return "ok"

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)
    monkeypatch.setattr(
        docker_utils.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    launcher.launch_container()

    assert warnings == [("Container Launch", "Failed to launch container")]
    assert any("container start timed out" in message for message in logs)
    assert post_launch_calls == []


def test_legacy_stop_uses_bounded_stop_and_cleanup(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.docker_container_name = "r1node"
    launcher.add_log = lambda *args, **kwargs: None
    launcher.get_stop_command = lambda: ["docker", "stop"]
    launcher.get_clean_cmd = lambda: ["docker", "rm", "r1node"]
    command_calls = []
    messages = []

    def fake_check_output(command, timeout):
        command_calls.append((command, timeout))
        return ""

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)
    monkeypatch.setattr(docker_utils, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        docker_utils.QMessageBox,
        "information",
        lambda parent, title, message: messages.append((title, message)),
    )

    launcher.stop_container(container_name="r1node2")

    assert command_calls == [
        (["docker", "stop", "r1node2"], docker_utils.DOCKER_STOP_TIMEOUT_SECONDS),
        (["docker", "rm", "r1node2"], docker_utils.DOCKER_CLEANUP_TIMEOUT_SECONDS),
    ]
    assert messages == [("Container Stop", "Container stopped successfully.")]


def test_legacy_stop_reports_timeout_without_cleanup(monkeypatch):
    launcher = object.__new__(docker_utils._DockerUtilsMixin)
    launcher.docker_container_name = "r1node"
    logs = []
    launcher.add_log = lambda message, *args, **kwargs: logs.append(message)
    launcher.get_stop_command = lambda: ["docker", "stop"]
    launcher.get_clean_cmd = lambda: ["docker", "rm", "r1node"]
    command_calls = []
    warnings = []

    def fake_check_output(command, timeout):
        command_calls.append((command, timeout))
        raise docker_utils.subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(docker_utils, "check_output_no_window", fake_check_output)
    monkeypatch.setattr(
        docker_utils.QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    launcher.stop_container()

    assert command_calls == [
        (["docker", "stop", "r1node"], docker_utils.DOCKER_STOP_TIMEOUT_SECONDS)
    ]
    assert warnings == [("Container Stop", "Failed to stop container.")]
    assert any("container stop timed out" in message for message in logs)
