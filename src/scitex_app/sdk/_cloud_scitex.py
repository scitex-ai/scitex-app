#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: scitex_app/sdk/_cloud_scitex.py

"""SciTeX Bridge client — proxy calls to the scitex Python package.

REST endpoint:
  POST /platform/api/scitex/<module>/<function>/
"""

from __future__ import annotations

from typing import Any, Optional

from ._client import get_client


def call(
    module: str,
    function: str,
    *,
    args: Optional[list] = None,
    kwargs: Optional[dict] = None,
    project_id: Optional[str] = None,
) -> dict:
    """Call a scitex package function via the Platform Bridge.

    Allowed modules: io, plt, stats, writer, scholar, session.
    """
    client = get_client()
    data: dict[str, Any] = {}
    if args:
        data["args"] = args
    if kwargs:
        data["kwargs"] = kwargs
    if project_id:
        data["project_id"] = project_id
    return client.request(
        "POST", f"/platform/api/scitex/{module}/{function}/", data=data
    )


# EOF
