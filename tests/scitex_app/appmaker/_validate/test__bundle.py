"""Tests for scitex_app/appmaker/_validate/_bundle.py."""

from __future__ import annotations

from scitex_app.appmaker._validate import (
    DEFAULT_MAX_BUNDLE_SIZE,
    validate_bundle_size,
)


def test_a_small_app_is_under_the_limit(tmp_path):
    # Arrange
    (tmp_path / "app.js").write_text("x", encoding="utf-8")
    # Act
    found = validate_bundle_size(tmp_path)
    # Assert
    assert found == []


def test_exceeding_the_limit_is_reported(tmp_path):
    """Uses a tiny explicit limit rather than writing 50 MB to disk."""
    # Arrange
    (tmp_path / "app.js").write_text("x" * 2048, encoding="utf-8")
    # Act
    found = validate_bundle_size(tmp_path, max_bundle_size=1024)
    # Assert
    assert len(found) == 1


def test_node_modules_does_not_count_toward_the_limit(tmp_path):
    """A dev dependency tree is not what a user downloads."""
    # Arrange
    deps = tmp_path / "node_modules" / "dep"
    deps.mkdir(parents=True)
    (deps / "big.js").write_text("x" * 4096, encoding="utf-8")
    # Act
    found = validate_bundle_size(tmp_path, max_bundle_size=1024)
    # Assert
    assert found == []


def test_built_output_does_count_toward_the_limit(tmp_path):
    """The other arm — `dist` IS what ships, so it must be measured."""
    # Arrange
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "bundle.js").write_text("x" * 4096, encoding="utf-8")
    # Act
    found = validate_bundle_size(tmp_path, max_bundle_size=1024)
    # Assert
    assert len(found) == 1


def test_the_default_limit_is_fifty_megabytes(tmp_path):
    # Arrange
    # Act
    limit_mb = DEFAULT_MAX_BUNDLE_SIZE / (1024 * 1024)
    # Assert
    assert limit_mb == 50


# EOF
