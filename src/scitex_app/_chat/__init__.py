#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared chat module — LLM streaming for all SciTeX apps.

Provides:
- ChatBackend protocol for pluggable LLM providers
- SSE streaming utilities
- Django view that any app can mount

Usage (Django)::

    # urls.py
    from scitex_app.chat import chat_urlpatterns
    urlpatterns += chat_urlpatterns

Usage (standalone)::

    from scitex_app.chat import stream_chat
    for event in stream_chat("Hello", system_prompt="You are helpful."):
        print(event)
"""

from ._protocol import ChatBackend
from ._stream import stream_chat
from ._sse import sse_format, sse_keepalive_wrap

__all__ = [
    "ChatBackend",
    "stream_chat",
    "sse_format",
    "sse_keepalive_wrap",
]


def __getattr__(name: str):
    """Lazy imports for optional Django integration."""
    if name == "chat_urlpatterns":
        from ._django import chat_urlpatterns

        return chat_urlpatterns
    if name == "chat_stream_view":
        from ._django import chat_stream_view

        return chat_stream_view
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
