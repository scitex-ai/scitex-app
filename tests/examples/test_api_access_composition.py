#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: /home/ywatanabe/proj/scitex-app/tests/examples/test_api_access_composition.py

"""Smoke test for examples/api_access_composition.py.

Per scitex-dev audit-project PS303: every example must have a matching
test under tests/examples/. Validates the example parses cleanly. The
example's behaviour itself is covered end-to-end by
``tests/scitex_app/api_access/`` (the composition's conformance proof), so this
file stays a parse check: the example needs the optional access core to RUN, and
a smoke test that skipped wherever that core is absent would prove nothing.
"""

import subprocess
import sys
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "api_access_composition.py"


def test_example_exists_example_exists():
    # Arrange
    # Act
    # Assert
    assert EXAMPLE.exists(), f"missing example: {EXAMPLE}"


def test_compiles_calls_run():
    # Arrange
    # Act
    _r = subprocess.run(
        [sys.executable, "-m", "py_compile", str(EXAMPLE)],
        check=True,
    )
    # Assert
    assert _r.returncode == 0
