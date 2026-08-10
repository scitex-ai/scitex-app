#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chat backend implementations — Anthropic and LiteLLM."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)


class AnthropicChatBackend:
    """Chat backend using the Anthropic SDK directly.

    Requires: ``pip install anthropic``
    Config: ``ANTHROPIC_API_KEY`` env var.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "claude-sonnet-4-20250514",
    ):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._default_model = default_model

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        kwargs: Dict[str, Any] = {
            "model": model or self._default_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield {"type": "chunk", "text": text}
            yield {"type": "done"}
        except Exception as e:
            logger.exception("Anthropic chat error")
            yield {"type": "error", "error": str(e)}


class LiteLLMChatBackend:
    """Chat backend using litellm for multi-provider support.

    Requires: ``pip install litellm``
    Config: provider-specific env vars (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
    """

    def __init__(self, default_model: str = "anthropic/claude-sonnet-4-20250514"):
        self._default_model = default_model

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        import litellm

        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        try:
            response = litellm.completion(
                model=model or self._default_model,
                messages=msgs,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield {"type": "chunk", "text": delta.content}
            yield {"type": "done"}
        except Exception as e:
            logger.exception("LiteLLM chat error")
            yield {"type": "error", "error": str(e)}


_DEFAULT_LLM_MODEL = "anthropic/claude-sonnet-4-20250514"


def _resolve_default_model() -> str:
    """Return the configured default LLM model id.

    ``SCITEX_APP_LLM_MODEL`` is the supported name. ``LLM_MODEL`` is a
    DEPRECATED alias kept because it was a published contract (documented in
    the environment-vars skill), so it is migrated rather than renamed: it
    still works and warns. The unprefixed name is being retired because it is
    generic enough to collide with any other tool in the same environment,
    which would silently change which model a user talks to.

    Precedence is prefixed-over-legacy, so a user midway through the
    migration who has BOTH set gets the new one and a warning naming the
    conflict -- never a silent pick.
    """
    prefixed = os.getenv("SCITEX_APP_LLM_MODEL")
    legacy = os.getenv("LLM_MODEL")
    if prefixed:
        if legacy and legacy != prefixed:
            logger.warning(
                "Both SCITEX_APP_LLM_MODEL and the deprecated LLM_MODEL are "
                "set and they disagree (%r vs %r). Using SCITEX_APP_LLM_MODEL; "
                "unset LLM_MODEL to silence this.",
                prefixed,
                legacy,
            )
        return prefixed
    if legacy:
        logger.warning(
            "LLM_MODEL is deprecated and will be removed; rename it to "
            "SCITEX_APP_LLM_MODEL (same value, %r).",
            legacy,
        )
        return legacy
    return _DEFAULT_LLM_MODEL


def get_chat_backend(
    model: Optional[str] = None,
) -> "AnthropicChatBackend | LiteLLMChatBackend":
    """Auto-detect and return the best available chat backend.

    Priority: Anthropic SDK (if key set) > LiteLLM > error.

    The default model comes from ``SCITEX_APP_LLM_MODEL``; see
    :func:`_resolve_default_model` for the deprecated ``LLM_MODEL`` alias.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic  # noqa: F401

            return AnthropicChatBackend(
                api_key=api_key,
                default_model=model or "claude-sonnet-4-20250514",
            )
        except ImportError:
            pass

    try:
        import litellm  # noqa: F401

        return LiteLLMChatBackend(
            default_model=model or _resolve_default_model(),
        )
    except ImportError:
        pass

    raise ImportError(
        "No LLM backend available. Install anthropic or litellm, "
        "and set ANTHROPIC_API_KEY."
    )
