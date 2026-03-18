#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django views for chat streaming — mountable by any SciTeX app.

Usage::

    # In your Django app's urls.py:
    from scitex_app.chat import chat_urlpatterns
    urlpatterns += chat_urlpatterns

    # Or mount directly:
    from scitex_app.chat import chat_stream_view
    path("api/chat/stream", chat_stream_view, name="chat-stream"),
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse, StreamingHttpResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ._sse import sse_keepalive_wrap
from ._stream import stream_chat

logger = logging.getLogger(__name__)

# Default system prompt — apps can override via request body
_DEFAULT_SYSTEM = (
    "You are a helpful AI assistant in a SciTeX application. "
    "Help users with their scientific work."
)


@csrf_exempt
@require_http_methods(["POST"])
def chat_stream_view(request):
    """SSE streaming chat endpoint.

    Request body (JSON)::

        {
            "prompt": "user message",
            "history": [{"role": "user", "content": "..."}, ...],
            "system_prompt": "optional override",
            "model": "optional model override",
            "context": {}
        }

    Response: text/event-stream with SSE events.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return JsonResponse({"error": "prompt required"}, status=400)

    history = data.get("history", [])
    system_prompt = data.get("system_prompt", _DEFAULT_SYSTEM)
    model = data.get("model")

    try:
        events = stream_chat(
            prompt,
            history=history,
            system_prompt=system_prompt,
            model=model,
        )
        generator = sse_keepalive_wrap(events)
    except ImportError as e:
        return JsonResponse({"error": str(e)}, status=503)
    except Exception as e:
        logger.exception("Chat stream setup failed")
        return JsonResponse({"error": str(e)}, status=500)

    response = StreamingHttpResponse(generator, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# URL patterns — mount with: urlpatterns += chat_urlpatterns
chat_urlpatterns = [
    path("api/chat/stream", chat_stream_view, name="scitex-chat-stream"),
]
