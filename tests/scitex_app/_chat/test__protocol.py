#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scitex_app/_chat/_protocol.py — ChatBackend Protocol contract."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from scitex_app._chat._protocol import ChatBackend


class _StubBackend:
    """Minimal stream() implementation that satisfies the Protocol."""

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        yield {"type": "chunk", "text": "ok"}
        yield {"type": "done"}


class _MissingStream:
    pass


def test_protocol_runtime_check_passes_with_stream():
    # Arrange
    # Act
    # Assert
    assert isinstance(_StubBackend(), ChatBackend)


def test_protocol_runtime_check_fails_without_stream():
    # Arrange
    # Act
    # Assert
    assert not isinstance(_MissingStream(), ChatBackend)


def test_stub_yields_expected_event_shape_events_0_type_chunk():
    # Arrange
    # Arrange
    # Act
    events = list(_StubBackend().stream([{"role": "user", "content": "hi"}]))
    # Act
    # Assert
    # Assert
    assert events[0]["type"] == "chunk"


def test_stub_yields_expected_event_shape_events_1_type_done():
    # Arrange
    # Arrange
    # Act
    events = list(_StubBackend().stream([{"role": "user", "content": "hi"}]))
    # Act
    # Assert
    # Assert
    assert events[-1]["type"] == "done"


