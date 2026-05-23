#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""High-level streaming chat function."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional


def stream_chat(
    prompt: str,
    *,
    history: Optional[List[Dict[str, str]]] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    max_history: int = 10,
    backend: Optional[Any] = None,
) -> Iterator[Dict[str, Any]]:
    """Stream a chat response using the best available backend.

    Parameters
    ----------
    prompt : str
        User message.
    history : list of dict, optional
        Previous messages [{"role": "user/assistant", "content": "..."}].
    system_prompt : str, optional
        System prompt for the conversation.
    model : str, optional
        Model override.
    max_tokens : int
        Maximum response tokens.
    max_history : int
        Maximum history messages to include.
    backend : object, optional
        Chat backend to stream through. Defaults to the best available
        backend from ``get_chat_backend(model=model)``. Injectable so
        callers (and tests) can supply a concrete backend.

    Yields
    ------
    dict
        Event dicts: {"type": "chunk", "text": "..."}, {"type": "done"}, etc.
    """
    if backend is None:
        from ._backends import get_chat_backend

        backend = get_chat_backend(model=model)

    messages = []
    if history:
        messages.extend(history[-max_history:])
    messages.append({"role": "user", "content": prompt})

    yield from backend.stream(
        messages,
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
    )
