#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared chat module — LLM streaming for all SciTeX apps.

Provides:
- ChatBackend protocol for pluggable LLM providers
- SSE streaming utilities
- Django view that any app can mount
- Chat session models and CRUD views

``chat`` is exposed on the ``scitex_app`` package via a lazy
``__getattr__`` (PEP 562), not as a real importable submodule — so
``from scitex_app.chat import X`` raises ``ModuleNotFoundError``. Use
the bare ``from scitex_app import chat`` form (which does trigger the
package's ``__getattr__``), then attribute-access from there.

Usage (Django)::

    # urls.py
    from scitex_app import chat
    urlpatterns += chat.chat_urlpatterns

Usage (standalone)::

    from scitex_app import chat
    for event in chat.stream_chat("Hello", system_prompt="You are helpful."):
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
    # Session views
    if name == "session_list_view":
        from ._session_views import session_list_view

        return session_list_view
    if name == "session_detail_view":
        from ._session_views import session_detail_view

        return session_detail_view
    if name == "session_messages_view":
        from ._session_views import session_messages_view

        return session_messages_view
    # Models
    if name == "ChatSession":
        from ._models import ChatSession

        return ChatSession
    if name == "ChatMessage":
        from ._models import ChatMessage

        return ChatMessage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
