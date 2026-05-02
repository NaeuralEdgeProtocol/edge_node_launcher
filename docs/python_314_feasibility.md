# Python 3.14 Feasibility

Last checked: 2026-05-03

## Result

Python 3.14 is feasible for the current launcher baseline on Windows.

Validated runtime:

- CPython 3.14.4 from `uv`
- PyQt5 5.15.11
- Qt runtime 5.15.2
- pytest 9.0.3
- pytest-qt 4.5.0
- PyInstaller 6.20.0

## Checks Run

Environment:

- Created an external Python 3.14 virtual environment with `uv`.
- Installed `requirements.txt`, `pytest`, `pytest-qt`, and `pyinstaller`.

Validation:

- Dependency imports passed.
- Baseline test suite passed: 11 tests.
- Launcher startup smoke passed: the app stayed running for 10 seconds.
- PyInstaller one-file packaging smoke passed and produced `EdgeNodeLauncherSmoke.exe`.

## Notes

- Packaging smoke was run outside the repo to avoid committing generated build artifacts.
- The first PyInstaller smoke failed because `--specpath` was outside the repo and a relative `--add-data` path resolved from the spec directory. Rerunning with absolute asset paths passed.
- PyInstaller emitted a warning that `pyqtgraph.opengl` could not be collected because `OpenGL` is not installed. The current app baseline does not depend on that optional OpenGL module.
- The shell startup smoke could not close the GUI via `CloseMainWindow()` and force-stopped the process after confirming it stayed running.

## Tracked Runtime Updates

- `pyproject.toml` now declares `requires-python = ">=3.14"`.
- GitHub Actions build workflows now use Python 3.14.4 with `actions/setup-python@v5`.
- README source setup instructions now use `uv` and Python 3.14.
