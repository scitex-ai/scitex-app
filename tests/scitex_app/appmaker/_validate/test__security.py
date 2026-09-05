"""Tests for scitex_app/appmaker/_validate/_security.py."""

from __future__ import annotations


from scitex_app.appmaker._validate import (
    validate_security,
)


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


# EOF


def test_a_commented_out_forbidden_call_is_a_remediation_note(tmp_path):
    """A SECURITY rule reporting the file that documents the call it removed.

    Measured on the shipped 0.14.2: live `os.system("ls")` 1 finding,
    `# removed in 0.9: os.system("ls")` ALSO 1 finding.

    Found by asking the same question of every remaining rule rather than
    stopping at the three already known. Of the six unprobed, this was the only
    one that could have it: three parse JSON (no comments exist in JSON) and
    two read no text at all — excluded by MECHANISM, not by an unread zero.
    """
    # Arrange
    from scitex_app.appmaker._validate import validate_security

    (tmp_path / "m.py").write_text(
        'import os\n# removed in 0.9: os.system("ls")\n', encoding="utf-8"
    )
    # Act
    reported = validate_security(tmp_path)
    # Assert
    assert not reported


def test_a_live_forbidden_call_after_a_comment_is_still_reported(tmp_path):
    """The control. In a security rule, a stripper that hides too much is the
    worst version of this trade: the finding disappears and nothing says why."""
    # Arrange
    from scitex_app.appmaker._validate import validate_security

    (tmp_path / "m.py").write_text(
        'import os\n# note: os.system("x")\nos.system("ls")\n', encoding="utf-8"
    )
    # Act
    reported = validate_security(tmp_path)
    # Assert
    assert reported


def test_a_hash_inside_a_string_does_not_start_a_comment(tmp_path):
    """`S = "#"` is a value. Treating it as a comment start would blank the
    rest of the line and, on the next line, whatever the scanner needed."""
    # Arrange
    from scitex_app.appmaker._validate import validate_security

    (tmp_path / "m.py").write_text(
        'import os\nS = "#"\nos.system("ls")\n', encoding="utf-8"
    )
    # Act
    reported = validate_security(tmp_path)
    # Assert
    assert reported


def test_a_docstring_mentioning_a_forbidden_call_still_reports(tmp_path):
    """DELIBERATE, and stated so it is not mistaken for an oversight.

    A docstring is a string the module genuinely contains, not a comment the
    parser discards. Deciding which strings are prose is a different judgement
    needing its own calibration — and guessing is how the first of these
    defects got here. Same treatment as a `<pre>` block in HTML.
    """
    # Arrange
    from scitex_app.appmaker._validate import validate_security

    (tmp_path / "m.py").write_text(
        'def f():\n    """never call os.system here"""\n    return 1\n',
        encoding="utf-8",
    )
    # Act
    reported = validate_security(tmp_path)
    # Assert
    assert reported
