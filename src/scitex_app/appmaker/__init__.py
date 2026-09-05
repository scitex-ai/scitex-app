"""SciTeX App Maker — scaffold, validate, and publish apps."""

from __future__ import annotations

from ._scaffold import init_app
from ._validate import (
    validate,
    validate_prefix_safety,
    validate_with_warnings,
)
from ._validate._prefix import (
    PREFIX_SCAN_SUFFIXES,
    PREFIX_SKIP_DIRS,
    scannable_files,
)

#: `validate_prefix_safety` is re-exported because a CONSUMER needed it and
#: could not reach it. scitex-hub scanned their fleet before this rule was
#: armed, imported it from `scitex_app.appmaker` as the obvious home, hit an
#: ImportError, and was one step from reporting the symbol missing. The
#: function lived only at `scitex_app.appmaker._validate` — a private path
#: for a check we ask other packages to run against their own code.
#: `scannable_files` and the two walk constants are public because we ASK other
#: packages to report files-scanned beside their findings, and scitex-hub found
#: that everything needed to produce that number was behind an underscore. They
#: imported from `_validate` to comply. A request we make of consumers cannot
#: depend on a path we tell them not to touch — the same defect as
#: `validate_prefix_safety` itself, found the same day by the same peer.
__all__ = [
    "PREFIX_SCAN_SUFFIXES",
    "PREFIX_SKIP_DIRS",
    "init_app",
    "scannable_files",
    "validate",
    "validate_prefix_safety",
    "validate_with_warnings",
]

# EOF
