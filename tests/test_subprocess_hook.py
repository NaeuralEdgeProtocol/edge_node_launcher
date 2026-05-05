import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_subprocess_hook_preserves_asyncio_and_sdk_imports():
    script = """
import subprocess
import utils.subprocess_hook

assert isinstance(subprocess.Popen, type), type(subprocess.Popen)

class ChildPopen(subprocess.Popen):
    pass

import asyncio
from services.sdk_identity_service import _load_sdk_session_class

print(asyncio.__file__)
print(_load_sdk_session_class().__name__)
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "MqttSession" in result.stdout
