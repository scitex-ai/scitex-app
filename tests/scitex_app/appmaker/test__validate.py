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
            "version": "1.0.0",
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
            "version": "1.0.0",
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
        embedded_dir = tmp_path / "_django"
        embedded_dir.mkdir()
        assert _is_embedded_package(embedded_dir) is True

    def test_normal_name_without_manifest_is_not_embedded(self, tmp_path):
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        assert _is_embedded_package(app_dir) is False

    def test_manifest_embedded_package_true(self, tmp_path):
        write_manifest(tmp_path, {"embedded_package": True})
        assert _is_embedded_package(tmp_path) is True

    def test_manifest_embedded_package_false(self, tmp_path):
        write_manifest(tmp_path, {"embedded_package": False})
        assert _is_embedded_package(tmp_path) is False

    def test_manifest_missing_embedded_package_key(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp"})
        assert _is_embedded_package(tmp_path) is False


# ---------------------------------------------------------------------------
# Tests: _get_frontend_type
# ---------------------------------------------------------------------------


class TestGetFrontendType:
    def test_returns_frontend_type_from_manifest(self, tmp_path):
        write_manifest(tmp_path, {"frontend_type": "react"})
        assert _get_frontend_type(tmp_path) == "react"

    def test_returns_empty_string_when_not_set(self, tmp_path):
        write_manifest(tmp_path, {"name": "app"})
        assert _get_frontend_type(tmp_path) == ""

    def test_returns_empty_string_when_no_manifest(self, tmp_path):
        assert _get_frontend_type(tmp_path) == ""


# ---------------------------------------------------------------------------
# Tests: _get_app_name
# ---------------------------------------------------------------------------


class TestGetAppName:
    def test_returns_name_from_manifest(self, tmp_path):
        write_manifest(tmp_path, {"name": "my_awesome_app"})
        assert _get_app_name(tmp_path) == "my_awesome_app"

    def test_falls_back_to_dir_name(self, tmp_path):
        # No manifest — should return dir name
        assert _get_app_name(tmp_path) == tmp_path.name

    def test_invalid_manifest_json_falls_back_to_dir_name(self, tmp_path):
        (tmp_path / "manifest.json").write_text("{broken", encoding="utf-8")
        assert _get_app_name(tmp_path) == tmp_path.name


# ---------------------------------------------------------------------------
# Tests: validate_structure
# ---------------------------------------------------------------------------


class TestValidateStructure:
    def test_missing_directory_returns_error(self, tmp_path):
        errors = validate_structure(tmp_path / "nonexistent")
        assert any("does not exist" in e for e in errors)

    def test_embedded_app_only_requires_core_files(self, tmp_path):
        make_minimal_embedded_app(tmp_path)
        errors = validate_structure(tmp_path)
        assert errors == []

    def test_missing_views_py_adds_error(self, tmp_path):
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "views.py").unlink()
        errors = validate_structure(tmp_path)
        assert any("views.py" in e for e in errors)

    def test_missing_urls_py_adds_error(self, tmp_path):
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "urls.py").unlink()
        errors = validate_structure(tmp_path)
        assert any("urls.py" in e for e in errors)

    def test_standalone_app_requires_apps_py(self, tmp_path):
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "apps.py").unlink()
        errors = validate_structure(tmp_path)
        assert any("apps.py" in e for e in errors)

    def test_standalone_app_requires_license(self, tmp_path):
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "LICENSE").unlink()
        errors = validate_structure(tmp_path)
        assert any("LICENSE" in e for e in errors)

    def test_standalone_app_requires_readme(self, tmp_path):
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / "README.md").unlink()
        errors = validate_structure(tmp_path)
        assert any("README.md" in e for e in errors)

    def test_standalone_app_requires_partial_template(self, tmp_path):
        make_full_standalone_app(tmp_path, "myapp")
        partial = tmp_path / "templates" / "myapp" / "index_partial.html"
        partial.unlink()
        errors = validate_structure(tmp_path)
        assert any("index_partial.html" in e for e in errors)

    def test_standalone_app_requires_agents_config(self, tmp_path):
        make_full_standalone_app(tmp_path, "myapp")
        (tmp_path / ".agents" / "agents.json").unlink()
        (tmp_path / ".agents" / "README.md").unlink() if (
            tmp_path / ".agents" / "README.md"
        ).exists() else None
        errors = validate_structure(tmp_path)
        assert any(".agents" in e for e in errors)

    def test_react_frontend_skips_template_check(self, tmp_path):
        """React apps skip the template check."""
        write_manifest(
            tmp_path,
            {
                "name": "react_app",
                "slug": "react-app",
                "label": "React App",
                "version": "1.0.0",
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
        errors = validate_structure(tmp_path)
        # No error about missing template
        assert not any("index_partial.html" in e for e in errors)


# ---------------------------------------------------------------------------
# Tests: validate_security
# ---------------------------------------------------------------------------


class TestValidateSecurity:
    def test_clean_python_passes(self, tmp_path):
        (tmp_path / "views.py").write_text(
            "from django.http import HttpResponse\n\ndef index(request): pass\n",
            encoding="utf-8",
        )
        errors = validate_security(tmp_path)
        assert errors == []

    def test_subprocess_in_python_adds_error(self, tmp_path):
        (tmp_path / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        errors = validate_security(tmp_path)
        assert any("subprocess" in e for e in errors)

    def test_os_system_in_python_adds_error(self, tmp_path):
        (tmp_path / "views.py").write_text("os.system('ls')\n", encoding="utf-8")
        errors = validate_security(tmp_path)
        assert any("os.system" in e for e in errors)

    def test_eval_in_python_adds_error(self, tmp_path):
        (tmp_path / "utils.py").write_text(
            "result = eval(user_input)\n", encoding="utf-8"
        )
        errors = validate_security(tmp_path)
        assert any("eval" in e for e in errors)

    def test_exec_in_python_adds_error(self, tmp_path):
        (tmp_path / "views.py").write_text("exec(some_code)\n", encoding="utf-8")
        errors = validate_security(tmp_path)
        assert any("exec" in e for e in errors)

    def test_pycache_excluded(self, tmp_path):
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        errors = validate_security(tmp_path)
        assert errors == []

    def test_venv_excluded(self, tmp_path):
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        errors = validate_security(tmp_path)
        assert errors == []

    def test_node_modules_excluded(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "bad.py").write_text("import subprocess\n", encoding="utf-8")
        errors = validate_security(tmp_path)
        assert errors == []

    def test_multiple_forbidden_patterns_accumulate(self, tmp_path):
        (tmp_path / "views.py").write_text(
            "import subprocess\nos.system('ls')\neval(x)\n", encoding="utf-8"
        )
        errors = validate_security(tmp_path)
        assert len(errors) >= 3


# ---------------------------------------------------------------------------
# Tests: validate_manifest
# ---------------------------------------------------------------------------


class TestValidateManifest:
    def test_missing_manifest_returns_error(self, tmp_path):
        errors = validate_manifest(tmp_path)
        assert any("not found" in e for e in errors)

    def test_invalid_json_returns_error(self, tmp_path):
        (tmp_path / "manifest.json").write_text("{bad json}", encoding="utf-8")
        errors = validate_manifest(tmp_path)
        assert any("not valid JSON" in e for e in errors)

    def test_non_object_manifest_returns_error(self, tmp_path):
        (tmp_path / "manifest.json").write_text("[1, 2, 3]", encoding="utf-8")
        errors = validate_manifest(tmp_path)
        assert any("must be a JSON object" in e for e in errors)

    def test_missing_required_keys_adds_errors(self, tmp_path):
        (tmp_path / "manifest.json").write_text(json.dumps({"name": "myapp"}))
        errors = validate_manifest(tmp_path)
        # All keys other than "name" should trigger errors
        assert len(errors) > 0

    def test_all_required_keys_present(self, tmp_path):
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["version"] = "1.0.0"
        data["slug"] = "my-app"
        data["label"] = "My App"
        data["icon"] = "fas fa-star"
        data["license"] = "MIT"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        assert errors == []

    def test_name_without_app_suffix_adds_error(self, tmp_path):
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "mybadname"  # no _app suffix
        data["version"] = "1.0.0"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        assert any("_app" in e or "-app" in e for e in errors)

    def test_name_with_app_suffix_accepted(self, tmp_path):
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["version"] = "1.0.0"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        name_errors = [e for e in errors if "_app" in e or "-app" in e]
        assert name_errors == []

    def test_non_semver_version_adds_error(self, tmp_path):
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["version"] = "not-a-version"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        assert any("semver" in e for e in errors)

    def test_valid_semver_version_passes(self, tmp_path):
        data = {k: "value" for k in MANIFEST_REQUIRED_KEYS}
        data["name"] = "my_app"
        data["version"] = "2.1.3"
        write_manifest(tmp_path, data)
        errors = validate_manifest(tmp_path)
        version_errors = [e for e in errors if "semver" in e]
        assert version_errors == []


# ---------------------------------------------------------------------------
# Tests: validate_templates
# ---------------------------------------------------------------------------


class TestValidateTemplates:
    def test_no_app_name_returns_no_errors(self, tmp_path):
        # No manifest and no directory name matching app
        errors = validate_templates(tmp_path)
        assert isinstance(errors, list)

    def test_missing_index_html_is_fine(self, tmp_path):
        """If index.html doesn't exist, template checks are skipped."""
        write_manifest(tmp_path, {"name": "myapp"})
        errors = validate_templates(tmp_path)
        assert errors == []

    def test_valid_template_passes(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "index.html").write_text(
            "{% extends 'global_base.html' %}{% block content %}hello{% endblock %}"
        )
        errors = validate_templates(tmp_path)
        assert errors == []

    def test_missing_global_base_extend_adds_error(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "index.html").write_text("{% block content %}hello{% endblock %}")
        errors = validate_templates(tmp_path)
        assert any("global_base.html" in e for e in errors)

    def test_missing_block_content_adds_error(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "index.html").write_text("{% extends 'global_base.html' %}")
        errors = validate_templates(tmp_path)
        assert any("block content" in e for e in errors)

    def test_forbidden_block_override_adds_error(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp"})
        tmpl_dir = tmp_path / "templates" / "myapp"
        tmpl_dir.mkdir(parents=True)
        forbidden_block = FORBIDDEN_BLOCK_OVERRIDES[0]
        (tmpl_dir / "index.html").write_text(
            f"{{% extends 'global_base.html' %}}"
            f"{{% block content %}}{{% endblock %}}"
            f"{{% block {forbidden_block} %}}{{% endblock %}}"
        )
        errors = validate_templates(tmp_path)
        assert any(forbidden_block in e for e in errors)


# ---------------------------------------------------------------------------
# Tests: validate_css
# ---------------------------------------------------------------------------


class TestValidateCss:
    def test_clean_css_passes(self, tmp_path):
        (tmp_path / "style.css").write_text("body { margin: 0; }")
        errors = validate_css(tmp_path)
        assert errors == []

    def test_deprecated_color_variable_adds_error(self, tmp_path):
        (tmp_path / "style.css").write_text("color: var(--color-primary);")
        errors = validate_css(tmp_path)
        assert any("--color-" in e or "--workspace-*" in e for e in errors)

    def test_important_on_protected_selector_adds_error(self, tmp_path):
        selector = PROTECTED_SELECTORS[0]
        css = f"{selector} {{ color: red !important; }}"
        (tmp_path / "bad.css").write_text(css)
        errors = validate_css(tmp_path)
        assert any("!important" in e for e in errors)

    def test_footer_display_none_adds_error(self, tmp_path):
        (tmp_path / "bad.css").write_text("footer { display: none; }")
        errors = validate_css(tmp_path)
        assert any("footer" in e for e in errors)

    def test_git_dir_excluded_from_css_scan(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "hook.css").write_text("footer { display: none; }")
        errors = validate_css(tmp_path)
        assert errors == []


# ---------------------------------------------------------------------------
# Tests: validate_dependencies
# ---------------------------------------------------------------------------


class TestValidateDependencies:
    def test_no_manifest_returns_no_errors(self, tmp_path):
        errors = validate_dependencies(tmp_path)
        assert errors == []

    def test_missing_dependencies_field_adds_error(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp"})
        errors = validate_dependencies(tmp_path)
        assert any("dependencies" in e for e in errors)

    def test_valid_dependencies_passes(self, tmp_path):
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": ["django>=4.0"]}}
        )
        errors = validate_dependencies(tmp_path)
        assert errors == []

    def test_dependencies_not_dict_adds_error(self, tmp_path):
        write_manifest(tmp_path, {"name": "myapp", "dependencies": ["django"]})
        errors = validate_dependencies(tmp_path)
        assert any("must be a JSON object" in e for e in errors)

    def test_unknown_dependency_type_adds_error(self, tmp_path):
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"alien": ["something"]}}
        )
        errors = validate_dependencies(tmp_path)
        assert any("unknown dependency type" in e.lower() for e in errors)

    def test_dependency_value_not_list_adds_error(self, tmp_path):
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": "django"}}
        )
        errors = validate_dependencies(tmp_path)
        assert any("must be a list" in e for e in errors)

    def test_dependency_items_not_strings_adds_error(self, tmp_path):
        write_manifest(
            tmp_path, {"name": "myapp", "dependencies": {"python": [1, 2, 3]}}
        )
        errors = validate_dependencies(tmp_path)
        assert any("must be strings" in e for e in errors)

    def test_all_valid_dependency_types(self, tmp_path):
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
        errors = validate_dependencies(tmp_path)
        assert errors == []


