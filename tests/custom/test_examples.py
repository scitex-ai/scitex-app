"""Smoke tests for the canonical example.

Per scitex-dev audit-project §5 (PS501), numbered examples
(`NN_*.py`) use `@stx.session` and are covered by their per-example
tests under `tests/examples/`. The cross-cutting smoke contract
here is restricted to `examples/quickstart.py`, which must run
end-to-end without external services. Mirrors the canonical pattern
used by scitex-audio / scitex-dataset / figrecipe.
"""

import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
QUICKSTART = EXAMPLES_DIR / "quickstart.py"


def test_quickstart_smoke(tmp_path):
    """Quickstart example must import and introspect cleanly (offline-safe)."""
    assert QUICKSTART.exists(), f"missing example: {QUICKSTART}"
    result = subprocess.run(
        [sys.executable, str(QUICKSTART)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"{QUICKSTART.name} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
