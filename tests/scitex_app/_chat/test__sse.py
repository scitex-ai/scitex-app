#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scitex_app/_chat/_sse.py — SSE formatting + keepalive wrapping."""

from __future__ import annotations

import json

from scitex_app._chat._sse import (
    sse_done,
    sse_format,
    sse_keepalive,
    sse_keepalive_wrap,
)


def test_sse_format_serializes_dict():
    out = sse_format({"type": "chunk", "text": "hello"})
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    payload = json.loads(out[len("data: ") : -2])
    assert payload == {"type": "chunk", "text": "hello"}


def test_sse_done_marker():
    assert sse_done() == "data: [DONE]\n\n"


def test_sse_keepalive_marker():
    assert sse_keepalive() == ": keepalive\n\n"


def test_sse_keepalive_wrap_emits_done_at_end():
    events = iter([{"type": "chunk", "text": "a"}, {"type": "chunk", "text": "b"}])
    out = list(sse_keepalive_wrap(events, interval_s=999.0))
    # 2 events + final [DONE]
    assert len(out) == 3
    assert "chunk" in out[0]
    assert out[-1] == sse_done()
