"""SciTeX App Maker — scaffold, validate, and publish apps."""

from __future__ import annotations

from ._scaffold import init_app
from ._validate import (
    validate,
    validate_prefix_safety,
    validate_with_warnings,
)

#: `validate_prefix_safety` is re-exported because a CONSUMER needed it and
#: could not reach it. scitex-hub scanned their fleet before this rule was
#: armed, imported it from `scitex_app.appmaker` as the obvious home, hit an
#: ImportError, and was one step from reporting the symbol missing. The
#: function lived only at `scitex_app.appmaker._validate` — a private path
#: for a check we ask other packages to run against their own code.
__all__ = [
    "init_app",
    "validate",
    "validate_prefix_safety",
    "validate_with_warnings",
]

# EOF
