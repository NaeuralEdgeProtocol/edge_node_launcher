import subprocess

from utils import subprocess_utils


def test_terminate_process_by_pid_uses_bounded_hidden_windows_taskkill(monkeypatch):
    calls = []

    def fake_run_process_no_window(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(subprocess_utils.os, "name", "nt")
    monkeypatch.setattr(
        subprocess_utils,
        "run_process_no_window",
        fake_run_process_no_window,
    )

    assert subprocess_utils.terminate_process_by_pid(1234)
    assert calls == [
        (
            ["taskkill", "/F", "/PID", "1234"],
            {
                "capture_output": True,
                "timeout": subprocess_utils.FORCE_EXIT_TIMEOUT_SECONDS,
            },
        )
    ]


def test_terminate_process_by_pid_reports_windows_timeout(monkeypatch):
    def fake_run_process_no_window(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess_utils.os, "name", "nt")
    monkeypatch.setattr(
        subprocess_utils,
        "run_process_no_window",
        fake_run_process_no_window,
    )

    assert not subprocess_utils.terminate_process_by_pid(1234)


def test_terminate_process_by_pid_uses_sigterm_on_posix(monkeypatch):
    calls = []

    monkeypatch.setattr(subprocess_utils.os, "name", "posix")
    monkeypatch.setattr(subprocess_utils.os, "kill", lambda pid, sig: calls.append((pid, sig)))

    assert subprocess_utils.terminate_process_by_pid(1234)

    import signal

    assert calls == [(1234, signal.SIGTERM)]
