#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: /home/ywatanabe/proj/scitex-app/tests/examples/test_01_basic_file_operations.py

"""Smoke test for examples/01_basic_file_operations.py.

Per scitex-dev audit-project PS303: every example must have a matching
test under tests/examples/. Validates the example parses cleanly. The
full end-to-end execution is covered by tests/scitex_app/test_examples.py.
"""

import subprocess
import sys
from pathlib import Path

EXAMPLE = (
    Path(__file__).resolve().parents[2] / "examples" / "01_basic_file_operations.py"
)


def test_example_exists():
    assert EXAMPLE.exists(), f"missing example: {EXAMPLE}"


def test_compiles():
    subprocess.run(
        [sys.executable, "-m", "py_compile", str(EXAMPLE)],
        check=True,
    )
