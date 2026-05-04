import subprocess

from utils import ssh_service


class FakeProcess:
    def __init__(self, stdout="out", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.calls = []
        self.killed = False

    def communicate(self, input=None, timeout=None):
        self.calls.append({"input": input, "timeout": timeout})
        return self.stdout, self.stderr

    def kill(self):
        self.killed = True


def test_execute_command_uses_timeout_and_hidden_windows_process(monkeypatch):
    popen_calls = []
    process = FakeProcess()

    def fake_popen(command, **kwargs):
        popen_calls.append((command, kwargs))
        return process

    monkeypatch.setattr(ssh_service.os, "name", "nt")
    monkeypatch.setattr(
        ssh_service.subprocess,
        "CREATE_NO_WINDOW",
        ssh_service.WINDOWS_CREATE_NO_WINDOW,
        raising=False,
    )
    monkeypatch.setattr(ssh_service.subprocess, "Popen", fake_popen)

    service = ssh_service.SSHService()
    service.configure(ssh_service.SSHConfig(host="192.0.2.10", user="ratio"))

    assert service.execute_command(["docker", "ps"], timeout=7) == ("out", "", 0)
    assert popen_calls == [
        (
            ["ssh", "ratio@192.0.2.10", "docker", "ps"],
            {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "universal_newlines": True,
                "creationflags": ssh_service.WINDOWS_CREATE_NO_WINDOW,
            },
        )
    ]
    assert process.calls == [{"input": None, "timeout": 7}]


def test_execute_command_sudo_sends_password_with_timeout(monkeypatch):
    popen_calls = []
    process = FakeProcess()

    def fake_popen(command, **kwargs):
        popen_calls.append((command, kwargs))
        return process

    monkeypatch.setattr(ssh_service.os, "name", "posix")
    monkeypatch.setattr(ssh_service.subprocess, "Popen", fake_popen)

    service = ssh_service.SSHService()
    service.configure(
        ssh_service.SSHConfig(host="192.0.2.10", user="ratio", password="secret")
    )

    assert service.execute_command(["systemctl", "restart", "edge"], sudo=True) == ("out", "", 0)
    assert popen_calls == [
        (
            ["ssh", "ratio@192.0.2.10", "sudo", "-S", "systemctl", "restart", "edge"],
            {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "universal_newlines": True,
                "stdin": subprocess.PIPE,
            },
        )
    ]
    assert process.calls == [{"input": "secret\n", "timeout": ssh_service.SSH_COMMAND_TIMEOUT}]


def test_execute_command_timeout_kills_process(monkeypatch):
    class TimeoutProcess(FakeProcess):
        def communicate(self, input=None, timeout=None):
            self.calls.append({"input": input, "timeout": timeout})
            if not self.killed:
                raise subprocess.TimeoutExpired(["ssh"], timeout)
            return "late out", "late err"

    process = TimeoutProcess()
    monkeypatch.setattr(ssh_service.os, "name", "posix")
    monkeypatch.setattr(ssh_service.subprocess, "Popen", lambda *args, **kwargs: process)

    service = ssh_service.SSHService()
    service.configure(ssh_service.SSHConfig(host="192.0.2.10", user="ratio"))

    stdout, stderr, return_code = service.execute_command(["docker", "ps"], timeout=3)

    assert stdout == "late out"
    assert "late err" in stderr
    assert "SSH command timed out after 3 seconds" in stderr
    assert return_code == 124
    assert process.killed
