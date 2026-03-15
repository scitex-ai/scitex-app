#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SSE (Server-Sent Events) utilities for chat streaming."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterator


def sse_format(event: Dict[str, Any]) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(event)}\n\n"


def sse_done() -> str:
    """Return the SSE termination marker."""
    return "data: [DONE]\n\n"


def sse_keepalive() -> str:
    """Return an SSE keepalive comment."""
    return ": keepalive\n\n"


def sse_keepalive_wrap(
    events: Iterator[Dict[str, Any]],
    interval_s: float = 15.0,
) -> Iterator[str]:
    """Wrap an event iterator with SSE formatting and keepalives.

    Yields SSE-formatted strings. Inserts keepalive comments
    if no event has been yielded for ``interval_s`` seconds,
    preventing proxy/browser timeouts.

    Parameters
    ----------
    events : Iterator[dict]
        Raw event dicts from a ChatBackend.stream().
    interval_s : float
        Keepalive interval in seconds.

    Yields
    ------
    str
        SSE-formatted lines ready for StreamingHttpResponse.
    """
    last_event = time.monotonic()

    for event in events:
        now = time.monotonic()
        if now - last_event > interval_s:
            yield sse_keepalive()

        yield sse_format(event)
        last_event = now

    yield sse_done()
