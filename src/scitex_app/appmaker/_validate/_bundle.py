"""Total distribution size.

PORTED from `scitex_app.validator.AppValidator.validate_bundle_size`, which the
shipped docs listed as part of the pipeline and which the CLI never called.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_MAX_BUNDLE_SIZE = 50 * 1024 * 1024  # 50 MB

# node_modules is a DEV dependency tree, not part of what ships, so counting it
# would measure the developer's checkout rather than the app. `dist` and
# `assets` ARE counted: built output is precisely what a user downloads.
BUNDLE_SKIP_DIRS = {"node_modules"}


def validate_bundle_size(
    app_dir: str | Path, max_bundle_size: int = DEFAULT_MAX_BUNDLE_SIZE
) -> list[str]:
    """Check the app's total file size is under the limit.

    NOT ARMED — `validate()` skips this unless `check_bundle_size=True`.

    Unlike the JS pattern scan this has no false-positive class: it is a
    measurement against a threshold, and it fails only if the app really is
    larger than the limit. It ships unarmed anyway, because whether 50 MB is the
    right threshold for THIS fleet is a question nobody has answered with a
    number — three apps ship built bundles and none of their sizes has been
    measured. Arming a limit before knowing what it would reject is how a
    threshold gets discovered by breaking someone's build.
    """
    root = Path(app_dir)
    total_size = 0

    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if BUNDLE_SKIP_DIRS & set(f.relative_to(root).parts):
            continue
        try:
            total_size += f.stat().st_size
        except OSError:
            continue

    if total_size > max_bundle_size:
        mb = total_size / (1024 * 1024)
        limit_mb = max_bundle_size / (1024 * 1024)
        return [f"Bundle size {mb:.1f}MB exceeds limit of {limit_mb:.1f}MB"]
    return []


# EOF
