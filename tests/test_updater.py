from pathlib import Path

import utils.updater as updater


class DummyReleaseResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "tag_name": "v1.2.3",
            "assets": [
                {"name": "EdgeNodeLauncher-Windows.exe", "browser_download_url": "https://example.test/win.exe"},
                {"name": "EdgeNodeLauncher-Ubuntu.AppImage", "browser_download_url": "https://example.test/linux.AppImage"},
                {"name": "EdgeNodeLauncher-OSX.zip", "browser_download_url": "https://example.test/mac.zip"},
                {"name": "checksums.txt", "browser_download_url": "https://example.test/checksums.txt"},
            ],
        }


def test_get_latest_release_version_uses_timeout_and_filters_assets(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return DummyReleaseResponse()

    monkeypatch.setattr(updater.requests, "get", fake_get)

    latest_version, download_urls = updater._UpdaterMixin.get_latest_release_version()

    assert latest_version == "v1.2.3"
    assert download_urls == {
        "Windows": "https://example.test/win.exe",
        "Linux": "https://example.test/linux.AppImage",
        "Darwin": "https://example.test/mac.zip",
    }
    assert calls == [
        (updater.GITHUB_API_URL, {"timeout": updater.UPDATE_CHECK_TIMEOUT_SECONDS})
    ]


def test_update_check_thread_emits_release_result(qtbot):
    results = []
    errors = []
    thread = updater.UpdateCheckThread(lambda: ("v9.9.9", {"Windows": "https://example.test/app.exe"}))

    thread.update_check_finished.connect(lambda version, urls: results.append((version, urls)))
    thread.update_check_failed.connect(errors.append)

    thread.run()

    assert results == [("v9.9.9", {"Windows": "https://example.test/app.exe"})]
    assert errors == []


def test_update_check_thread_emits_fetch_errors(qtbot):
    results = []
    errors = []

    def fail_fetch():
        raise RuntimeError("network unavailable")

    thread = updater.UpdateCheckThread(fail_fetch)
    thread.update_check_finished.connect(lambda version, urls: results.append((version, urls)))
    thread.update_check_failed.connect(errors.append)

    thread.run()

    assert results == []
    assert errors == ["network unavailable"]


def test_updater_shutdown_path_does_not_pump_events_or_sleep():
    source = Path(updater.__file__).read_text(encoding="utf-8")

    assert ".processEvents(" not in source
    assert "time.sleep" not in source
