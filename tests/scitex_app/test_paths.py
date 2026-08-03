#!/usr/bin/env python3
# Timestamp: 2026-03-16
# File: tests/test__paths.py

"""Tests for scitex_app.paths module."""

from __future__ import annotations


import os

import pytest

from scitex_app.paths import (
    find_partial_template,
    get_base_dir,
    parse_dev_module_name,
    resolve_manifest,
    resolve_static_dir,
    resolve_template_dir,
    resolve_user_project_dir,
    resolve_published_project_dir,
    safe_iterdir,
    validate_project_structure,
)


# ---------------------------------------------------------------------------
# get_base_dir
# ---------------------------------------------------------------------------


@pytest.fixture
def base_dir_env():
    """Set/restore the SCITEX_BASE_DIR env var around a test.

    Real env-var manipulation (not a mock): yields a setter; whatever
    was there before is restored on teardown so tests don't leak state.
    """
    saved = os.environ.get("SCITEX_BASE_DIR")

    def _set(value):
        if value is None:
            os.environ.pop("SCITEX_BASE_DIR", None)
        else:
            os.environ["SCITEX_BASE_DIR"] = str(value)

    try:
        yield _set
    finally:
        if saved is None:
            os.environ.pop("SCITEX_BASE_DIR", None)
        else:
            os.environ["SCITEX_BASE_DIR"] = saved


