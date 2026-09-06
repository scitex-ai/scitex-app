"""Tests for scitex_app/appmaker/_validate/_frame.py."""

from __future__ import annotations


from scitex_app.appmaker._validate import (
    validate_templates,
    validate_css,
    validate_css_advisory,
    PROTECTED_SELECTORS,
    FORBIDDEN_BLOCK_OVERRIDES,
)
from ._helpers import (
    write_manifest,
)


# ---------------------------------------------------------------------------
# Tests: validate_templates
# ---------------------------------------------------------------------------


class TestValidateTemplates:
    def test_no_app_name_returns_no_errors(self, tmp_path):
        # No manifest and no directory name matching app
        # Arrange
        # Act
        errors = validate_templates(tmp_path)
        # Assert
        assert isinstance(errors, list)

    def test_missing_index_html_is_fine(self, tmp_path):
        """If index.html doesn't exist, template checks are skipped."""
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        # Act
        errors = validate_templates(tmp_path)
        # Assert
        assert errors == []

    def test_valid_template_passes(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "index.html").write_text(
            "{% extends 'global_base.html' %}{% block content %}hello{% endblock %}"
        )
        # Act
        errors = validate_templates(tmp_path)
        # Assert
        assert errors == []

    def test_missing_global_base_extend_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "index.html").write_text("{% block content %}hello{% endblock %}")
        # Act
        errors = validate_templates(tmp_path)
        # Assert
        assert any("global_base.html" in e for e in errors)

    def test_missing_block_content_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "index.html").write_text("{% extends 'global_base.html' %}")
        # Act
        errors = validate_templates(tmp_path)
        # Assert
        assert any("block content" in e for e in errors)

    def test_forbidden_block_override_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        forbidden_block = FORBIDDEN_BLOCK_OVERRIDES[0]
        (tmpl_dir / "index.html").write_text(
            f"{{% extends 'global_base.html' %}}"
            f"{{% block content %}}{{% endblock %}}"
            f"{{% block {forbidden_block} %}}{{% endblock %}}"
        )
        # Act
        errors = validate_templates(tmp_path)
        # Assert
        assert any(forbidden_block in e for e in errors)


# ---------------------------------------------------------------------------
# Tests: validate_css
# ---------------------------------------------------------------------------


class TestValidateCss:
    def test_clean_css_passes(self, tmp_path):
        # Arrange
        (tmp_path / "style.css").write_text("body { margin: 0; }")
        # Act
        errors = validate_css(tmp_path)
        # Assert
        assert errors == []

    def test_deprecated_color_variable_is_not_an_error(self, tmp_path):
        """Deprecated variables still RENDER — drift, not a broken app."""
        # Arrange
        (tmp_path / "style.css").write_text("color: var(--color-primary);")
        # Act
        errors = validate_css(tmp_path)
        # Assert
        assert not [e for e in errors if "--color-" in e or "--workspace-*" in e]

    def test_deprecated_color_variable_is_an_advisory(self, tmp_path):
        """The other arm: moved to the warn tier, NOT deleted."""
        # Arrange
        (tmp_path / "style.css").write_text("color: var(--color-primary);")
        # Act
        warnings = validate_css_advisory(tmp_path)
        # Assert
        assert any("--color-" in w or "--workspace-*" in w for w in warnings)

    def test_compliant_css_raises_no_advisory(self, tmp_path):
        # Arrange
        (tmp_path / "style.css").write_text("color: var(--workspace-fg);")
        # Act
        warnings = validate_css_advisory(tmp_path)
        # Assert
        assert warnings == []

    def test_important_on_protected_selector_adds_error(self, tmp_path):
        # Arrange
        selector = PROTECTED_SELECTORS[0]
        css = f"{selector} {{ color: red !important; }}"
        (tmp_path / "bad.css").write_text(css)
        # Act
        errors = validate_css(tmp_path)
        # Assert
        assert any("!important" in e for e in errors)

    def test_footer_display_none_adds_error(self, tmp_path):
        # Arrange
        (tmp_path / "bad.css").write_text("footer { display: none; }")
        # Act
        errors = validate_css(tmp_path)
        # Assert
        assert any("footer" in e for e in errors)

    def test_git_dir_excluded_from_css_scan(self, tmp_path):
        # Arrange
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "hook.css").write_text("footer { display: none; }")
        # Act
        errors = validate_css(tmp_path)
        # Assert
        assert errors == []


# EOF


def _index(tmp_path, body):
    import json

    app = tmp_path / "myapp"
    (app / "templates" / "myapp").mkdir(parents=True)
    (app / "manifest.json").write_text(json.dumps({"name": "myapp"}), encoding="utf-8")
    (app / "templates" / "myapp" / "index.html").write_text(body, encoding="utf-8")
    return app


