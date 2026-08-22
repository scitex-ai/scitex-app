#!/usr/bin/env python3
# Timestamp: 2026-03-21
# File: tests/test__appmaker_validate.py

"""Tests for scitex_app/appmaker/_validate.py — app validation functions."""

from __future__ import annotations

import json
from pathlib import Path


from scitex_app.appmaker._validate import (
    validate,
    validate_structure,
    validate_security,
    validate_manifest,
    validate_templates,
    validate_css,
    validate_dependencies,
    _is_embedded_package,
    _get_frontend_type,
    _get_app_name,
    REQUIRED_FILES,
    FORBIDDEN_PATTERNS,
    MANIFEST_REQUIRED_KEYS,
    PROTECTED_SELECTORS,
    FORBIDDEN_BLOCK_OVERRIDES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_manifest(path: Path, data: dict) -> None:
    (path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")


def make_minimal_embedded_app(root: Path) -> None:
    """Create a minimal embedded app (passes validate() without template/CSS checks)."""
    write_manifest(
        root,
        {
            "name": "test_app",
            "slug": "test-app",
            "label": "Test App",
            "pip_package": "test-app",
            "icon": "fas fa-flask",
            "license": "MIT",
            "embedded_package": True,
            "dependencies": {"python": []},
        },
    )
    (root / "views.py").touch()
    (root / "urls.py").touch()


def make_full_standalone_app(root: Path, app_name: str = "myapp") -> None:
    """Create a standalone app with all required files."""
    write_manifest(
        root,
        {
            "name": app_name,
            "slug": app_name.replace("_", "-"),
            "label": "My App",
            "pip_package": app_name.replace("_", "-"),
            "icon": "fas fa-star",
            "license": "MIT",
            "dependencies": {"python": ["django"]},
        },
    )
    (root / "apps.py").touch()
    (root / "views.py").touch()
    (root / "urls.py").touch()
    (root / "LICENSE").write_text("MIT License", encoding="utf-8")
    (root / "README.md").write_text("# My App", encoding="utf-8")

    # Template for standalone app
    templates_dir = root / "templates" / app_name
    templates_dir.mkdir(parents=True)
    (templates_dir / "index_partial.html").write_text("<div>content</div>")

    # Agents config
    agents_dir = root / ".agents"
    agents_dir.mkdir()
    (agents_dir / "agents.json").write_text(json.dumps({"agents": []}))


# ---------------------------------------------------------------------------
# Tests: _is_embedded_package
# ---------------------------------------------------------------------------


class TestIsEmbeddedPackage:
    def test_underscore_prefix_is_embedded(self, tmp_path):
        # Arrange
        embedded_dir = tmp_path / "_django"
        # Act
        embedded_dir.mkdir()
        # Assert
        assert _is_embedded_package(embedded_dir) is True

    def test_normal_name_without_manifest_is_not_embedded(self, tmp_path):
        # Arrange
        app_dir = tmp_path / "myapp"
        # Act
        app_dir.mkdir()
        # Assert
        assert _is_embedded_package(app_dir) is False

    def test_manifest_embedded_package_true(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"embedded_package": True})
        # Assert
        assert _is_embedded_package(tmp_path) is True

    def test_manifest_embedded_package_false(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"embedded_package": False})
        # Assert
        assert _is_embedded_package(tmp_path) is False

    def test_manifest_missing_embedded_package_key(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"name": "myapp"})
        # Assert
        assert _is_embedded_package(tmp_path) is False


# ---------------------------------------------------------------------------
# Tests: _get_frontend_type
# ---------------------------------------------------------------------------


