"""The authorization verdict's `kind` strings must agree across packages AND
across languages.

INSTANCE TWO of the problem `test__django_marker_agreement.py` names at the end
of its own docstring, and that file is the worked example this one follows.

WHAT THIS GUARDS. `scitex_app.authz` PRODUCES the verdict; scitex-ui RENDERS it.
The value crosses the boundary as plain serialisable data, so scitex-ui does not
and must not import scitex-app — an app depends on both, and importing the SDK
from the presentation layer would point that arrow backwards. The cost of that
correct boundary is that the four strings are declared twice, in two languages,
in two repositories:

    scitex_app/authz.py                   ALLOWED = "allowed"           BUILDS
    scitex_ui .../ts/app/dim/types.ts     export const ALLOWED = ...    RENDERS

scitex-ui's own file says it plainly: "THE FOUR KIND STRINGS BELOW ARE A SECOND
COPY of scitex_app.authz's, in another repo, and nothing in this file can detect
a rename on their side."

WHY THE CHECK LIVES HERE AND NOT THERE. The breakage would appear in scitex-ui,
but the cause is a rename in scitex-app. A check nearest the rename PREVENTS;
a check at the far end DETECTS, after someone has already shipped. This one runs
where the edit happens.

HOW A DIVERGENCE FAILS, concretely, since "the strings differ" understates it.
A renamed kind arrives at the TypeScript switch as an unhandled value. scitex-ui
has an `assertNever` there, so a fifth or renamed kind is a compile error rather
than a silent branch — good, and it means the failure lands at THEIR build, from
OUR edit, with nothing in between to say why. That is the loop this closes.

WHAT THIS COSTS, said plainly, in the same terms as its sibling: it runs in the
CI job that installs scitex-ui for the reference example, and that job is
deliberately NOT a required context. So this is a RECORD, not a gate — visible
on a pull request, blocking nothing. Promoting it is tracked on
app-arm-the-example-leg-once-it-has-a-track-record. Saying so because a skipped
test and a passing test look identical in a summary line.

CALIBRATION, AND WHY THIS FILE IS EXPECTED TO BE RED WHEN IT LANDS.
`dim/types.ts` was merged in scitex-ui but has shipped in NO RELEASE — installed
scitex-ui is 0.19.1 and does not contain it. So on arrival this check hits its
own FILE-MISSING arm and FAILS. That is not a defect to work around; it is the
one observation that proves the check can fail for the reason it claims to.
scitex-ui is holding their release deliberately so that red is observable first,
in this order:

    1. this check lands on a branch
    2. RED is observed here            <- calibration
    3. scitex-ui releases
    4. re-run -> green -> merge

Their words, and the reason the order is theirs to keep rather than mine to
waive: "あなたの較正はあなたのものなので、私からは提案しません."
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scitex_app.authz import (
    ALLOWED,
    DENIED,
    DENIED_NOT_ENTITLED,
    DENIED_NOT_SIGNED_IN,
    VERDICT_KINDS,
)

from ._ts_agreement import installed_scitex_ui_root, strip_ts_comments

#: `export const ALLOWED = "allowed";` — anchored on the DECLARATION, never on
#: the bare string, so prose naming a kind cannot satisfy it. The name is
#: captured too: two constants that swapped values would otherwise agree as a
#: SET while meaning opposite things.
_TS_KIND_CONSTANT = re.compile(
    r"""export\s+const\s+([A-Z_][A-Z0-9_]*)\s*=\s*['"]([^'"]+)['"]"""
)

_TYPES_TS_RELPATH = Path("static") / "scitex_ui" / "ts" / "app" / "dim" / "types.ts"

#: The Python side, as a mapping rather than a set, for the reason above.
_PY_KINDS = {
    "ALLOWED": ALLOWED,
    "DENIED": DENIED,
    "DENIED_NOT_SIGNED_IN": DENIED_NOT_SIGNED_IN,
    "DENIED_NOT_ENTITLED": DENIED_NOT_ENTITLED,
}


def _read_ts_kinds(source: str) -> dict[str, str]:
    """Declared name -> value from TypeScript source, ignoring comments. Pure."""
    stripped = strip_ts_comments(source)
    found = dict(_TS_KIND_CONSTANT.findall(stripped))
    return {name: value for name, value in found.items() if name in _PY_KINDS}


@pytest.fixture
def ui_root() -> Path:
    """scitex-ui's installed root, skipping when it is absent.

    NOT INSTALLED IS THE ONLY LEGITIMATE SKIP; everything past here is signal.
    """
    root = installed_scitex_ui_root()
    if root is None:
        pytest.skip(
            "scitex-ui is not installed — the cross-package half of the "
            "verdict-kind contract was NOT checked by this run"
        )
    return root


@pytest.fixture
def types_ts_source(ui_root: Path) -> str:
    """The shipped dim/types.ts, FAILING if scitex-ui is installed without it.

    THREE-VALUED, and the middle value is the whole point. Returning None for
    both "scitex-ui absent" and "present but no longer shipping the file" would
    report a vanished subject as not-applicable. Those are different facts:
    the second means the wheel changed shape beneath a check that depends on
    it, and a check whose subject has disappeared must say so.

    THIS IS THE ARM THAT IS RED ON ARRIVAL — see the module docstring. It is
    the calibration, not a bug.
    """
    path = ui_root / _TYPES_TS_RELPATH
    assert path.exists(), (
        f"scitex-ui is installed but does not ship {_TYPES_TS_RELPATH} — "
        "either it has not been released yet (expected until scitex-ui ships "
        "the dim component) or the path moved. Update the path rather than "
        "deleting the check: four strings duplicated across two languages with "
        "no reader-side verification is how the contract silently diverges."
    )
    return path.read_text(encoding="utf-8")


def test_the_python_kind_values_are_the_contract_literals():
    """Calibration. Every comparison below is meaningless if this drifts.

    Asserts the literals rather than comparing two variables, so a rename that
    changed BOTH sides together still fails here and forces a deliberate
    decision — these strings are published in `data-stx-gate` page source and
    read by apps we do not control.
    """
    # Arrange
    # Act
    kinds = _PY_KINDS
    # Assert
    assert kinds == {
        "ALLOWED": "allowed",
        "DENIED": "denied",
        "DENIED_NOT_SIGNED_IN": "denied-because-not-signed-in",
        "DENIED_NOT_ENTITLED": "denied-because-not-entitled",
    }


def test_there_are_exactly_four_kinds():
    """A fifth kind must be a deliberate edit, not something that appears.

    The fifth ("auth not yet resolved") is REQUIRED the moment any verdict is
    fetched client-side, and must never be folded into not-signed-in — that
    asserts the user is signed out, which we would not know.
    """
    # Arrange
    # Act
    count = len(VERDICT_KINDS)
    # Assert
    assert count == 4


def test_the_typescript_kinds_agree_with_the_python_kinds(types_ts_source):
    # Arrange
    # Act
    ts_kinds = _read_ts_kinds(types_ts_source)
    # Assert
    assert ts_kinds == _PY_KINDS


def test_a_commented_out_declaration_is_not_read_as_a_declaration():
    # Arrange — measured: an anchored pattern still matches a commented-out
    # line and yields the stale value. Anchoring is not a defence.
    source = '// export const ALLOWED = "stale-value";'
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found == {}


def test_prose_naming_a_kind_is_not_read_as_a_declaration():
    # Arrange — a substring detector inverts on documentation: the file that
    # best explains the contract must not look like the file that declares it.
    source = "/* ALLOWED is the only kind that is not a denial. */"
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found == {}


def test_a_real_declaration_is_detected():
    # Arrange — the positive control. Without it the two negatives above are
    # vacuous: a detector that matches nothing at all would pass both.
    source = 'export const ALLOWED = "allowed";'
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found == {"ALLOWED": "allowed"}


def test_a_stale_comment_beside_real_code_reports_the_code():
    # Arrange — the arm people omit, and the one that separates "stripped
    # comments correctly" from "blunted the detector"; both look green.
    source = '// export const ALLOWED = "old";\nexport const ALLOWED = "allowed";'
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found == {"ALLOWED": "allowed"}


def test_a_swapped_value_is_detected_rather_than_agreeing_as_a_set():
    # Arrange — why the comparison is a MAPPING: these four values as a SET are
    # identical to the contract's while meaning the opposite thing.
    source = (
        'export const ALLOWED = "denied";\nexport const DENIED = "allowed";'
    )
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found != {"ALLOWED": "allowed", "DENIED": "denied"}
