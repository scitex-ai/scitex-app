"""Make this example runnable from anywhere, not only from inside its own dir.

`tests/test_mounts_anywhere.py` sets DJANGO_SETTINGS_MODULE to `project.settings`,
which Django imports by name — so the example's root has to be on `sys.path`.
Running `pytest` from inside this directory happens to satisfy that; running it
from the repository root does not, and the failure is an ImportError about
`project` that says nothing about the working directory.

pytest loads every conftest.py between its rootdir and the test file, so putting
the insertion here makes the example self-sufficient: CI, a developer at the
repo root, and a developer inside this folder all get the same result without
anyone remembering to export PYTHONPATH.

WHY THIS EXISTS AT ALL. These tests have never run in CI — `testpaths` is
`["tests"]` and this example lives under `examples/`, so nothing collected them.
That matters more than a normal coverage gap: this example is the REFERENCE
IMPLEMENTATION of the stx-mount contract, the only place the "one build serves
correctly at two different mounts" claim is executable, and the thing app
authors are pointed at. If an SDK change broke it, CI stayed green and the first
person to find out would be someone copying it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLE_ROOT = str(Path(__file__).resolve().parent)

if _EXAMPLE_ROOT not in sys.path:
    sys.path.insert(0, _EXAMPLE_ROOT)

# EOF