class TestGetFrontendType:
    def test_returns_frontend_type_from_manifest(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"frontend_type": "react"})
        # Assert
        assert _get_frontend_type(tmp_path) == "react"

    def test_returns_empty_string_when_not_set(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"name": "app"})
        # Assert
        assert _get_frontend_type(tmp_path) == ""

    def test_returns_empty_string_when_no_manifest(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert _get_frontend_type(tmp_path) == ""


# ---------------------------------------------------------------------------
# Tests: _get_app_name
# ---------------------------------------------------------------------------


class TestGetAppName:
    def test_returns_name_from_manifest(self, tmp_path):
        # Arrange
        # Act
        write_manifest(tmp_path, {"name": "my_awesome_app"})
        # Assert
        assert _get_app_name(tmp_path) == "my_awesome_app"

    def test_falls_back_to_dir_name(self, tmp_path):
        # No manifest — should return dir name
        # Arrange
        # Act
        # Assert
        assert _get_app_name(tmp_path) == tmp_path.name

    def test_invalid_manifest_json_falls_back_to_dir_name(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "manifest.json").write_text("{broken", encoding="utf-8")
        # Assert
        assert _get_app_name(tmp_path) == tmp_path.name


# ---------------------------------------------------------------------------
# Tests: validate_structure
# ---------------------------------------------------------------------------


class TestValidateStructure:
    def test_missing_directory_returns_error(self, tmp_path):
        # Arrange
        # Act
        errors = validate_structure(tmp_path / "nonexistent")
        # Assert
        assert any("does not exist" in e for e in errors)

    def test_embedded_app_only_requires_core_files(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert errors == []

    def test_missing_views_py_adds_error(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "views.py").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("views.py" in e for e in errors)

    def test_missing_urls_py_adds_error(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "urls.py").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("urls.py" in e for e in errors)

    def test_standalone_app_requires_apps_py(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "apps.py").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("apps.py" in e for e in errors)

    def test_standalone_app_requires_license(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "LICENSE").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("LICENSE" in e for e in errors)

    def test_standalone_app_requires_readme(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "README.md").unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("README.md" in e for e in errors)

    def test_standalone_app_requires_partial_template(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        partial = tmp_path / "templates" / "myapp" / "index_partial.html"
        partial.unlink()
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any("index_partial.html" in e for e in errors)

    def test_standalone_app_requires_agents_config(self, tmp_path):
        # Arrange
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / ".agents" / "agents.json").unlink()
        (tmp_path / ".agents" / "README.md").unlink() if (
            tmp_path / ".agents" / "README.md"
        ).exists() else None
        # Act
        errors = validate_structure(tmp_path)
        # Assert
        assert any(".agents" in e for e in errors)

    def test_react_frontend_skips_template_check(self, tmp_path):
        """React apps skip the template check."""
        # Arrange
        write_manifest(
            tmp_path,
            {
                "name": "react_app",
                "slug": "react-app",
                "label": "React App",
                "pip_package": "react-app",
                "icon": "fa",
                "license": "MIT",
                "frontend_type": "react",
                "dependencies": {"python": []},
            },
        )
        (tmp_path / "apps.py").touch()
        (tmp_path / "views.py").touch()
        (tmp_path / "urls.py").touch()
        (tmp_path / "LICENSE").write_text("MIT")
        (tmp_path / "README.md").write_text("# React App")
        agents_dir = tmp_path / ".agents"
        agents_dir.mkdir()
        (agents_dir / "agents.json").write_text("{}")
        # Act
        errors = validate_structure(tmp_path)
        # No error about missing template
        # Assert
        assert not any("index_partial.html" in e for e in errors)


# ---------------------------------------------------------------------------
# Tests: validate_security
# ---------------------------------------------------------------------------


class TestValidateSecurity:
    def test_clean_python_passes(self, tmp_path):
        # Arrange
        (tmp_path / "views.py").write_text(
            "from django.http import HttpResponse\n\ndef index(request): pass\n",
            encoding="utf-8",
        )
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert errors == []

    def test_subprocess_in_python_adds_error(self, tmp_path):
        # Arrange
        (tmp_path / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert any("subprocess" in e for e in errors)

    def test_os_system_in_python_adds_error(self, tmp_path):
        # Arrange
        (tmp_path / "views.py").write_text("os.system('ls')\n", encoding="utf-8")
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert any("os.system" in e for e in errors)

    def test_eval_in_python_adds_error(self, tmp_path):
        # Arrange
        (tmp_path / "utils.py").write_text(
            "result = eval(user_input)\n", encoding="utf-8"
        )
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert any("eval" in e for e in errors)

    def test_exec_in_python_adds_error(self, tmp_path):
        # Arrange
        (tmp_path / "views.py").write_text("exec(some_code)\n", encoding="utf-8")
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert any("exec" in e for e in errors)

    def test_pycache_excluded_errors_equals_case(self, tmp_path):
        # Arrange
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert errors == []

    def test_venv_excluded_errors_equals_case(self, tmp_path):
        # Arrange
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert errors == []

    def test_node_modules_excluded(self, tmp_path):
        # Arrange
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert errors == []

    def test_multiple_forbidden_patterns_accumulate(self, tmp_path):
        # Arrange
        (tmp_path / "views.py").write_text(
            "import subprocess\nos.system('ls')\neval(x)\n", encoding="utf-8"
        )
        # Act
        errors = validate_security(tmp_path)
        # Assert
        assert len(errors) >= 3


# ---------------------------------------------------------------------------
# Tests: validate_manifest
# ---------------------------------------------------------------------------


class TestValidateManifest:
    def test_missing_manifest_returns_error(self, tmp_path):
        # Arrange
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("not found" in e for e in errors)

    def test_invalid_json_returns_error(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text("{bad json}", encoding="utf-8")
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("not valid JSON" in e for e in errors)

    def test_non_object_manifest_returns_error(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text("[1, 2, 3]", encoding="utf-8")
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("must be a JSON object" in e for e in errors)

    def test_missing_required_keys_adds_errors(self, tmp_path):
        # Arrange
        (tmp_path / "manifest.json").write_text(json.dumps({"name": "myapp"}))
        # Act
        errors = validate_manifest(tmp_path)
        # All keys other than "name" should trigger errors
        # Assert
        assert len(errors) > 0

    def test_all_required_keys_present(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["slug"] = "my-app"
        data["label"] = "My App"
        data["icon"] = "fas fa-star"
        data["license"] = "MIT"
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert errors == []

    def test_name_without_app_suffix_adds_error(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "mybadname"  # no _app suffix
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("_app" in e or "-app" in e for e in errors)

    def test_name_with_app_suffix_accepted(self, tmp_path):
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        # Act
        name_errors = [e for e in errors if "_app" in e or "-app" in e]
        # Assert
        assert name_errors == []

    def test_version_key_forbidden_adds_error(self, tmp_path):
        # A hand-written 'version' key is forbidden — the version derives at
        # runtime from the installed 'pip_package' (importlib.metadata).
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["version"] = "1.0.0"
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("must NOT declare 'version'" in e for e in errors)

    def test_missing_pip_package_adds_error(self, tmp_path):
        # pip_package is required — the single source of truth for the version.
        # Arrange
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS if k != "pip_package"}
        data["name"] = "my_app"
        write_manifest(tmp_path, data)
        # Act
        errors = validate_manifest(tmp_path)
        # Assert
        assert any("pip_package" in e for e in errors)


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


# ---------------------------------------------------------------------------
# Tests: validate_dependencies
# ---------------------------------------------------------------------------


class TestValidateDependencies:
    def test_no_manifest_returns_no_errors(self, tmp_path):
        # Arrange
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert errors == []

    def test_missing_dependencies_field_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp"})
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("dependencies" in e for e in errors)

    def test_valid_dependencies_passes(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": ["django>=4.0"]}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert errors == []

    def test_dependencies_not_dict_adds_error(self, tmp_path):
        # Arrange
        write_manifest(tmp_path, {"name": "myapp", "dependencies": ["django"]})
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("must be a JSON object" in e for e in errors)

    def test_unknown_dependency_type_adds_error(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"alien": ["something"]}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("unknown dependency type" in e.lower() for e in errors)

    def test_dependency_value_not_list_adds_error(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": "django"}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("must be a list" in e for e in errors)

    def test_dependency_items_not_strings_adds_error(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": [1, 2, 3]}}
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert any("must be strings" in e for e in errors)

    def test_all_valid_dependency_types(self, tmp_path):
        # Arrange
        write_manifest(
            tmp_path,
            {
                "name": "myapp",
                "dependencies": {
                    "python": ["django"],
                    "system": ["git"],
                    "node": ["react"],
                    "r": ["ggplot2"],
                    "other": ["some-tool"],
                },
            },
        )
        # Act
        errors = validate_dependencies(tmp_path)
        # Assert
        assert errors == []


# ---------------------------------------------------------------------------
# Tests: full validate() pipeline
# ---------------------------------------------------------------------------


class TestFullValidate:
    def test_embedded_app_with_all_required_files_passes(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        # Act
        errors = validate(tmp_path)
        # Assert
        assert errors == []

    def test_missing_manifest_produces_errors(self, tmp_path):
        # Arrange
        (tmp_path / "views.py").touch()
        (tmp_path / "urls.py").touch()
        # Act
        errors = validate(tmp_path)
        # Assert
        assert len(errors) > 0

    def test_nonexistent_directory_produces_error(self, tmp_path):
        # Arrange
        # Act
        errors = validate(tmp_path / "does_not_exist")
        # Assert
        assert any("does not exist" in e for e in errors)

    def test_security_errors_included_in_full_validate(self, tmp_path):
        # Arrange
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "utils.py").write_text("import subprocess\n", encoding="utf-8")
        # Act
        errors = validate(tmp_path)
        # Assert
        assert any("subprocess" in e for e in errors)

    def test_embedded_skips_template_and_css_checks(self, tmp_path):
        """Embedded apps skip template and CSS validation."""
        # Arrange
        make_minimal_embedded_app(tmp_path)
        # Add a CSS file that would fail standalone checks
        (tmp_path / "bad.css").write_text("footer { display: none; }")
        errors = validate(tmp_path)
        # CSS check is still run for embedded — only template check is skipped
        # But embedded=True means validate_templates/validate_css skipped
        # Actually _is_embedded_package=True skips those two checks
        # Act
        css_errors = [e for e in errors if "footer" in e]
        # Assert
        assert css_errors == []  # CSS skipped for embedded


# ---------------------------------------------------------------------------
# Tests: constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_required_files_list_views_py_in_required_files(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "views.py" in REQUIRED_FILES

    def test_required_files_list_urls_py_in_required_files(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "urls.py" in REQUIRED_FILES

    def test_required_files_list_manifest_json_in_required_files(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "manifest.json" in REQUIRED_FILES


    def test_forbidden_patterns_list_subprocess_in_pattern_names(self):
        # Arrange
        # Arrange
        # Act
        pattern_names = [name for _, name in FORBIDDEN_PATTERNS]
        # Act
        # Assert
        # Assert
        assert "subprocess" in pattern_names

    def test_forbidden_patterns_list_eval_in_pattern_names(self):
        # Arrange
        # Arrange
        # Act
        pattern_names = [name for _, name in FORBIDDEN_PATTERNS]
        # Act
        # Assert
        # Assert
        assert "eval()" in pattern_names


    def test_manifest_required_keys_name_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "name" in MANIFEST_REQUIRED_KEYS

    def test_manifest_required_keys_slug_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "slug" in MANIFEST_REQUIRED_KEYS

    def test_manifest_required_keys_license_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert "license" in MANIFEST_REQUIRED_KEYS

    def test_manifest_required_keys_pip_package_in_manifest_required_keys(self):
        # Arrange
        # Act
        # Assert
        assert "pip_package" in MANIFEST_REQUIRED_KEYS


    def test_protected_selectors_len_protected_selectors_0(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert len(PROTECTED_SELECTORS) > 0

    def test_protected_selectors_any_stx_shell_in_s_for_s_in_protected_selectors(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert any("stx-shell" in s for s in PROTECTED_SELECTORS)


    def test_forbidden_block_overrides(self):
        # Arrange
        # Act
        # Assert
        assert len(FORBIDDEN_BLOCK_OVERRIDES) > 0


# EOF


# ─── mount-prefix safety ────────────────────────────────────────────────────
# Each test carries ONE assertion. These are arms of a single control, and a
# compound assert would let the first failure hide the rest: "the scan is
# broken", "the platform exemption is gone" and "embedded apps are skipped" are
# different defects with different fixes.

from scitex_app.appmaker._validate import validate_prefix_safety


def _app_with_js(tmp_path, source, name="app.js"):
    (tmp_path / name).write_text(source, encoding="utf-8")
    return validate_prefix_safety(tmp_path)


def test_a_root_absolute_request_url_is_reported(tmp_path):
    # Arrange — ignores the mount outright; the loud failure.
    source = 'fetch("/api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_a_relative_request_url_is_reported_as_inferred_base(tmp_path):
    # Arrange — the QUIET failure scitex-scholar measured: resolves against the
    # document URL, so it works at "/app/" and 404s at "/app".
    source = 'fetch("api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert "inferred-base" in found[0]


def test_a_platform_route_is_not_reported(tmp_path):
    # Arrange — hub owns this route, it lives at the server root, and prefixing
    # it BREAKS it. Flagging it would make the rule advise a regression.
    source = 'fetch("/platform/api/context/");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_an_absolute_external_url_is_not_reported(tmp_path):
    # Arrange — a different origin entirely; no mount applies.
    source = 'fetch("https://example.com/api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_url_bound_to_a_variable_before_fetching_is_reported(tmp_path):
    # Arrange — the shape that defeated the first draft. Calibrating against
    # scitex-scholar's shipped wheel found 1 of 3 known sites because the other
    # two bind the literal first and fetch it on the next line.
    source = 'const url = `/api/graph/network?doi=${doi}`;\nconst r = await fetch(url);'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_an_embedded_package_is_still_scanned(tmp_path):
    # Arrange — the wrong-population arm. validate() skips template/CSS checks
    # for embedded packages, and EVERY app carrying this defect is an embedded
    # `_django` package. A prefix rule inheriting that skip would pass forever
    # on exactly the apps it exists to measure.
    (tmp_path / "manifest.json").write_text('{"embedded_package": true}', encoding="utf-8")
    (tmp_path / "bundle.js").write_text('fetch("/api/search");', encoding="utf-8")
    # Act
    found = validate_prefix_safety(tmp_path)
    # Assert
    assert len(found) == 1


def test_build_output_directories_are_scanned_not_skipped(tmp_path):
    # Arrange — the committed built bundle is what SHIPS, and it can disagree
    # with the TS source (scitex-writer's offending anchor lives in one).
    # validator.py's SKIP_DIRS excludes "assets"/"dist"; this rule must not.
    assets = tmp_path / "static" / "writer" / "assets"
    assets.mkdir(parents=True)
    (assets / "index.js").write_text('fetch("/api/pdf?download=1");', encoding="utf-8")
    # Act
    found = validate_prefix_safety(tmp_path)
    # Assert
    assert len(found) == 1


def test_validate_does_not_report_prefix_findings_by_default(tmp_path):
    # Arrange — UNARMED is the shipped state. If this test ever fails, the rule
    # has silently started failing three peer repos' builds for work two of them
    # have not begun. This is the arm that protects them, not the code.
    from scitex_app.appmaker._validate import validate as _validate

    (tmp_path / "bundle.js").write_text('fetch("/api/search");', encoding="utf-8")
    # Act
    reported = _validate(tmp_path)
    # Assert
    assert not [e for e in reported if "does not resolve under an app mount" in e]


def test_validate_reports_prefix_findings_when_explicitly_armed(tmp_path):
    # Arrange — the other arm. Without it, "unarmed" above would also pass if
    # the check were wired up to nothing at all, which is the failure mode the
    # default-off flag most resembles.
    from scitex_app.appmaker._validate import validate as _validate

    (tmp_path / "bundle.js").write_text('fetch("/api/search");', encoding="utf-8")
    # Act
    reported = _validate(tmp_path, check_prefix_safety=True)
    # Assert
    assert [e for e in reported if "does not resolve under an app mount" in e]


# ─── template/CSS skip is keyed on frontend_type, not on the directory name ──
# Four arms, one assertion each — this is a truth table, and a compound assert
# would report "the table is wrong" instead of "this row is wrong".

def _embedded_app_with_bad_css(tmp_path, frontend_type):
    """An embedded app whose CSS breaks a workspace frame rule."""
    import json as _json

    app = tmp_path / "_django"
    app.mkdir()
    manifest = {"embedded_package": True}
    if frontend_type is not None:
        manifest["frontend_type"] = frontend_type
    (app / "manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")
    (app / "app.css").write_text("footer { display: none; }", encoding="utf-8")
    from scitex_app.appmaker._validate import validate_css

    return app, validate_css(app)


def test_the_css_rule_itself_fires_on_this_fixture(tmp_path):
    # Arrange — calibration. Every arm below asserts about whether validate_css
    # RUNS; that is meaningless unless the rule would fire on this input.
    _app, direct = _embedded_app_with_bad_css(tmp_path, "vanilla")
    # Act
    fired = len(direct)
    # Assert
    assert fired == 1


def test_an_embedded_non_react_app_is_css_validated(tmp_path):
    # Arrange — THE FIX. scitex-scholar's shape: embedded, frontend_type
    # "vanilla", hand-written CSS, previously skipped on the directory name.
    from scitex_app.appmaker._validate import validate as _validate

    app, _ = _embedded_app_with_bad_css(tmp_path, "vanilla")
    # Act
    reported = _validate(app)
    # Assert
    assert [e for e in reported if "footer" in e]


def test_an_embedded_react_app_is_still_skipped(tmp_path):
    # Arrange — compiled output is not hand-written and must not be linted for
    # frame conventions. This is the behaviour the old comment intended.
    from scitex_app.appmaker._validate import validate as _validate

    app, _ = _embedded_app_with_bad_css(tmp_path, "react")
    # Act
    reported = _validate(app)
    # Assert
    assert not [e for e in reported if "footer" in e]


def test_an_embedded_app_with_no_declared_frontend_type_is_still_skipped(tmp_path):
    # Arrange — conservative arm. An undeclared app may be a React build, and
    # guessing would invent findings on compiled output. Preserves today.
    from scitex_app.appmaker._validate import validate as _validate

    app, _ = _embedded_app_with_bad_css(tmp_path, None)
    # Act
    reported = _validate(app)
    # Assert
    assert not [e for e in reported if "footer" in e]


# ─── variable-prefixed URLs are a THIRD value, not a violation ──────────────
# 0.9.0 flagged `${STX_MOUNT}/api/x` — the exact code its own remediation text
# prescribes — because it collapsed "variable-prefixed" into "inferred-base".
# Reported by scitex-scholar against their CORRECTED tree.

def test_the_prescribed_mount_prefix_form_is_not_flagged(tmp_path):
    # Arrange — this IS the fix. Flagging it tells an app to undo correct work.
    source = "const url = `${STX_MOUNT}/api/search?${params}`;"
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_the_concatenated_mount_prefix_form_is_not_flagged(tmp_path):
    # Arrange — the other documented spelling, base + "/path". Both forms are
    # correct and both must pass; only the template one regressed in 0.9.0.
    source = 'fetch(STX_MOUNT + "/api/graph/health");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_url_prefixed_by_an_unknown_variable_is_not_reported(tmp_path):
    # Arrange — UNKNOWN, deliberately not collapsed into "violation". Whether
    # `someBase` holds the mount needs its value, which a scanner lacks.
    source = "const url = `${someBase}/api/search`;"
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert found == []


def test_a_genuinely_root_absolute_url_is_still_flagged(tmp_path):
    # Arrange — the arm that stops this fix becoming a blanket amnesty. Without
    # it, returning None for everything would satisfy all three tests above.
    source = 'fetch("/api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1


def test_a_genuinely_relative_url_is_still_flagged(tmp_path):
    # Arrange — same guard for the inferred-base class, which is the one the
    # fix narrowed. If narrowing went too far this is what catches it.
    source = 'fetch("api/search");'
    # Act
    found = _app_with_js(tmp_path, source)
    # Assert
    assert len(found) == 1
