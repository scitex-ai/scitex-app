#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: tests/conftest.py

"""Pytest configuration for scitex-app."""

import sys
from pathlib import Path

# Ensure tests import from local source (src/)
_REPO_ROOT = Path(__file__).parent.parent
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) in sys.path:
    sys.path.remove(str(_SRC_PATH))
sys.path.insert(0, str(_SRC_PATH))

# Clear cached imports to force reload
_modules_to_clear = [k for k in sys.modules.keys() if k.startswith("scitex_app")]
for _mod in _modules_to_clear:
    del sys.modules[_mod]
