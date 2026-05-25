#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scitex_app/_chat/_stream.py — high-level stream_chat helper."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

import pytest

from scitex_app._chat import _stream


class _RecordingBackend:
    """Backend that records arguments and yields a fixed event sequence."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        self.calls.append(
            {
                "messages": list(messages),
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
            }
        )
        yield {"type": "chunk", "text": "hi"}
        yield {"type": "done"}


@pytest.fixture
def recording_backend():
    """A concrete recording backend injected via stream_chat(backend=...)."""
    return _RecordingBackend()


def test_stream_chat_appends_user_prompt(recording_backend):
    # Arrange
    backend = recording_backend
    # Act
    list(_stream.stream_chat("hello", backend=backend))
    # Assert
    assert backend.calls[-1]["messages"] == [{"role": "user", "content": "hello"}]


def test_stream_chat_passes_through_system_prompt(recording_backend):
    # Arrange
    backend = recording_backend
    # Act
    list(_stream.stream_chat("hi", system_prompt="be terse", backend=backend))
    # Assert
    assert backend.calls[-1]["system"] == "be terse"


def test_stream_chat_truncates_history_len_msgs_is_4(recording_backend):
    # Arrange
    backend = recording_backend
    history = [{"role": "user", "content": str(i)} for i in range(20)]
    # Act
    list(_stream.stream_chat("hi", history=history, max_history=3, backend=backend))
    # Assert
    assert len(backend.calls[-1]["messages"]) == 4


def test_stream_chat_truncates_history_keeps_latest_user_prompt(recording_backend):
    # Arrange
    backend = recording_backend
    history = [{"role": "user", "content": str(i)} for i in range(20)]
    # Act
    list(_stream.stream_chat("hi", history=history, max_history=3, backend=backend))
    # Assert
    assert backend.calls[-1]["messages"][-1] == {"role": "user", "content": "hi"}


def test_stream_chat_yields_backend_events(recording_backend):
    # Arrange
    backend = recording_backend
    # Act
    events = list(_stream.stream_chat("hi", backend=backend))
    # Assert
    assert events == [{"type": "chunk", "text": "hi"}, {"type": "done"}]
