#!/usr/bin/env python3
# Timestamp: 2026-07-29
# File: tests/scitex_app/test__django.py

"""Tests for scitex_app._django — the mount-prefix marker.

The marker is what lets ONE codebase serve both standalone and as a
scitex-hub built-in app. `scitex_urlpatterns` is already prefix-agnostic
server-side, but nothing told the BROWSER where the app was mounted, so
client code hardcoded "/" — correct standalone, silently broken embedded.
"""

from __future__ import annotations

import django
import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8", ALLOWED_HOSTS=["*"])
    django.setup()

from django.test import RequestFactory  # noqa: E402

from scitex_app._django import (  # noqa: E402
    MOUNT_META_NAME,
    _inject_mount_meta,
    scitex_editor_page,
)

# Both real mounts this feature exists to span: "/" standalone, and the
# hub's published-app prefix (apps/workspace/apps_app/urls_user_apps.py
# mounts under "apps/u/<module_name>/").
STANDALONE = "/"
EMBEDDED = "/apps/u/figrecipe/"


def _serve(tmp_path, html: str, path: str) -> str:
    (tmp_path / "index.html").write_text(html)
    view = scitex_editor_page(tmp_path)
    response = view(RequestFactory().get(path))
    return response.content.decode()


def test_injects_marker_into_head(tmp_path):
    # Arrange
    html = "<html><head><title>x</title></head><body></body></html>"
    # Act
    served = _serve(tmp_path, html, EMBEDDED)
    # Assert
    assert f'<meta name="{MOUNT_META_NAME}" content="{EMBEDDED}">' in served


def test_marker_is_inside_the_head_element(tmp_path):
    # Arrange — a meta after </head> is not guaranteed to be parsed as
    # metadata, so placement is part of the contract, not cosmetic.
    html = "<html><head><title>x</title></head><body></body></html>"
    # Act
    served = _serve(tmp_path, html, EMBEDDED)
    # Assert
    assert served.index(MOUNT_META_NAME) < served.index("</head>")


@pytest.mark.parametrize(
    "request_path,expected",
    [
        (STANDALONE, "/"),
        (EMBEDDED, "/apps/u/figrecipe/"),
        # Django can route a mount without the trailing slash; the marker
        # must still be a usable base for joining, so it is normalised.
        ("/apps/u/figrecipe", "/apps/u/figrecipe/"),
    ],
)
def test_marker_carries_the_actual_mount_prefix(tmp_path, request_path, expected):
    # Arrange
    html = "<html><head></head><body></body></html>"
    # Act
    served = _serve(tmp_path, html, request_path)
    # Assert
    assert f'content="{expected}"' in served


def test_one_build_serves_differently_under_each_mount(tmp_path):
    # Arrange — the whole point: one build, two mounts, no rebuild.
    html = "<html><head></head><body></body></html>"
    # Act
    standalone = _serve(tmp_path, html, STANDALONE)
    embedded = _serve(tmp_path, html, EMBEDDED)
    # Assert
    assert standalone != embedded


def test_standalone_mount_marks_the_root(tmp_path):
    # Arrange
    html = "<html><head></head><body></body></html>"
    # Act
    served = _serve(tmp_path, html, STANDALONE)
    # Assert
    assert 'content="/"' in served


def test_body_is_otherwise_untouched(tmp_path):
    # Arrange — a built SPA's index.html is not ours to rewrite.
    html = '<html><head></head><body><div id="root"></div><script src="/a.js"></script></body></html>'
    # Act
    served = _serve(tmp_path, html, EMBEDDED)
    # Assert
    assert '<div id="root"></div><script src="/a.js"></script>' in served


def test_template_syntax_in_the_bundle_survives_verbatim(tmp_path):
    # Arrange — THE reason this is a string insertion and not a Django
    # template render. Bundled JS routinely contains `{{` and `{%`; a
    # render would try to interpret them and break the bundle for reasons
    # unrelated to mounting.
    html = "<html><head></head><body><script>var t={{a:1}};var p='{% raw %}';</script></body></html>"
    # Act
    served = _serve(tmp_path, html, EMBEDDED)
    # Assert
    assert "var t={{a:1}};var p='{% raw %}';" in served


def test_prefix_is_html_escaped(tmp_path):
    # Arrange — the prefix reaches an HTML attribute, and request.path is
    # attacker-influenced. Escaping is a security property, not tidiness.
    html = "<html><head></head><body></body></html>"
    # Act
    served = _serve(tmp_path, html, '/apps/u/x"><script>alert(1)</script>/')
    # Assert
    assert "<script>alert(1)</script>" not in served


@pytest.mark.parametrize(
    "html",
    [
        "<div>bare fragment</div>",
        # <header> is NOT <head>. A substring search for "<head" matches it,
        # which put the marker inside the <header> element instead of at the
        # front -- findable, so the contract held, but not where the docstring
        # says. The plain fragment above cannot catch that; this case can.
        "<html><body><header>nav</header><div>x</div></body></html>",
        "<html><body><HEADER>nav</HEADER></body></html>",
    ],
)
def test_marker_still_emitted_when_document_has_no_head(html):
    # Arrange — dropping the prefix silently is the exact failure mode
    # this feature exists to remove, so an unusual document must not
    # lose it. A leading <meta> is hoisted into the head by the parser.
    # Act
    injected = _inject_mount_meta(html, EMBEDDED)
    # Assert
    assert injected.startswith(f'<meta name="{MOUNT_META_NAME}"')


@pytest.mark.parametrize(
    "html",
    [
        "<html><head><title>x</title></head><body></body></html>",
        '<html><head lang="en"><title>x</title></head><body></body></html>',
        "<html><HEAD><title>x</title></HEAD><body></body></html>",
    ],
)
def test_real_head_still_receives_the_marker_inside_it(html):
    # Arrange — the counterpart to the case above: tightening the match
    # must not stop recognising a genuine <head>, with or without
    # attributes, in either case.
    # Act
    injected = _inject_mount_meta(html, EMBEDDED)
    # Assert
    assert injected.lower().index(MOUNT_META_NAME) < injected.lower().index("</head>")


def test_headless_document_keeps_its_own_content():
    # Arrange — prepending the marker must not cost the document anything.
    html = "<div>bare fragment</div>"
    # Act
    injected = _inject_mount_meta(html, EMBEDDED)
    # Assert
    assert "<div>bare fragment</div>" in injected


def test_missing_build_still_reports_503(tmp_path):
    # Arrange — pre-existing behaviour must be unchanged by this feature.
    view = scitex_editor_page(tmp_path)
    # Act
    response = view(RequestFactory().get(EMBEDDED))
    # Assert
    assert response.status_code == 503
