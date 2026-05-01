#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke tests for scitex_app/_chat/migrations/0001_initial.py.

Django migration files are generated metadata — the only meaningful check
is that the module imports cleanly under Django and declares the expected
model operations. Full ORM behaviour is covered by Django's own migration
runner in downstream apps that mount scitex_app.
"""

from __future__ import annotations

import importlib

import pytest

# Skip when Django is not installed (chat is an optional extra).
pytest.importorskip("django")


def test_migration_module_imports():
    mod = importlib.import_module("scitex_app._chat.migrations.0001_initial")
    assert hasattr(mod, "Migration")


def test_migration_creates_chat_models():
    mod = importlib.import_module("scitex_app._chat.migrations.0001_initial")
    op_names = {
        getattr(op, "name", None) or type(op).__name__
        for op in mod.Migration.operations
    }
    assert "ChatSession" in op_names
    assert "ChatMessage" in op_names


def test_migration_is_initial():
    mod = importlib.import_module("scitex_app._chat.migrations.0001_initial")
    assert mod.Migration.initial is True
    assert mod.Migration.dependencies == []
