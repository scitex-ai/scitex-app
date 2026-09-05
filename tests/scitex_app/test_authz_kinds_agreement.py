"""The authorization verdict's `kind` strings must agree across packages AND
across languages.

INSTANCE TWO of the problem `test__django_marker_agreement.py` names at the end
of its own docstring, and that file is the worked example this one follows.

WHAT THIS GUARDS. `scitex_app.authz` PRODUCES the verdict; scitex-ui RENDERS it.
The value crosses the boundary as plain serialisable data, so scitex-ui does not
and must not import scitex-app — an app depends on both, and importing the SDK
from the presentation layer would point that arrow backwards. The cost of that
correct boundary is that the five strings are declared twice, in two languages,
in two repositories:

    scitex_app/authz.py                   ALLOWED = "allowed"           BUILDS
    scitex_ui .../ts/app/dim/types.ts     export const ALLOWED = ...    RENDERS

scitex-ui's own file said it plainly: "THE FOUR KIND STRINGS BELOW ARE A SECOND
COPY of scitex_app.authz's, in another repo, and nothing in this file can detect
a rename on their side."

THAT SENTENCE IS GONE FROM THEIR FILE AS OF 0.20.2, and how it went is the
point. Adding the fifth kind would have shipped a comment saying FOUR on the
very file this check reads — a stale comment DENYING the count beside the code
that sets it. They caught it only because a control they ran for an unrelated
reason made them open the real file. Quoted here as history, and kept rather
than deleted because the near-miss is the useful part.

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
deliberately NOT a required context. That job had to be TAUGHT to run this
file -- it previously ran only the example's own tests, so the sibling check
skipped in CI for a week while its docstring claimed otherwise. So this is a RECORD, not a gate — visible
on a pull request, blocking nothing. Promoting it is tracked on
app-arm-the-example-leg-once-it-has-a-track-record. Saying so because a skipped
test and a passing test look identical in a summary line.

CALIBRATION — DONE, AND RECORDED AS HISTORY RATHER THAN DELETED.
When this file landed, `dim/types.ts` was merged in scitex-ui but shipped in NO
RELEASE (installed scitex-ui was 0.19.1), so the check hit its own FILE-MISSING
arm and FAILED. That red was not a defect to work around; it was the one
observation proving the check can fail for the reason it claims to. It ran in
this order, all four steps observed:

    1. this check lands on a branch
    2. RED is observed here            <- calibration
    3. scitex-ui releases
    4. re-run -> green -> merge

THE FIFTH KIND WENT THE SAME WAY, and the ORDER IS THE LESSON. This check reads
the INSTALLED scitex-ui, so:

    TS first (their wheel ships UNRESOLVED, then Python)   this side went SILENT
    Python first                                           RED, and this side
                                                           CANNOT clear it —
                                                           it waits on someone
                                                           else's release

THAT SILENCE WAS A HOLE, AND IT IS NOW CLOSED. `_read_ts_kinds` used to filter
the far side to names Python already declares, so an ADDITION over there was
invisible here — measured on the shipped 0.20.2 wheel, TS 5 against Python 4
compared EQUAL. The whole fifth-kind rollout ran through that window watched by
hand rather than by this file.

It now reads the `VerdictKind` UNION instead, which is where TypeScript itself
says what the set is, and both directions are calibrated:

    TS 5 vs Python 4   DETECTED   (was MISSED)
    TS 5 vs Python 5   agrees     (the control, without which "not equal"
                                   proves nothing)

TS-first remains the right ORDER — a red nobody can clear is worse than one you
can — but the reason is now only sequencing, not a gap somebody must remember to
watch.

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
    UNRESOLVED,
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
    "UNRESOLVED": UNRESOLVED,
}


#: `export type VerdictKind = | typeof ALLOWED | typeof DENIED ...;`
#: THE UNION IS THE AUTHORITATIVE SET, and reading it is what makes this check
#: two-directional. See _read_ts_kinds.
_TS_KIND_UNION = re.compile(
    r"export\s+type\s+VerdictKind\s*=\s*(?P<body>[^;]+);", re.S
)
_TS_UNION_MEMBER = re.compile(r"typeof\s+([A-Z_][A-Z0-9_]*)")


#: The five kinds as scitex-ui 0.20.2 actually ships them — copied from the
#: wheel, not written from memory. Local fixtures below mutate THIS rather than
#: inventing a shape, so a control cannot pass by describing a file that does
#: not exist. (Measured: a peer spent an evening on a "0 hits" result for a
#: kind spelling they had reconstructed from memory and that was never real.)
_TS_SOURCE_FIVE = """\
export const ALLOWED = "allowed";
export const DENIED = "denied";
export const DENIED_NOT_SIGNED_IN = "denied-because-not-signed-in";
export const DENIED_NOT_ENTITLED = "denied-because-not-entitled";
export const UNRESOLVED = "unresolved";

export type VerdictKind =
  | typeof ALLOWED
  | typeof DENIED
  | typeof DENIED_NOT_SIGNED_IN
  | typeof DENIED_NOT_ENTITLED
  | typeof UNRESOLVED;
