#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django views for chat session CRUD.

Ported from scitex-cloud's llm_app/views/sessions.py.
All endpoints are CSRF-exempt for programmatic API use.

EVERY VIEW HERE QUERIES THE ORM, so a host mounting them must configure a
database. `chat_stream_view` in `_django.py` does not and is safe without
one. ("standalone" is reserved for the launcher — see `_models.py`.)

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

import functools
import json

import scitex_logging as slogging

try:
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt
    from django.views.decorators.http import require_http_methods
except ImportError as exc:
    raise ImportError(
        "scitex_app._chat._session_views needs django: "
        "pip install scitex-app[all]"
    ) from exc

from ._models import ChatMessage, ChatSession

log = slogging.getLogger(__name__)


class ChatSessionsUnavailableError(ImproperlyConfigured):
    """A session view was called in a process where it cannot serve.

    THE BASE TO CATCH. There are two independent requirements — a database,
    and the models' app being installed — and a host that just wants "can
    these views work here" should not have to enumerate them. The two
    subclasses exist because the two FIXES are different, and an error that
    cannot say which requirement is missing sends the reader to the wrong one.

    SUBCLASSES ImproperlyConfigured, which is what Django raised here before
    0.21.0, so a host already catching that keeps working.
    """


class ChatSessionsRequireADatabaseError(ChatSessionsUnavailableError):
    """No usable database in this process.

    SUBCLASSES ImproperlyConfigured on purpose. That is what Django itself
    raised here before 0.21.0, so any host already catching it keeps working
    and this is an additive change. The subclass exists for the MESSAGE:
    Django's own reads "settings.DATABASES is improperly configured. Please
    supply the ENGINE value." — which names a setting rather than the mistake,
    and reads as simply wrong to a host that left DATABASES empty deliberately.
    The host's error is not the setting; it is having mounted these views at
    all.

    HONEST ABOUT WHAT THIS IS. It is a better DIAGNOSIS, not a barrier.
    Mounting `chat_urlpatterns` without a database still imports, still starts,
    and still fails per request. Making it impossible rather than merely loud
    is a separate question about whether these views belong in this SDK — see
    the card, which is not closed by this.
    """


_NO_DATABASE = (
    "scitex_app chat SESSION views require a configured database, and this "
    "process has none (settings.DATABASES has no usable ENGINE).\n"
    "\n"
    "The usual cause is mounting `chat_urlpatterns`, which bundles the session "
    "CRUD routes together with the database-free streaming route, into a host "
    "that configures no database — `scitex_app.run_standalone` is one such "
    "host.\n"
    "\n"
    "Two fixes; pick the one that matches what you wanted:\n"
    "  - streaming only, no database: mount `chat_stream_urlpatterns` instead "
    "of `chat_urlpatterns`.\n"
    "  - session history as well: configure settings.DATABASES and migrate "
    "the `scitex_app._chat` app."
)


class ChatSessionsAppNotInstalledError(ChatSessionsUnavailableError):
    """A database exists, but no installed app carries the models' app_label.

    THE CASE 0.21.0 MISSED, and the reason it missed it. 0.21.0 asked "is a
    database configured" and wrote a message saying these views "require a
    configured database". True, and not the whole requirement: `ChatSession`
    and `ChatMessage` declare an EXPLICIT `app_label` (see `_models.py`), so
    Django creates the classes happily and only consults the app registry
    later, at query time. A host with a real database and no registration
    therefore sailed past the 0.21.0 guard and failed deeper down with a
    LookupError about an app label — the confusing error 0.21.0 existed to
    remove, surviving in a different configuration.

    Measured on scitex-hub 2026-09-06: it installs `figrecipe._django`, which
    loads that module's DEFAULT AppConfig only, while the config that
    registers these models is a SECOND AppConfig in the same module. One
    INSTALLED_APPS entry does not load two AppConfigs.
    """


_NO_APP = (
    "scitex_app chat SESSION views need their models registered, and no "
    "installed app carries the app_label %r in this process. A database IS "
    "configured — this is the OTHER requirement.\n"
    "\n"
    "Add the AppConfig that registers them to INSTALLED_APPS explicitly. "
    "Naming the module is not enough if the config you need is not that "
    "module's default AppConfig — one entry loads one config.\n"
    "\n"
    "If you did not mean to serve chat history at all, mount "
    "`chat_stream_urlpatterns` instead of `chat_urlpatterns`."
)


def _app_is_installed(label: str) -> bool:
    """Does an INSTALLED_APPS entry carry this app label?

    Asked of the label rather than hardcoded, so the check cannot drift from
    whatever `_models.py` declares and so it can be exercised in both
    directions in a test.
    """
    try:
        from django.apps import apps
    except ImportError as exc:
        raise ImportError(
            "scitex_app._chat._session_views needs django: "
            "pip install scitex-app[all]"
        ) from exc

    try:
        apps.get_app_config(label)
    except LookupError:
        return False
    return True


def _database_is_configured() -> bool:
    """Does this process have a database it could actually query?

    `DATABASES={}` does NOT stay an empty mapping: by the time Django is set
    up it has been filled in with the DUMMY backend, whose ENGINE ends in
    `.dummy` and whose entire behaviour is to raise. So "no database" is
    either no ENGINE at all or that sentinel — testing `not settings.DATABASES`
    would miss the exact case this guard exists for.
    """
    default = (getattr(settings, "DATABASES", None) or {}).get("default") or {}
    engine = default.get("ENGINE") or ""
    return bool(engine) and not engine.endswith(".dummy")


def _requires_usable_models(view):
    """Fail with a message that names the MOUNT mistake, before touching the ORM.

    Applied INNERMOST (closest to `def`), so `require_http_methods` still
    answers a bad method with 405 rather than this — a wrong verb is a
    different mistake and deserves its own error.
    """

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not _database_is_configured():
            raise ChatSessionsRequireADatabaseError(_NO_DATABASE)
        label = ChatSession._meta.app_label
        if not _app_is_installed(label):
            raise ChatSessionsAppNotInstalledError(_NO_APP % (label,))
        return view(request, *args, **kwargs)

    return wrapper


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
@_requires_usable_models
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
@_requires_usable_models
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
@_requires_usable_models
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
