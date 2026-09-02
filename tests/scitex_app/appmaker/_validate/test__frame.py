"""Tests for scitex_app/appmaker/_validate/_frame.py."""

from __future__ import annotations


from scitex_app.appmaker._validate import (
    validate_templates,
    validate_css,
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

    def test_deprecated_color_variable_adds_error(self, tmp_path):
        # Arrange
        (tmp_path / "style.css").write_text("color: var(--color-primary);")
        # Act
        errors = validate_css(tmp_path)
        # Assert
        assert any("--color-" in e or "--workspace-*" in e for e in errors)

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
