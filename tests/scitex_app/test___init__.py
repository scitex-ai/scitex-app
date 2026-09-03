"""`import scitex_app` must not drag a web framework in with it.

Mirrors src/scitex_app/__init__.py: the eager re-export that makes this property
fragile lives there, so the constraint is tested against the module that carries
it. (Named test__import_purity.py first; the project-structure audit rejected it
as an orphan test with no matching source file, and the rule was right — the
better name was the one that says which module the property belongs to.)

WHY THIS EXISTS. 0.11.0 added `from ._standalone import hosts_to_allow` to the
package root, so `_standalone` — the module that runs Django servers — now
imports EAGERLY on every `import scitex_app`. It keeps its Django imports inside
its functions, so the property holds; nothing enforced that it kept holding.

WHY IT MATTERS TO SOMEONE ELSE. scitex-scholar made scitex-app a HARD dependency
of their server extra and retired the "scitex-app not installed" fallback, on
the correct reasoning that a fallback which still starts but silently drops the
ALLOWED_HOSTS derivation is worse than a loud failure. That trade is only sound
while importing this package is cheap and side-effect-free: an import-time
regression here is now an OUTAGE there, not a downgrade.

WHY THE EXISTING GATE DOES NOT COVER IT. The import-smoke CI leg installs the
extras, so Django is present in that environment and the leg passes whether or
not the property holds. A gate that cannot fail for the case that matters is not
a gate — hence a subprocess, which makes the assertion independent of what
happens to be installed in the runner.
"""

from __future__ import annotations

import subprocess
import sys


def _import_and_report(module_name: str) -> str:
    """Import scitex_app in a FRESH interpreter, report if `module_name` came too.

    A subprocess rather than an in-process import: by the time this test runs,
    pytest has already imported Django for other tests, so `sys.modules` in this
    process says nothing about what importing scitex_app costs.
    """
    code = (
        "import sys; import scitex_app; "
        f"print({module_name!r} in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def test_importing_the_package_does_not_import_django():
    """The property scholar's hard import depends on."""
    # Arrange
    # Act
    pulled = _import_and_report("django")
    # Assert
    assert pulled == "False"


def test_importing_the_package_does_not_import_scitex_ui():
    """Same reasoning, and the one the CLI's headless claim rests on."""
    # Arrange
    # Act
    pulled = _import_and_report("scitex_ui")
    # Assert
    assert pulled == "False"


def test_the_public_name_is_available_without_importing_django():
    """Control: the two above would also pass if the import had simply failed.

    Without this, deleting `hosts_to_allow` from the package root would turn
    both assertions green — the strongest possible way to not import Django is
    to not import anything.
    """
    # Arrange
    code = "import scitex_app; print(callable(scitex_app.hosts_to_allow))"
    # Act
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    # Assert
    assert out.stdout.strip() == "True"


# EOF