"""


def _read_ts_kinds(source: str) -> dict[str, str]:
    """Declared name -> value from TypeScript source, ignoring comments. Pure.

    READS THE UNION, NOT THE LOOSE CONSTANTS, and that distinction is the whole
    fix. The previous implementation ended with

        return {n: v for n, v in found.items() if n in _PY_KINDS}

    which filtered the far side to names THIS side already declares — so a kind
    added in TypeScript and absent in Python was silently dropped, and the
    comparison passed. Measured 2026-09-05 on the shipped scitex-ui 0.20.2
    wheel, not on a fixture: TS 5 / Python 4 PASSED. The check detected renames
    and removals and was blind to additions, while its own docstring opened with
    "must AGREE", which is a symmetric word.

    Dropping that filter needs somewhere authoritative to draw the set FROM,
    otherwise any unrelated `export const` in the file reads as a kind.
    TypeScript already has that place: the `VerdictKind` union. Measured on the
    same wheel — `types.ts` exports exactly five `const`s, all kinds, plus
    types/interfaces the constant pattern cannot match — so today the two
    agree; tomorrow the union is what decides.

    Returns the union's members mapped to the VALUES their constants declare.
    A union member with no constant maps to None, which cannot equal any Python
    kind, so it fails LOUDLY rather than vanishing.
    """
    stripped = strip_ts_comments(source)
    values = dict(_TS_KIND_CONSTANT.findall(stripped))

    union = _TS_KIND_UNION.search(stripped)
    if union is None:
        # NOT an empty result: the subject changed shape and this check can no
        # longer read what it claims to. Falling back to the constants would
        # quietly restore the one-directional behaviour this function exists to
        # end, so return them UNFILTERED and let the comparison fail.
        return values

    members = _TS_UNION_MEMBER.findall(union.group("body"))
    return {name: values.get(name) for name in members}


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
        "deleting the check: five strings duplicated across two languages with "
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
        "UNRESOLVED": "unresolved",
    }


def test_the_count_here_matches_the_count_asserted_in_test_authz():
    """A SECOND copy of the count assertion, and it nearly went stale.

    This file used to declare `test_there_are_exactly_four_kinds` too, with the
    same body as the one in test_authz.py. Adding the fifth kind, I swept for
    every "four" that had to become "five" with `rg '\bfour\b'` — and that
    sweep CANNOT SEE `exactly_four_kinds`, because `_` is a word character, so
    there is no word boundary before `four` inside an identifier.

    So the sweep reported the file clean and the test failed on the first real
    run: `assert 5 == 4`. Two lessons worth keeping over deleting this:

      - a word-boundary search for prose is blind to the same word inside
        identifiers, which is exactly where a count assertion lives;
      - the same stale-count hazard scitex-ui hit in their own types.ts
        (a comment saying FOUR beside the code that sets five) was live in
        THIS repo at the same moment, in a test name.

    Kept as an agreement between the two files rather than a third independent
    count, so a future change has one number to update here and the reason is
    attached to it.
    """
    # Arrange
    expected = len(_PY_KINDS)
    # Act
    count = len(VERDICT_KINDS)
    # Assert
    assert count == expected


def test_the_typescript_kinds_agree_with_the_python_kinds(types_ts_source):
    # Arrange
    # Act
    ts_kinds = _read_ts_kinds(types_ts_source)
    # Assert
    assert ts_kinds == _PY_KINDS


def test_a_kind_added_only_in_typescript_is_detected():
    """THE ARM THAT DID NOT EXIST, and whose absence made this file's opening
    sentence — "must AGREE" — a claim it could not back.

    Measured on the shipped scitex-ui 0.20.2 wheel before the fix: a TypeScript
    side declaring five kinds against a Python side declaring four came back
    EQUAL, because the reader filtered the far side to names this side already
    had. Renames and removals were caught; additions were invisible.

    That is not a hypothetical direction. It is exactly what a peer adding a
    kind ahead of us looks like, and the rollout of the fifth kind ran in that
    state deliberately, watched by hand rather than by this test.
    """
    # Arrange — a sixth kind, present in the union and its constant, that this
    # package has never heard of.
    source = _TS_SOURCE_FIVE.replace(
        'export const UNRESOLVED = "unresolved";',
        'export const UNRESOLVED = "unresolved";\n'
        'export const DEFERRED = "deferred";',
    ).replace("  | typeof UNRESOLVED;", "  | typeof UNRESOLVED\n  | typeof DEFERRED;")
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found != _PY_KINDS


def test_the_five_shipped_kinds_still_agree():
    """Calibration for the arm above: without this, "not equal" proves nothing,
    because a reader that returned garbage would also satisfy it."""
    # Arrange
    # Act
    found = _read_ts_kinds(_TS_SOURCE_FIVE)
    # Assert
    assert found == _PY_KINDS


def test_a_constant_outside_the_union_is_not_read_as_a_kind():
    """Why the union rather than the loose constants.

    Dropping the old name filter needs an authoritative place to draw the set
    from, or any unrelated `export const` in the file becomes a kind. The union
    is where TypeScript itself says what the kinds are.
    """
    # Arrange — a constant that is deliberately NOT a verdict kind.
    source = _TS_SOURCE_FIVE.replace(
        'export const ALLOWED = "allowed";',
        'export const ATTR_GATE = "data-stx-gate";\n'
        'export const ALLOWED = "allowed";',
    )
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert "ATTR_GATE" not in found


def test_a_union_member_with_no_constant_fails_rather_than_vanishing():
    """A dangling member must not be silently dropped — it maps to None, which
    equals no Python kind, so the comparison goes red instead of quiet."""
    # Arrange
    source = _TS_SOURCE_FIVE.replace('export const DENIED = "denied";', "")
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found["DENIED"] is None


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
    # Arrange — why the comparison is a MAPPING: these values as a SET are
    # identical to the contract's while meaning the opposite thing.
    source = (
        'export const ALLOWED = "denied";\nexport const DENIED = "allowed";'
    )
    # Act
    found = _read_ts_kinds(source)
    # Assert
    assert found != {"ALLOWED": "allowed", "DENIED": "denied"}
