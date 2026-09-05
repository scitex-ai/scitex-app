"""Python source scanning — forbidden patterns in an app's own .py files."""

from __future__ import annotations

from ._comments import strip_python_comments
import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    (r"\bsubprocess\b", "subprocess"),
    (r"\bos\.system\b", "os.system"),
    (r"\beval\s*\(", "eval()"),
    (r"\bexec\s*\(", "exec()"),
    (r"\b__import__\b", "__import__"),
]


def validate_security(app_dir: str | Path) -> list[str]:
    """Scan Python files for forbidden patterns."""
    errors = []
    root = Path(app_dir)

    excluded_dirs = {"__pycache__", ".git", "scitex", "node_modules", ".venv", "venv"}
    for py_file in root.rglob("*.py"):
        if excluded_dirs & set(py_file.relative_to(root).parts):
            continue
        try:
            raw = py_file.read_text(encoding="utf-8", errors="replace")
            # A commented-out `os.system` is the file EXPLAINING that it no
            # longer calls it. Measured on 0.14.2: live 1, commented-out also
            # 1 — a security rule reporting its own remediation note.
            content = strip_python_comments(raw)
        except OSError:
            continue
        relpath = py_file.relative_to(root)
        for pattern, name in FORBIDDEN_PATTERNS:
            if re.search(pattern, content):
                errors.append(f"Forbidden pattern '{name}' found in {relpath}")

    return errors


# EOF
