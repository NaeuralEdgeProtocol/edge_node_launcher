import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ratio1_sdk_is_declared_in_runtime_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "ratio1>=3.5.30" in dependencies
    assert "ratio1>=3.5.30" in requirements


def test_windows_qt_runtime_pin_is_declared_for_reproducible_uv_sync():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "PyQt5-Qt5==5.15.2; sys_platform == 'win32'" in dependencies
    assert 'PyQt5-Qt5==5.15.2; sys_platform == "win32"' in requirements

    if sys.platform == "win32":
        assert any("PyQt5-Qt5==5.15.2" in dependency for dependency in dependencies)
