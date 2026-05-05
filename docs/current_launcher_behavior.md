# Current Launcher Behavior

Last checked: 2026-05-05

## Purpose

Edge Node Launcher is a PyQt desktop control surface for running and managing the Ratio1 edge node Docker container. It is responsible for local operator workflows around Docker availability, container lifecycle, node status, node configuration, logs, allowed addresses, updates, and basic resource visibility.

The launcher is not the edge node runtime itself. The production runtime is the `ratio1/edge_node:mainnet` container image, and the launcher controls it mostly through Docker commands and `docker exec` calls into command scripts provided by the edge node image.

## Runtime Shape

- `main.py` is the source entrypoint for local development. It creates `QApplication`, applies the app icon and Windows AppUserModelID, instantiates `EdgeNodeLauncher`, shows it, and starts the Qt event loop.
- `launcher.py` is the packaged wrapper. It configures file logging, hides the console window on Windows, patches subprocess behavior, and then starts the same PyQt application.
- Local source runs can override the edge-node image with `--edge-image` or `R1_EDGE_NODE_IMAGE`, for example `ratio1/edge_node:devnet`. Packaged production runs ignore non-mainnet overrides and use mainnet only.
- Mainnet Docker resources keep the existing names (`r1node`, `r1vol`, with numeric suffixes for additional nodes). Devnet and testnet source runs use separate prefixes (`r1devnode`/`r1devvol`, `r1testnode`/`r1testvol`) and the launcher filters saved nodes to the active image network before creating or selecting containers.
- `app_forms/frm_main.py` contains the main `EdgeNodeLauncher` widget. It currently owns a large amount of UI construction, app state, Docker flow coordination, refresh timers, dialogs, logs, and node-status behavior.
- `requirements.txt` currently lists direct runtime dependencies without pinned versions: `PyQt5`, `matplotlib`, `pyqtgraph`, `requests`, `pyyaml`, and `psutil`.

## Docker And Edge Node Integration

- `utils/docker_commands.py` is the primary Docker command layer used by the UI.
- The default production image is `ratio1/edge_node:mainnet`; local source and E2E runs resolve the active image through `utils/edge_image_config.py`. Destructive E2E defaults to `ratio1/edge_node:devnet` so test containers do not look like mainnet resources.
- Container launch builds a `docker run` command with detached mode, privileged mode, restart policy, optional GPU support, optional ARM platform override, cgroup settings on non-macOS platforms, and an optional named volume mounted to the edge-node local cache path.
- Node information is fetched through container exec commands such as `get_node_info`, `get_node_history`, `get_allowed`, `get_startup_config`, `get_config_app`, `reset_address`, and `change_alias`.
- Docker work is executed through Qt threads to avoid blocking the UI.
- Destructive E2E supports `--devnet-real-data`, which selects `ratio1/edge_node:devnet` and disables offline startup-config injection. It uses dedicated `r1devnodee2e*` containers and `r1devvole2e*` volumes. Use `--no-cleanup` only for manual real-data/license sessions where the dedicated E2E volume should remain available afterward.
- Environment-scoped naming is implemented in `utils/edge_image_config.py` and `utils/docker_utils.py`; UI flows in `app_forms/frm_main.py` use those helpers instead of hard-coded dev/test names.

## Local State

- `utils/config_manager.py` stores launcher configuration under the user home directory using the `CONFIG_DIR` constant from `utils/const.py`.
- Container metadata includes container name, volume, timestamps, node address, ETH address, and alias.
- `utils/docker_commands.ContainerRegistry` also stores container metadata in `~/.edge_node/containers.json`, which is a separate registry path from `ConfigManager`.
- This split storage model should be reviewed during refactoring because it increases the chance of inconsistent state.

## UI Shape

- The current UI is implemented directly in PyQt widgets.
- Most of the real app behavior still flows through `EdgeNodeLauncher` in `app_forms/frm_main.py`.
- `widgets/app_widgets/` contains extracted widgets from an earlier refactor attempt, but `REFACTORING_SUMMARY.md` references `main_simplified.py`, which is not present in the repo. Treat that summary as stale until proven otherwise.
- The main UX problems to address are visual hierarchy, crowded controls, unclear status/error states, hard-to-follow Docker/container flows, and high coupling between UI and runtime behavior.

## Packaging And Updates

- Windows packaging uses PyInstaller through `build_scripts/win32_build.bat`.
- Linux packaging uses `build_scripts/unix_build.sh`.
- MSI packaging assets are present under `wix/` and `build_scripts/build_msi.bat`.
- `utils/updater.py` checks GitHub releases for platform-specific assets and can replace the packaged executable.

## Baseline Verification

Environment setup:

- `uv` is available.
- A repo-local `.venv` was created with CPython 3.11.15.
- Runtime dependencies and test dependencies were installed into `.venv`.

Checks:

- Dependency import check passed with `.venv\Scripts\python.exe`.
- Initial `uv run` checks did not use the repo-local `.venv`, so explicit `.venv\Scripts\python.exe` commands are used for baseline testing.
- Baseline pytest command initially found no tests.
- A first smoke/regression test suite was added under `tests/`.
- Current baseline test result: 20 passing tests.
- Window startup now logs screen, available area, client geometry, frame geometry, and maximized/full-screen state so window position and size issues can be diagnosed from runtime logs.
- Docker CLI is installed.
- Docker Desktop was started successfully and `docker info` reported server version `29.4.1`.
- The app was launched with `.venv\Scripts\python.exe main.py`; it stayed running for 10 seconds and did not crash during startup. The process did not close via `CloseMainWindow()` from the shell smoke command and was force-stopped to avoid leaving it running.

## Refactor Implications

- Start by preserving behavior and adding tests around the current command/config boundaries.
- Avoid moving UI and Docker behavior at the same time unless the test coverage for that workflow is already in place.
- Separate long-running Docker operations, state persistence, and presentation logic before making larger UI changes.
- Decide whether to keep PyQt5 or move to PySide6/Qt6 only after Python 3.14 feasibility and packaging checks are complete.
