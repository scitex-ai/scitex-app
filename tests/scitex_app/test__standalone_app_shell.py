#!/usr/bin/env python3
"""`app_shell.html` ships in the wheel and its block contract renders.

The adapter (scitex-app's) delegates to scitex-ui's `standalone_shell.html`
and re-opens that shell's `app_content` block as `scitex_app_content`. The
shell also exposes `extra_css` (head) and `extra_js` (tail) — measured on
scitex-ui develop `standalone_shell.html` lines 57/495/511 — and those pass
straight through the adapter to leaf apps, which is the contract Cards'
board_v3/standalone migration and SAC's fleet.html depend on.

The template search root is resolved RELATIVE TO THE IMPORTED `scitex_app`
package, so this test asserts the shipped artifact (the installed build in
CI), not a checkout path. The scitex-ui side is a hermetic stub with the
real shell's block names: scitex-app's own CI deliberately runs without
scitex-ui (that is the case `ScitexUiRequiredError` names), and the stub
keeps this contract test green there without weakening it.
"""

import os
import tempfile

import scitex_app

from django.template import Context, Engine

# `<scitex_app pkg>/templates` — the dir under which the template is named
# `scitex_app/app_shell.html`.
_PKG_TEMPLATES_ROOT = os.path.join(
    os.path.dirname(scitex_app.__file__), "templates"
)

# Minimal stand-in for scitex_ui/standalone_shell.html with the same block
# names as the real shell, so the render chain under test is exactly
# leaf -> app_shell (adapter) -> standalone_shell (scitex-ui).
_STUB_ROOT = tempfile.mkdtemp(prefix="stx-app-shell-stub-")
os.makedirs(os.path.join(_STUB_ROOT, "scitex_ui"), exist_ok=True)
with open(
    os.path.join(_STUB_ROOT, "scitex_ui", "standalone_shell.html"), "w"
) as _f:
    _f.write(
        "<html><head>{% block extra_css %}{% endblock %}</head>"
        "<main>{% block app_content %}__SHELL_DEFAULT__{% endblock %}</main>"
        "<tail>{% block extra_js %}{% endblock %}</tail></html>"
    )

_ENGINE = Engine(dirs=[_PKG_TEMPLATES_ROOT, _STUB_ROOT])


def _render_leaf(extra_blocks=""):
    # Arrange — a leaf template that extends the shipped adapter and fills
    # the content block, plus any extra chrome blocks under test.
    leaf = _ENGINE.from_string(
        '{% extends "scitex_app/app_shell.html" %}'
        "{% block scitex_app_content %}__LEAF_BODY__{% endblock %}" + extra_blocks
    )
    # Act — render it against the adapter -> stub shell chain.
    # Assert — the return value is the rendered HTML string.
    return leaf.render(Context({}))


def test_app_shell_is_present_in_the_installed_package():
    # Arrange — the path the shipped template must occupy. The 0.23.0 wheel
    # shipped zero Django templates; this is the line Cards' migration fell
    # back from. Resolved via the imported package, so in CI it checks the
    # installed build, not a checkout.
    path = os.path.join(_PKG_TEMPLATES_ROOT, "scitex_app", "app_shell.html")
    # Act
    present = os.path.exists(path)
    # Assert
    assert present


def test_leaf_body_renders_into_the_shell_content_region():
    # Arrange
    leaf = _render_leaf()
    # Act
    body_present = "__LEAF_BODY__" in leaf
    # Assert
    assert body_present


def test_unoverridden_shell_default_is_replaced():
    # Arrange
    leaf = _render_leaf()
    # Act
    default_absent = "__SHELL_DEFAULT__" not in leaf
    # Assert
    assert default_absent


def test_extra_css_passes_through_the_adapter():
    # Arrange
    leaf = _render_leaf(
        "{% block extra_css %}__LEAF_CSS__{% endblock %}"
    )
    # Act
    css_present = "__LEAF_CSS__" in leaf
    # Assert
    assert css_present


def test_extra_js_passes_through_the_adapter():
    # Arrange
    leaf = _render_leaf(
        "{% block extra_js %}__LEAF_JS__{% endblock %}"
    )
    # Act
    js_present = "__LEAF_JS__" in leaf
    # Assert
    assert js_present