class TestGetBaseDir:
    def test_explicit_arg_get_base_dir_tmp_path_tmp_path_resolve(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert get_base_dir(tmp_path) == tmp_path.resolve()

    def test_env_var_get_base_dir_tmp_path_resolve(self, tmp_path, base_dir_env):
        # Arrange
        base_dir_env(tmp_path)
        # Act
        result = get_base_dir()
        # Assert
        assert result == tmp_path.resolve()

    def test_explicit_arg_overrides_env(self, tmp_path, base_dir_env):
        # Arrange
        other = tmp_path / "other"
        other.mkdir()
        base_dir_env(tmp_path)
        # Act
        result = get_base_dir(other)
        # Assert
        assert result == other.resolve()

    def test_raises_when_no_source(self, base_dir_env):
        # Arrange
        base_dir_env(None)
        # Act
        ctx = pytest.raises(ValueError, match="No base directory")
        # Assert
        with ctx:
            get_base_dir()


# ---------------------------------------------------------------------------
# resolve_user_project_dir
# ---------------------------------------------------------------------------


class TestResolveUserProjectDir:
    def test_existing_dir_result_equals_proj_2(self, tmp_path):
        # Arrange
        proj = tmp_path / "data" / "users" / "alice" / "proj" / "myapp"
        proj.mkdir(parents=True)
        # Act
        result = resolve_user_project_dir("alice", "myapp", base_dir=tmp_path)
        # Assert
        assert result == proj

    def test_missing_dir_result_is_none_2(self, tmp_path):
        # Arrange
        # Act
        result = resolve_user_project_dir("alice", "noapp", base_dir=tmp_path)
        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# resolve_published_project_dir
# ---------------------------------------------------------------------------


class TestResolvePublishedProjectDir:
    def test_existing_dir_result_equals_proj_2(self, tmp_path):
        # Arrange
        proj = tmp_path / "data" / "projects" / "myproj"
        proj.mkdir(parents=True)
        # Act
        result = resolve_published_project_dir("myproj", base_dir=tmp_path)
        # Assert
        assert result == proj

    def test_missing_dir_result_is_none_2(self, tmp_path):
        # Arrange
        # Act
        result = resolve_published_project_dir("nope", base_dir=tmp_path)
        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# resolve_manifest
# ---------------------------------------------------------------------------


class TestResolveManifest:
    def test_reads_valid_manifest(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "manifest.json").write_text('{"name": "test"}')
        # Assert
        assert resolve_manifest(tmp_path) == {"name": "test"}

    def test_missing_manifest_resolve_manifest_tmp_path(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert resolve_manifest(tmp_path) == {}

    def test_invalid_json_resolve_manifest_tmp_path(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "manifest.json").write_text("{broken")
        # Assert
        assert resolve_manifest(tmp_path) == {}


# ---------------------------------------------------------------------------
# find_partial_template
# ---------------------------------------------------------------------------


class TestFindPartialTemplate:
    def test_flat_layout_find_partial_template_tmp_path_tpl(self, tmp_path):
        # Arrange
        tpl = tmp_path / "index_partial.html"
        # Act
        tpl.write_text("<div>flat</div>")
        # Assert
        assert find_partial_template(tmp_path) == tpl

    def test_nested_layout_find_partial_template_tmp_path_nested(self, tmp_path):
        # Arrange
        nested = tmp_path / "myapp" / "index_partial.html"
        nested.parent.mkdir()
        # Act
        nested.write_text("<div>nested</div>")
        # Assert
        assert find_partial_template(tmp_path) == nested

    def test_missing_find_partial_template_tmp_path_is_none(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert find_partial_template(tmp_path) is None

    def test_nonexistent_dir_result_equals_case(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert find_partial_template(tmp_path / "nope") is None


# ---------------------------------------------------------------------------
# resolve_template_dir / resolve_static_dir
# ---------------------------------------------------------------------------


class TestResolveDirs:
    def test_template_dir_exists(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "templates").mkdir()
        # Assert
        assert resolve_template_dir(tmp_path) == tmp_path / "templates"

    def test_template_dir_missing(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert resolve_template_dir(tmp_path) is None

    def test_static_dir_exists(self, tmp_path):
        # Arrange
        # Act
        (tmp_path / "static").mkdir()
        # Assert
        assert resolve_static_dir(tmp_path) == tmp_path / "static"

    def test_static_dir_missing(self, tmp_path):
        # Arrange
        # Act
        # Assert
        assert resolve_static_dir(tmp_path) is None


# ---------------------------------------------------------------------------
# parse_dev_module_name
# ---------------------------------------------------------------------------


class TestParseDevModuleName:
    def test_valid_parse_dev_module_name_dev_alice_myapp_alice_myapp(self):
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("dev__alice__myapp") == ("alice", "myapp")

    def test_not_dev_prefix(self):
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("writer") is None

    def test_wrong_parts_count_parse_dev_module_name_dev_only_is_none(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("dev__only") is None

    def test_wrong_parts_count_parse_dev_module_name_dev_a_b_c_is_none(self):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert parse_dev_module_name("dev__a__b__c") is None


# ---------------------------------------------------------------------------
# safe_iterdir
# ---------------------------------------------------------------------------


class TestSafeIterdir:
    def test_skips_hidden_len_result_is_1(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        # Act
        result = list(safe_iterdir(tmp_path))
        # Act
        # Assert
        # Assert
        assert len(result) == 1

    def test_skips_hidden_result_0_name_visible(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        # Act
        result = list(safe_iterdir(tmp_path))
        # Act
        # Assert
        # Assert
        assert result[0].name == "visible"

    def test_nonexistent_dir_result_equals_case(self, tmp_path):
        # Arrange
        # Act
        result = list(safe_iterdir(tmp_path / "nope"))
        # Assert
        assert result == []


# ---------------------------------------------------------------------------
# validate_project_structure
# ---------------------------------------------------------------------------


class TestValidateProjectStructure:
    def test_valid_flat_ok_is_true(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "index_partial.html").write_text("<div/>")
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert ok is True

    def test_valid_flat_msg_equals_ok(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "index_partial.html").write_text("<div/>")
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert msg == "ok"

    def test_missing_templates_ok_is_false(self, tmp_path):
        # Arrange
        # Arrange
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert ok is False

    def test_missing_templates_templates_in_msg(self, tmp_path):
        # Arrange
        # Arrange
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert "templates" in msg

    def test_missing_partial_ok_is_false(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert ok is False

    def test_missing_partial_index_partial_in_msg(self, tmp_path):
        # Arrange
        # Arrange
        (tmp_path / "templates").mkdir()
        # Act
        ok, msg = validate_project_structure(tmp_path)
        # Act
        # Assert
        # Assert
        assert "index_partial" in msg

    def test_nonexistent_ok_is_false(self, tmp_path):
        # Arrange
        # Act
        ok, msg = validate_project_structure(tmp_path / "nope")
        # Assert
        assert ok is False


# ---------------------------------------------------------------------------
# Path containment
#
# Every refusal below is PAIRED with a positive control, because a negative
# assertion passes for free when the thing it looks for cannot exist at all.
# For the symlink cases the control is stronger than "a valid input still
# works": it first proves the escape target really is reachable and readable
# THROUGH the planted link, so "it was refused" is a statement about the
# containment check and not about a link that never resolved anywhere.
# ---------------------------------------------------------------------------


@pytest.fixture
def escape_target(tmp_path):
    """A real, readable directory tree OUTSIDE the base dir.

    Returns ``(root, outside)``. ``root`` is the base dir handed to the
    functions under test; ``outside`` is its sibling, holding content that a
    successful traversal would expose.
    """
    root = tmp_path / "root"
    (root / "data" / "users").mkdir(parents=True)
    (root / "data" / "projects").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    return root, outside


class TestParseDevModuleNameRefusesUnsafeSegments:
    def test_dotdot_segments_are_refused(self):
        # Arrange
        module_name = "dev__..__.."
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result is None

    def test_slash_in_segment_is_refused(self):
        # Arrange
        module_name = "dev__a/b__c"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result is None

    def test_backslash_in_segment_is_refused(self):
        # Arrange
        module_name = "dev__alice__..\\..\\etc"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result is None

    def test_nul_byte_in_segment_is_refused(self):
        # Arrange
        module_name = "dev__alice__myapp\0.png"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result is None

    def test_single_dot_segment_is_refused(self):
        # Arrange
        module_name = "dev__.__myapp"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result is None

    def test_empty_segment_is_refused(self):
        # Arrange
        module_name = "dev____myapp"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result is None

    def test_positive_control_ordinary_name_still_parses(self):
        # Arrange
        module_name = "dev__alice__myapp"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result == ("alice", "myapp")

    def test_positive_control_dotted_name_still_parses(self):
        # Arrange
        module_name = "dev__alice.b__my.app"
        # Act
        result = parse_dev_module_name(module_name)
        # Assert
        assert result == ("alice.b", "my.app")


class TestResolveUserProjectDirContainment:
    def test_dotdot_owner_and_repo_are_refused(self, escape_target):
        # Arrange
        root, _outside = escape_target
        # Act
        result = resolve_user_project_dir("..", "..", base_dir=root)
        # Assert
        assert result is None

    def test_traversal_owner_reaching_another_tenant_is_refused(
        self, escape_target
    ):
        # Arrange
        root, _outside = escape_target
        victim = root / "data" / "users" / "bob" / "proj" / "myapp"
        victim.mkdir(parents=True)
        assert victim.is_dir()
        # Act
        result = resolve_user_project_dir("alice/../bob", "myapp", base_dir=root)
        # Assert
        assert result is None

    def test_positive_control_that_tenant_is_reachable_under_its_own_name(
        self, escape_target
    ):
        # Arrange
        root, _outside = escape_target
        victim = root / "data" / "users" / "bob" / "proj" / "myapp"
        victim.mkdir(parents=True)
        # Act
        result = resolve_user_project_dir("bob", "myapp", base_dir=root)
        # Assert
        assert result == victim

    def test_absolute_owner_is_refused(self, escape_target):
        # Arrange
        root, outside = escape_target
        (outside / "proj" / "myapp").mkdir(parents=True)
        # Act
        result = resolve_user_project_dir(str(outside), "myapp", base_dir=root)
        # Assert
        assert result is None

    def test_symlinked_owner_dir_pointing_outside_root_is_refused(
        self, escape_target
    ):
        # Arrange
        root, outside = escape_target
        target = outside / "alice" / "proj" / "myapp"
        target.mkdir(parents=True)
        (target / "manifest.json").write_text('{"secret": "leaked"}')
        link = root / "data" / "users" / "alice"
        link.symlink_to(outside / "alice", target_is_directory=True)
        assert link.resolve() == (outside / "alice").resolve()
        assert not str(link.resolve()).startswith(str(root.resolve()))
        assert (link / "proj" / "myapp").is_dir()
        assert "leaked" in (link / "proj" / "myapp" / "manifest.json").read_text()
        # Act
        result = resolve_user_project_dir("alice", "myapp", base_dir=root)
        # Assert
        assert result is None

    def test_positive_control_real_dir_in_same_layout_still_resolves(
        self, escape_target
    ):
        # Arrange
        root, _outside = escape_target
        proj = root / "data" / "users" / "alice" / "proj" / "myapp"
        proj.mkdir(parents=True)
        # Act
        result = resolve_user_project_dir("alice", "myapp", base_dir=root)
        # Assert
        assert result == proj


class TestResolvePublishedProjectDirContainment:
    def test_traversal_slug_reaching_the_users_tree_is_refused(
        self, escape_target
    ):
        # Arrange
        root, _outside = escape_target
        victim = root / "data" / "users" / "alice" / "proj" / "myapp"
        victim.mkdir(parents=True)
        assert victim.is_dir()
        # Act
        result = resolve_published_project_dir(
            "../users/alice/proj/myapp", base_dir=root
        )
        # Assert
        assert result is None

    def test_symlinked_slug_pointing_outside_root_is_refused(
        self, escape_target
    ):
        # Arrange
        root, outside = escape_target
        target = outside / "published"
        target.mkdir()
        (target / "manifest.json").write_text('{"secret": "leaked"}')
        link = root / "data" / "projects" / "myproj"
        link.symlink_to(target, target_is_directory=True)
        assert link.resolve() == target.resolve()
        assert not str(link.resolve()).startswith(str(root.resolve()))
        assert "leaked" in (link / "manifest.json").read_text()
        # Act
        result = resolve_published_project_dir("myproj", base_dir=root)
        # Assert
        assert result is None

    def test_positive_control_real_slug_still_resolves(self, escape_target):
        # Arrange
        root, _outside = escape_target
        proj = root / "data" / "projects" / "myproj"
        proj.mkdir(parents=True)
        # Act
        result = resolve_published_project_dir("myproj", base_dir=root)
        # Assert
        assert result == proj


class TestProjectSubdirContainment:
    def test_symlinked_templates_dir_pointing_outside_is_refused(self, tmp_path):
        # Arrange
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "index_partial.html").write_text("<div>other tenant</div>")
        link = project_dir / "templates"
        link.symlink_to(outside, target_is_directory=True)
        assert link.is_dir()
        assert "other tenant" in (link / "index_partial.html").read_text()
        # Act
        result = resolve_template_dir(project_dir)
        # Assert
        assert result is None

    def test_positive_control_real_templates_dir_still_resolves(self, tmp_path):
        # Arrange
        project_dir = tmp_path / "proj"
        (project_dir / "templates").mkdir(parents=True)
        # Act
        result = resolve_template_dir(project_dir)
        # Assert
        assert result == project_dir / "templates"

    def test_symlinked_static_dir_pointing_outside_is_refused(self, tmp_path):
        # Arrange
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "id_rsa").write_text("PRIVATE KEY")
        link = project_dir / "static"
        link.symlink_to(outside, target_is_directory=True)
        assert link.is_dir()
        assert "PRIVATE KEY" in (link / "id_rsa").read_text()
        # Act
        result = resolve_static_dir(project_dir)
        # Assert
        assert result is None

    def test_positive_control_real_static_dir_still_resolves(self, tmp_path):
        # Arrange
        project_dir = tmp_path / "proj"
        (project_dir / "static").mkdir(parents=True)
        # Act
        result = resolve_static_dir(project_dir)
        # Assert
        assert result == project_dir / "static"

    def test_symlinked_manifest_pointing_outside_is_refused(self, tmp_path):
        # Arrange
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.json"
        secret.write_text('{"secret": "leaked"}')
        link = project_dir / "manifest.json"
        link.symlink_to(secret)
        assert link.is_file()
        assert "leaked" in link.read_text()
        # Act
        result = resolve_manifest(project_dir)
        # Assert
        assert result == {}

    def test_positive_control_real_manifest_still_reads(self, tmp_path):
        # Arrange
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "manifest.json").write_text('{"name": "test"}')
        # Act
        result = resolve_manifest(project_dir)
        # Assert
        assert result == {"name": "test"}


class TestFindPartialTemplateContainment:
    def test_traversal_filename_is_refused(self, tmp_path):
        # Arrange
        templates_dir = tmp_path / "proj" / "templates"
        templates_dir.mkdir(parents=True)
        outsider = tmp_path / "outsider.html"
        outsider.write_text("<div>outside</div>")
        assert (templates_dir / ".." / ".." / "outsider.html").is_file()
        # Act
        result = find_partial_template(templates_dir, "../../outsider.html")
        # Assert
        assert result is None

    def test_positive_control_custom_filename_still_found(self, tmp_path):
        # Arrange
        templates_dir = tmp_path / "proj" / "templates"
        templates_dir.mkdir(parents=True)
        custom = templates_dir / "outsider.html"
        custom.write_text("<div>inside</div>")
        # Act
        result = find_partial_template(templates_dir, "outsider.html")
        # Assert
        assert result == custom

    def test_symlinked_subdir_pointing_outside_is_refused(self, tmp_path):
        # Arrange
        templates_dir = tmp_path / "proj" / "templates"
        templates_dir.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "index_partial.html").write_text("<div>other tenant</div>")
        link = templates_dir / "evil"
        link.symlink_to(outside, target_is_directory=True)
        assert link.is_dir()
        assert "other tenant" in (link / "index_partial.html").read_text()
        # Act
        result = find_partial_template(templates_dir)
        # Assert
        assert result is None

    def test_positive_control_real_nested_subdir_still_found(self, tmp_path):
        # Arrange
        templates_dir = tmp_path / "proj" / "templates"
        nested = templates_dir / "myapp" / "index_partial.html"
        nested.parent.mkdir(parents=True)
        nested.write_text("<div>nested</div>")
        # Act
        result = find_partial_template(templates_dir)
        # Assert
        assert result == nested


# EOF
