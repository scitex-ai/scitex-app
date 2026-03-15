#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ChatBackend protocol — structural typing for pluggable LLM providers."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ChatBackend(Protocol):
    """LLM chat backend protocol.

    Implementations must provide ``stream()``.
    Uses ``typing.Protocol`` for structural subtyping.

    Implementations
    ---------------
    - ``AnthropicChatBackend`` — direct Anthropic SDK
    - ``LiteLLMChatBackend`` — multi-provider via litellm
    """

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream chat completion events.

        Parameters
        ----------
        messages : list of dict
            OpenAI-format messages: [{"role": "user", "content": "..."}]
        model : str, optional
            Model override. If None, use backend default.
        max_tokens : int
            Maximum tokens in response.
        temperature : float
            Sampling temperature.
        system : str, optional
            System prompt.

        Yields
        ------
        dict
            Event dicts with "type" key:
            - {"type": "chunk", "text": "..."}
            - {"type": "done"}
            - {"type": "error", "error": "..."}
        """
        ...
