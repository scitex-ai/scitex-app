#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django views for chat session CRUD.

Ported from scitex-cloud's llm_app/views/sessions.py.
All endpoints are CSRF-exempt for standalone / API use.

Endpoints:
    GET    /api/chat/sessions/                  — list sessions
    POST   /api/chat/sessions/                  — create session
    GET    /api/chat/sessions/<id>/              — get session detail
    PATCH  /api/chat/sessions/<id>/              — update session title
    DELETE /api/chat/sessions/<id>/              — delete session
    GET    /api/chat/sessions/<id>/messages/     — get session messages
    POST   /api/chat/sessions/<id>/messages/     — add message to session
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ._models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


def _session_to_dict(session: ChatSession, include_count: bool = True) -> dict:
    """Serialize a ChatSession to a JSON-friendly dict."""
    d = {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }
    if include_count:
        d["message_count"] = session.messages.count()
    return d


@csrf_exempt
@require_http_methods(["GET", "POST"])
def session_list_view(request):
    """List or create chat sessions."""
    if request.method == "GET":
        qs = ChatSession.objects.all()[:50]
        sessions = [_session_to_dict(s) for s in qs]
        return JsonResponse({"sessions": sessions})

    # POST: create
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    title = (body.get("title", "New Chat") or "New Chat").strip()[:255]
    session = ChatSession.objects.create(title=title)
    return JsonResponse(_session_to_dict(session, include_count=False), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def session_detail_view(request, session_id: int):
    """Get, update, or delete a specific session."""
    try:
        session = ChatSession.objects.get(id=session_id)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_session_to_dict(session))

    if request.method == "PATCH":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        fields = []
        if "title" in body:
            session.title = (body["title"] or session.title).strip()[:255]
            fields.append("title")
        if fields:
            session.save(update_fields=fields + ["updated_at"])
        return JsonResponse(_session_to_dict(session))

    # DELETE
    session.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def session_messages_view(request, session_id: int):
    """Get or add messages for a session."""
    try:
        session = ChatSession.objects.get(id=session_id)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)

    if request.method == "GET":
        messages = list(
            session.messages.all().values("id", "role", "content", "created_at")
        )
        return JsonResponse(
            {
                "session_id": session.id,
                "title": session.title,
                "messages": messages,
            }
        )

    # POST: add message
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    role = (body.get("role", "") or "").strip()
    if role not in ("user", "assistant", "error"):
        return JsonResponse({"error": "Invalid role"}, status=400)

    content = (body.get("content", "") or "").strip()
    if not content:
        return JsonResponse({"error": "content required"}, status=400)

    msg = ChatMessage.objects.create(
        session=session,
        role=role,
        content=content,
    )

    # Auto-title from first user message
    if role == "user" and session.title == "New Chat":
        session.title = content[:50] + ("..." if len(content) > 50 else "")
        session.save(update_fields=["title", "updated_at"])
    else:
        session.save(update_fields=["updated_at"])

    return JsonResponse(
        {"id": msg.id, "created_at": msg.created_at.isoformat()}, status=201
    )
