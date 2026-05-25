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


def test_sse_format_serializes_dict_out_startswith_data():
    # Arrange
    # Arrange
    # Act
    out = sse_format({"type": "chunk", "text": "hello"})
    # Act
    # Assert
    # Assert
    assert out.startswith("data: ")


def test_sse_format_serializes_dict_out_endswith_n_n():
    # Arrange
    # Arrange
    # Act
    out = sse_format({"type": "chunk", "text": "hello"})
    # Act
    # Assert
    # Assert
    assert out.endswith("\n\n")


def test_sse_format_serializes_dict_payload_equals_type_chunk_text_hello():
    # Arrange
    out = sse_format({"type": "chunk", "text": "hello"})
    # Act
    payload = json.loads(out[len("data: ") : -2])
    # Assert
    assert payload == {"type": "chunk", "text": "hello"}


def test_sse_done_marker():
    # Arrange
    # Act
    # Assert
    assert sse_done() == "data: [DONE]\n\n"


def test_sse_keepalive_marker():
    # Arrange
    # Act
    # Assert
    assert sse_keepalive() == ": keepalive\n\n"


def test_sse_keepalive_wrap_emits_done_at_end_len_out_is_3():
    # Arrange
    # Arrange
    events = iter([{"type": "chunk", "text": "a"}, {"type": "chunk", "text": "b"}])
    # Act
    out = list(sse_keepalive_wrap(events, interval_s=999.0))
    # Act
    # Assert
    # Assert
    assert len(out) == 3


def test_sse_keepalive_wrap_emits_done_at_end_chunk_in_out_0():
    # Arrange
    # Arrange
    events = iter([{"type": "chunk", "text": "a"}, {"type": "chunk", "text": "b"}])
    # Act
    out = list(sse_keepalive_wrap(events, interval_s=999.0))
    # Act
    # Assert
    # Assert
    assert "chunk" in out[0]


def test_sse_keepalive_wrap_emits_done_at_end_out_1_sse_done():
    # Arrange
    # Arrange
    events = iter([{"type": "chunk", "text": "a"}, {"type": "chunk", "text": "b"}])
    # Act
    out = list(sse_keepalive_wrap(events, interval_s=999.0))
    # Act
    # Assert
    # Assert
    assert out[-1] == sse_done()