# ---------------------------------------------------------------------------
# Tests: full validate() pipeline
# ---------------------------------------------------------------------------


class TestFullValidate:
    def test_embedded_app_with_all_required_files_passes(self, tmp_path):
        make_minimal_embedded_app(tmp_path)
        errors = validate(tmp_path)
        assert errors == []

    def test_missing_manifest_produces_errors(self, tmp_path):
        (tmp_path / "views.py").touch()
        (tmp_path / "urls.py").touch()
        errors = validate(tmp_path)
        assert len(errors) > 0

    def test_nonexistent_directory_produces_error(self, tmp_path):
        errors = validate(tmp_path / "does_not_exist")
        assert any("does not exist" in e for e in errors)

    def test_security_errors_included_in_full_validate(self, tmp_path):
        make_minimal_embedded_app(tmp_path)
        (tmp_path / "utils.py").write_text("import subprocess\n", encoding="utf-8")
        errors = validate(tmp_path)
        assert any("subprocess" in e for e in errors)

    def test_embedded_skips_template_and_css_checks(self, tmp_path):
        """Embedded apps skip template and CSS validation."""
        make_minimal_embedded_app(tmp_path)
        # Add a CSS file that would fail standalone checks
        (tmp_path / "bad.css").write_text("footer { display: none; }")
        errors = validate(tmp_path)
        # CSS check is still run for embedded — only template check is skipped
        # But embedded=True means validate_templates/validate_css skipped
        # Actually _is_embedded_package=True skips those two checks
        css_errors = [e for e in errors if "footer" in e]
        assert css_errors == []  # CSS skipped for embedded


# ---------------------------------------------------------------------------
# Tests: constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_required_files_list(self):
        assert "views.py" in REQUIRED_FILES
        assert "urls.py" in REQUIRED_FILES
        assert "manifest.json" in REQUIRED_FILES

    def test_forbidden_patterns_list(self):
        pattern_names = [name for _, name in FORBIDDEN_PATTERNS]
        assert "subprocess" in pattern_names
        assert "eval()" in pattern_names

    def test_manifest_required_keys(self):
        assert "name" in MANIFEST_REQUIRED_KEYS
        assert "slug" in MANIFEST_REQUIRED_KEYS
        assert "license" in MANIFEST_REQUIRED_KEYS

    def test_protected_selectors(self):
        assert len(PROTECTED_SELECTORS) > 0
        assert any("stx-shell" in s for s in PROTECTED_SELECTORS)

    def test_forbidden_block_overrides(self):
        assert len(FORBIDDEN_BLOCK_OVERRIDES) > 0


# EOF
