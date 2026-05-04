from utils import docker_utils


def test_generate_container_name_uses_bounded_hidden_docker_queries(monkeypatch, tmp_path):
    calls = []
    create_no_window = 0x08000000

    class FakePath:
        @staticmethod
        def home():
            return tmp_path

    class FakeResult:
        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[-1] == "name=r1node":
            return FakeResult("r1node\nr1node2\n")
        return FakeResult("")

    monkeypatch.setattr(docker_utils, "Path", FakePath)
    monkeypatch.setattr(docker_utils.os, "name", "nt")
    monkeypatch.setattr(
        docker_utils.subprocess,
        "CREATE_NO_WINDOW",
        create_no_window,
        raising=False,
    )
    monkeypatch.setattr(docker_utils.subprocess, "run", fake_run)

    assert docker_utils.generate_container_name() == "r1node3"
    assert calls == [
        (
            ["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", "name=r1node"],
            {
                "capture_output": True,
                "text": True,
                "timeout": docker_utils.DOCKER_NAME_CHECK_TIMEOUT,
                "creationflags": create_no_window,
            },
        ),
        (
            ["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", "name=r1node3"],
            {
                "capture_output": True,
                "text": True,
                "timeout": docker_utils.DOCKER_NAME_CHECK_TIMEOUT,
                "creationflags": create_no_window,
            },
        ),
    ]


def test_generate_container_name_falls_back_when_docker_query_times_out(monkeypatch, tmp_path):
    class FakePath:
        @staticmethod
        def home():
            return tmp_path

    def fake_run(command, **kwargs):
        raise docker_utils.subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(docker_utils, "Path", FakePath)
    monkeypatch.setattr(docker_utils.subprocess, "run", fake_run)

    assert docker_utils.generate_container_name() == "r1node"
