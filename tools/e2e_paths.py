import json
from pathlib import Path


def _resolved_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def prepare_evidence_paths(args):
    if args.output:
        output_path = _resolved_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output = str(output_path)

    if args.screenshot_dir:
        screenshot_dir = _resolved_path(args.screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        args.screenshot_dir = str(screenshot_dir)

    return args


def write_json_log(log, output_path):
    if not output_path:
        return

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")
