#!/usr/bin/env python3
"""Make this example runnable from anywhere, not only from inside its own dir.

TWO insertions, for two different imports:

  * this example's own root, so ``project_context`` (its Django app and its
    ``ROOT_URLCONF``) is importable by name;
  * the CHECKOUT's ``src``, so ``scitex_app`` resolves to the tree this example
    ships with. Without that, an editable install wins and the example is
    exercised against whatever happens to be installed — the same wrong-tree
    failure the shell-layout guard documents for ``scitex_ui.__file__``: the
    test would be reading someone else's package and reporting on this one.

pytest loads every conftest.py between its rootdir and the test file, so the
insertions here make the example self-sufficient: CI, a developer at the repo
root, and a developer inside this folder all get the same result without anyone
exporting PYTHONPATH.

NOTE ON CI: ``testpaths`` is ``["tests"]``, so an example's own suite is not
collected — true of this example and of ``hello_world_app`` alike. Run it
explicitly:

    pytest examples/project_context_app/tests/
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLE_ROOT = Path(__file__).resolve().parent
_REPO_SRC = _EXAMPLE_ROOT.parents[1] / "src"

for _path in (str(_REPO_SRC), str(_EXAMPLE_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# EOF
