"""Enforces SciTeX skills quality checklist §1–§4.
Canonical: src/scitex/_skills/general/21_scitex-package-quality-checklist.md
"""

from pathlib import Path
from scitex_dev._skills_quality_pytest import make_skill_quality_tests

test_skills_quality = make_skill_quality_tests(
    package_root=Path(__file__).resolve().parents[2]
)


def test_skills_quality_hook_is_wired():
    # Arrange
    hook = test_skills_quality
    # Act
    wired = callable(hook)
    # Assert
    assert wired
