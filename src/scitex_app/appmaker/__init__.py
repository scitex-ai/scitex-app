"""SciTeX App Maker — scaffold, validate, and publish apps."""

from __future__ import annotations

from ._scaffold import init_app
from ._validate import validate

__all__ = [
    "init_app",
    "validate",
]

# EOF