def test_a_requirement_present_only_in_a_comment_no_longer_satisfies_it(
    tmp_path,
):
    """THE FALSE NEGATIVE, and the reason this fix is not a tidy-up.

    These checks are PRESENCE tests (`"global_base.html" not in content`), so a
    comment does not merely add a spurious finding — it SATISFIES A
    REQUIREMENT. Measured on the shipped 0.14.2 with controls: this page, which
    extends nothing and defines no content block, reported ZERO errors.

    Every other instance of this blindness found the same day was a false
    POSITIVE: documentation read as code, noisy but visible. This one is
    silent, and it sits in a check that runs by DEFAULT rather than behind a
    `check_*` flag.
    """
    # Arrange
    app = _index(
        tmp_path,
        '<!-- TODO: {% extends "global_base.html" %} {% block content %} -->\n<p>hi</p>\n',
    )
    from scitex_app.appmaker._validate import validate_templates

    # Act
    reported = validate_templates(app)
    # Assert — both requirements are genuinely unmet and both are reported.
    assert len(reported) == 2


def test_a_conformant_page_still_passes(tmp_path):
    """The control for the arm above: if the stripper broke the presence tests
    outright, the test above would pass for the wrong reason."""
    # Arrange
    app = _index(
        tmp_path,
        '{% extends "global_base.html" %}\n{% block content %}hi{% endblock %}\n',
    )
    from scitex_app.appmaker._validate import validate_templates

    # Act
    reported = validate_templates(app)
    # Assert
    assert not reported


def test_a_commented_out_forbidden_block_is_not_an_override(tmp_path):
    """The ordinary false positive in the same function, fixed by the same
    strip: a page documenting the override it removed was reported as still
    overriding."""
    # Arrange
    app = _index(
        tmp_path,
        '{% extends "global_base.html" %}\n{% block content %}h{% endblock %}\n'
        "<!-- removed: {% block workspace_ai_pane %}x{% endblock %} -->\n",
    )
    from scitex_app.appmaker._validate import validate_templates

    # Act
    reported = validate_templates(app)
    # Assert
    assert not reported


def test_a_css_rule_quoted_in_a_comment_is_not_applied(tmp_path):
    """This is the shape of the incident scitex-ui reported: a path quoted
    inside a CSS comment read as a live reference by a text scanner, which
    failed every PR in a peer repository."""
    # Arrange
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "a.css").write_text(
        "/* old: footer { display: none } */\nbody{color:red}\n", encoding="utf-8"
    )
    from scitex_app.appmaker._validate import validate_css

    # Act
    reported = validate_css(tmp_path)
    # Assert
    assert not reported


def test_a_live_css_rule_after_a_comment_is_still_reported(tmp_path):
    """The control. Hiding too much would convert the fix above into a silent
    failure to enforce the frame rules at all."""
    # Arrange
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "a.css").write_text(
        "/* note */\nfooter { display: none }\n", encoding="utf-8"
    )
    from scitex_app.appmaker._validate import validate_css

    # Act
    reported = validate_css(tmp_path)
    # Assert
    assert reported


# ---------------------------------------------------------------------------
# NAME BOUNDARY — added 2026-09-06. `re.escape(selector)` matched any name that
# merely STARTED with a protected one. scitex-hub measured 42 legitimate
# `stx-shell-sidebar__*` selector lines across nine apps; every one of them
# fired this rule. Same root cause as the bare `.stx-shell-` prefix removed
# from AppValidator's SHELL_SELECTORS in the same change.
# ---------------------------------------------------------------------------


def _css(tmp_path, text):
    d = tmp_path / "app"
    (d / "static").mkdir(parents=True)
    (d / "static" / "a.css").write_text(text, encoding="utf-8")
    return d


def test_an_apps_own_bem_element_is_not_a_protected_selector(tmp_path):
    # Arrange
    app = _css(tmp_path, ".stx-shell-sidebar__header-compact { color: red !important }\n")
    # Act
    errors = validate_css(app)
    # Assert
    assert errors == []


def test_a_class_ending_in_footer_is_not_the_footer_element(tmp_path):
    """`.myapp-footer` is a name an app is entitled to. The bare `footer`
    table entry used to claim it."""
    # Arrange
    app = _css(tmp_path, ".myapp-footer { color: red !important }\n")
    # Act
    errors = validate_css(app)
    # Assert
    assert errors == []


def test_a_class_ending_in_footer_may_be_hidden(tmp_path):
    """The footer-hiding check carried the same defect and needed the same
    boundary — an app hiding its OWN footer is not hiding the shell's."""
    # Arrange
    app = _css(tmp_path, ".myapp-footer { display: none }\n")
    # Act
    errors = validate_css(app)
    # Assert
    assert errors == []


def test_the_exact_protected_name_still_fires(tmp_path):
    """CONTROL. Without it, the three assertions above are equally consistent
    with 'the boundary works' and 'the rule stopped firing'."""
    # Arrange
    app = _css(tmp_path, ".stx-shell-sidebar { color: red !important }\n")
    # Act
    errors = validate_css(app)
    # Assert
    assert len(errors) == 1


def test_the_bare_footer_element_still_fires(tmp_path):
    """CONTROL for the leading boundary specifically: `footer` as an element
    must still be caught, which is what makes `.myapp-footer` a real
    discrimination rather than a disabled rule."""
    # Arrange
    app = _css(tmp_path, "footer { color: red !important }\n")
    # Act
    errors = validate_css(app)
    # Assert
    assert len(errors) == 1


def test_hiding_the_shells_footer_still_fires(tmp_path):
    # Arrange
    app = _css(tmp_path, "footer { display: none }\n")
    # Act
    errors = validate_css(app)
    # Assert
    assert len(errors) == 1
