from pathlib import Path

from utils import ansible_hosts


def test_ansible_hosts_manager_loads_hosts_and_builds_ssh_command(tmp_path, monkeypatch):
    hosts_file = (
        tmp_path
        / ".ansible"
        / "collections"
        / "ansible_collections"
        / "vitalii_t12"
        / "multi_node_launcher"
        / "hosts.yml"
    )
    hosts_file.parent.mkdir(parents=True)
    hosts_file.write_text(
        """
all:
  children:
    gpu_nodes:
      hosts:
        edge-a:
          ansible_host: 192.0.2.10
          ansible_user: ratio
          ansible_ssh_private_key_file: ~/.ssh/edge
          ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
""",
        encoding="utf-8",
    )

    def fake_expanduser(path):
        return str(tmp_path / path[2:].replace("/", "\\")) if path.startswith("~/") else path

    monkeypatch.setattr(ansible_hosts.os.path, "expanduser", fake_expanduser)

    manager = ansible_hosts.AnsibleHostsManager()

    assert manager.get_host_list() == ["edge-a"]
    assert manager.get_host_config("edge-a")["ansible_host"] == "192.0.2.10"
    assert manager.get_ssh_command_prefix("edge-a") == [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-i",
        str(tmp_path / ".ssh" / "edge"),
        "ratio@192.0.2.10",
    ]


def test_ansible_hosts_manager_returns_none_for_unknown_host(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ansible_hosts.os.path,
        "expanduser",
        lambda path: str(tmp_path / "missing-hosts.yml") if path.startswith("~") else path,
    )

    manager = ansible_hosts.AnsibleHostsManager()

    assert manager.get_host_list() == []
    assert manager.get_ssh_command_prefix("missing") is None
