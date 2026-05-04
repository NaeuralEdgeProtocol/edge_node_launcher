import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

ACTION_SOURCE_FILES = [
    Path("app_forms/frm_main.py"),
    Path("ui/ProgressDialog.py"),
    Path("widgets/HostSelector.py"),
    Path("widgets/dialogs/AuthorizedAddressedDialog.py"),
    Path("widgets/dialogs/AddNodeDialog.py"),
    Path("widgets/dialogs/DockerCheckDialog.py"),
    Path("widgets/dialogs/RenameNodeDialog.py"),
    Path("widgets/app_widgets/config_editor.py"),
    Path("widgets/app_widgets/activity_log.py"),
    Path("widgets/app_widgets/container_list.py"),
    Path("widgets/app_widgets/log_console.py"),
    Path("widgets/app_widgets/metrics_widget.py"),
    Path("widgets/app_widgets/node_info.py"),
    Path("widgets/app_widgets/sidebar_status_cards.py"),
]

ACTION_IDS = [
    "addNodeButton",
    "startNodeButton",
    "downloadDockerButton",
    "openDappButton",
    "openExplorerButton",
    "refreshNodeInfoButton",
    "copyAddrButton",
    "copyEthButton",
    "renameNodeButton",
    "themeToggleButton",
    "forceDebugCheckbox",
    "renameNodeSaveButton",
    "renameNodeCancelButton",
    "createNodeConfirmButton",
    "createNodeCancelButton",
    "authorizedAddressCopyAddressButton",
    "authorizedAddressCopyAliasButton",
    "authorizedAddressDeleteButton",
    "authorizedAddressAddButton",
    "authorizedAddressSaveButton",
    "authorizedAddressCloseButton",
    "dockerCheckDownloadButton",
    "dockerCheckRetryButton",
    "dockerCheckQuitButton",
    "imagePullCancelButton",
    "configEditorSaveButton",
    "configEditorCancelButton",
    "hostSelectorModeCheckbox",
    "hostSelectorRefreshButton",
    "configEditorEditButton",
    "containerListToggleButton",
    "containerListAddNodeButton",
    "logConsoleClearButton",
    "metricsRefreshButton",
    "nodeInfoCopyAddressButton",
    "nodeInfoCopyEthButton",
    "nodeInfoRefreshButton",
    "activityLogCopyButton",
    "activityLogClearButton",
]

CONTROL_PATTERN = re.compile(
    r"^\s*(?P<target>(?:self\.)?[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?:QPushButton|QToolButton|QCheckBox|QAction)\("
)

DIALOG_BUTTON_BOX_PATTERN = re.compile(
    r"^\s*(?P<target>(?:self\.)?[A-Za-z_][A-Za-z0-9_]*)\s*=\s*QDialogButtonBox\("
)


def _read(relative_path: Path) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _source_text() -> str:
    return "\n".join(_read(path) for path in ACTION_SOURCE_FILES)


def _has_action_id_source(source: str, action_id: str) -> bool:
    if f'.setObjectName("{action_id}")' in source:
        return True

    for helper_name in (
        "_create_sidebar_action_button",
        "_create_action_button",
        "_create_copy_button",
    ):
        helper_pattern = re.compile(
            rf"{helper_name}\(\s*(?:[^\n]*\n){{0,6}}\s*"
            rf'"{re.escape(action_id)}"',
            re.MULTILINE,
        )
        if helper_pattern.search(source):
            return True

    return False


def test_ui_action_ids_are_unique():
    assert len(ACTION_IDS) == len(set(ACTION_IDS))


def test_ui_action_ids_exist_in_source():
    source = _source_text()

    missing = [
        action_id
        for action_id in ACTION_IDS
        if not _has_action_id_source(source, action_id)
    ]

    assert missing == []


def test_ui_action_ids_are_documented():
    action_matrix = _read(Path("docs/ui_action_matrix.md"))

    missing = [
        action_id
        for action_id in ACTION_IDS
        if f"`{action_id}`" not in action_matrix
    ]

    assert missing == []


def test_button_like_controls_set_object_name_near_construction():
    missing = []

    for relative_path in ACTION_SOURCE_FILES:
        lines = _read(relative_path).splitlines()
        for index, line in enumerate(lines):
            match = CONTROL_PATTERN.match(line)
            if not match:
                continue

            target = match.group("target")
            nearby_source = "\n".join(lines[index : index + 8])
            if f"{target}.setObjectName(" not in nearby_source:
                missing.append(f"{relative_path}:{index + 1} {target}")

    assert missing == []


def test_dialog_button_boxes_name_standard_buttons():
    missing = []

    for relative_path in ACTION_SOURCE_FILES:
        lines = _read(relative_path).splitlines()
        for index, line in enumerate(lines):
            match = DIALOG_BUTTON_BOX_PATTERN.match(line)
            if not match:
                continue

            target = match.group("target")
            nearby_source = "\n".join(lines[index : index + 8])
            if f"{target}.setObjectName(" not in nearby_source:
                missing.append(f"{relative_path}:{index + 1} {target} box")
            if (
                f"{target}.button(" not in nearby_source
                or ".setObjectName(" not in nearby_source
            ):
                missing.append(f"{relative_path}:{index + 1} {target} standard buttons")

    assert missing == []
