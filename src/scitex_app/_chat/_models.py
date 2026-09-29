#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django models for chat sessions and messages.

Ported from scitex-cloud's llm_app.models (ChatSession, ChatMessage).
Simplified for SINGLE-USER use — no user FK, no share_token / is_shared
(handled at cloud level if needed).

THESE MODELS REQUIRE A CONFIGURED DATABASE, and this line exists because
the word that used to be here did not say so. It read "simplified for
STANDALONE use", meaning single-user-rather-than-cloud — while
`scitex_app._standalone`, the launcher, uses the same word for a profile
that sets ``DATABASES={}``. Two senses, one word, in one package.

On 2026-09-06 figrecipe wired the session views into that launcher's
settings and every one of them answered 500 with a Django settings
diagnostic. They were not careless: the chat package documented itself as
the "standalone" way to use chat, and the launcher is literally named
standalone. Nothing in either place said the two could not be combined.

So: "standalone" in this package means THE LAUNCHER (`run_standalone`,
skill 05) and nothing else. Say "single-user" for this, and "without
Django" for library use of `stream_chat`, which genuinely needs no
database.
"""

from __future__ import annotations

try:
    from django.db import models
except ImportError as exc:
    raise ImportError(
        "scitex_app._chat._models needs django: pip install scitex-app[all]"
    ) from exc


class ChatSession(models.Model):
    """A named chat conversation."""

    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        app_label = "scitex_app"

    def __str__(self) -> str:
        return f"ChatSession({self.id}): {self.title}"


class ChatMessage(models.Model):
    """A single message within a chat session."""

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20)  # user | assistant | error
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        app_label = "scitex_app"

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:60]}"
