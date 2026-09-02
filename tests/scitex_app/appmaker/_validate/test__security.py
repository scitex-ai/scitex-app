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
