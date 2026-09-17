"""Env-gated strict-skip hook for the access conformance proof.

Active only when ``SCITEX_ACCESS_STRICT=1`` (set by the ci.yml
``access-conformance`` job). In that mode ANY skipped test in this directory
is reported as a failure, so the authoritative proof — which must run every
case against the real core — cannot pass by skipping. The normal pinned
pytest-matrix run does NOT set the env, so its legitimate skips (core
absent / no DB) remain skips, not failures.
"""

from __future__ import annotations

import os

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Upgrade a skip to a failure when the strict flag is set."""
    if os.environ.get("SCITEX_ACCESS_STRICT") != "1":
        yield
        return
    outcome = yield
    report = outcome.get_result()
    if report is not None and report.skipped:
        report.outcome = "failed"
        report.longrepr = (
            "SCITEX_ACCESS_STRICT: this case SKIPPED, but the conformance "
            "proof must run every case non-skipped."
        )
