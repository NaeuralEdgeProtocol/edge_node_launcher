from utils import docker_utils
from utils.edge_image_config import configure_edge_node_image


def test_main_form_uses_bounded_container_name_generator():
    from app_forms import frm_main

    assert frm_main.generate_container_name is docker_utils.generate_container_name


def test_main_form_uses_canonical_volume_name_helper():
    from app_forms import frm_main

    assert frm_main.get_volume_name is docker_utils.get_volume_name


def test_mainnet_volume_names_stay_unchanged():
    assert docker_utils.get_volume_name("r1node") == "r1vol"
    assert docker_utils.get_volume_name("r1node2") == "r1vol2"
    assert docker_utils.get_volume_name("edge_node_container") == "edge_node_volume"


def test_devnet_and_testnet_volume_names_use_separate_prefixes():
    assert docker_utils.get_volume_name("r1devnode") == "r1devvol"
    assert docker_utils.get_volume_name("r1devnode2") == "r1devvol2"
    assert docker_utils.get_volume_name("r1testnode") == "r1testvol"
    assert docker_utils.get_volume_name("r1testnode3") == "r1testvol3"


def test_active_devnet_container_name_generation_uses_dev_prefix(monkeypatch, tmp_path):
    configure_edge_node_image(cli_image="devnet", environ={}, production_mode=False)
    calls = []

    class FakePath:
        @staticmethod
        def home():
            return tmp_path

    class FakeResult:
        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] == "name=r1devnode":
            return FakeResult("r1devnode\nr1devnode2\n")
        return FakeResult("")

    monkeypatch.setattr(docker_utils, "Path", FakePath)
    monkeypatch.setattr(docker_utils.subprocess, "run", fake_run)

    assert docker_utils.generate_container_name() == "r1devnode3"
    assert calls[0][-1] == "name=r1devnode"


def test_container_environment_filter_keeps_mainnet_and_devnet_separate():
    mainnet = configure_edge_node_image(cli_image="mainnet", environ={}, production_mode=False)
    devnet = configure_edge_node_image(cli_image="devnet", environ={}, production_mode=False)

    assert docker_utils.is_container_name_for_config("r1node", mainnet)
    assert docker_utils.is_container_name_for_config("r1node2", mainnet)
    assert not docker_utils.is_container_name_for_config("r1devnode", mainnet)
    assert docker_utils.is_container_name_for_config("r1devnode", devnet)
    assert docker_utils.is_container_name_for_config("r1devnode2", devnet)
    assert not docker_utils.is_container_name_for_config("r1node", devnet)


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
