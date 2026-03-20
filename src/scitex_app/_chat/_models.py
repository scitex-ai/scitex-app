#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django models for chat sessions and messages.

Ported from scitex-cloud's llm_app.models (ChatSession, ChatMessage).
Simplified for standalone use — no user FK (single-user mode),
no share_token / is_shared (handled at cloud level if needed).
"""

from __future__ import annotations

from django.db import models


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
