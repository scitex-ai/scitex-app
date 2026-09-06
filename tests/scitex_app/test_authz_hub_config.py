#!/usr/bin/env python3
"""Hub configuration: the default is the decision.

Operator ruling 2026-09-06, via scitex-hub:
「ハブなしを規定にしてもらってで、うるさく失敗するヒントは出すでいいと思います」
— make no-hub the default, and fail noisily with hints.

These tests exist because a DEFAULT is the easiest thing in a codebase to
change by accident and the hardest to notice: nothing fails when it flips, the
suite stays green, and an install that was contacting nobody starts contacting
somebody. The assertion that `hub_url({})` is None is the whole ruling.
"""

from __future__ import annotations

import logging

import pytest

from scitex_app.authz import (
    DENIED,
    HUB_URL_ENV,
    _reset_hub_hint_for_testing,
    denied_no_hub,
    hub_url,
)


@pytest.fixture(autouse=True)
def _fresh_hint_latch():
    """The hint fires once per PROCESS, so without this the second test to
    assert it would pass or fail depending on test order — a result that
    depends on something other than the code under test."""
    _reset_hub_hint_for_testing()
    yield
    _reset_hub_hint_for_testing()


def test_an_unconfigured_install_has_no_hub():
    """THE RULING, as one assertion. An empty environment yields None, not a
    URL — so a self-hosted install that configures nothing contacts nobody."""
    # Arrange
    env: dict[str, str] = {}
    # Act
    resolved = hub_url(env)
    # Assert
    assert resolved is None


def test_a_configured_hub_is_returned():
    """The control. Without it, `None` is equally consistent with "the default
    is none" and "this function never returns anything"."""
    # Arrange
    env = {HUB_URL_ENV: "https://hub.example.org"}
    # Act
    resolved = hub_url(env)
    # Assert
    assert resolved == "https://hub.example.org"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "ws"])
def test_a_blank_value_means_explicitly_no_hub(raw):
    """Setting the variable to empty is how an operator says "none" in a shell
    profile or compose file where deleting the line is awkward. Treating that
    as a malformed URL would punish the person being explicit."""
    # Arrange
    env = {HUB_URL_ENV: raw}
    # Act
    resolved = hub_url(env)
    # Assert
    assert resolved is None


def test_surrounding_whitespace_is_not_part_of_the_url():
    """A trailing newline from a heredoc or a `.env` file is not a hostname."""
    # Arrange
    env = {HUB_URL_ENV: "  https://hub.example.org\n"}
    # Act
    resolved = hub_url(env)
    # Assert
    assert resolved == "https://hub.example.org"


# ---------------------------------------------------------------------------
# THE NOISY HINT — and the two surfaces it must keep apart.
# ---------------------------------------------------------------------------


def test_the_no_hub_verdict_carries_nothing():
    """The verdict crosses into page source as `data-stx-gate` and is read by
    someone not authenticated to this deployment, so it stays payload-free even
    though the ruling asked for hints. The hint goes elsewhere — see below."""
    # Arrange
    expected = DENIED
    # Act
    verdict = denied_no_hub(action="open the library")
    # Assert
    assert (verdict.kind, verdict.to_dict()) == (expected, {"kind": DENIED})


def test_the_hint_reaches_the_developer_channel(caplog):
    """THE OTHER HALF OF THE RULING, and the reason the test above is not the
    whole story: `denied` says nothing, and the person who can fix it is told
    anyway — on the log, naming the variable to set."""
    # Arrange
    caplog.set_level(logging.WARNING, logger="scitex_app.authz")
    # Act
    denied_no_hub(action="open the library")
    # Assert
    assert HUB_URL_ENV in caplog.text


def test_the_hint_names_the_action_that_was_denied(caplog):
    """"Something was denied" sends the reader looking; naming the first one
    tells them which feature they are missing. Asserted separately from the
    variable name because they fail for different reasons."""
    # Arrange
    caplog.set_level(logging.WARNING, logger="scitex_app.authz")
    # Act
    denied_no_hub(action="open the library")
    # Assert
    assert "open the library" in caplog.text


def test_the_hint_fires_once_not_once_per_render(caplog):
    """`can()` is called per render, so an unconditional warning would fire
    hundreds of times on one page. A log nobody can read is silence with extra
    steps — which is the failure mode the ruling was trying to avoid, arrived
    at from the other direction."""
    # Arrange
    caplog.set_level(logging.WARNING, logger="scitex_app.authz")
    # Act
    for _ in range(50):
        denied_no_hub(action="render a pane")
    # Assert
    assert caplog.text.count(HUB_URL_ENV) == 1


def test_the_verdict_is_still_returned_after_the_hint_is_spent(caplog):
    """THE CONTROL ON THE LATCH. Suppressing the hint must not suppress the
    ANSWER — a once-per-process guard that also made later calls return
    something different would be a gate that changes behaviour based on how
    many times it has run."""
    # Arrange
    caplog.set_level(logging.WARNING, logger="scitex_app.authz")
    denied_no_hub(action="first")
    # Act
    later = denied_no_hub(action="second")
    # Assert
    assert later.kind == DENIED


def test_the_variable_name_follows_the_owner_prefix_rule():
    """PINS THE LITERAL, because every other test here asserts against the
    CONSTANT and would pass through a silent rename.

    The name is a published contract the moment this ships, and it encodes the
    operator's naming rule (2026-09-06): prefix by WHERE the thing is
    configured, not by what it points at. This variable is set on the APP's
    install and names hub as its subject, so `SCITEX_APP_HUB_URL` — his stated
    reason being 「どこに何が設定されてるのかわからない」, that a name must tell you
    where to go looking.

    Renaming it after release is a MIGRATION — alias, DeprecationWarning, one
    release — not an edit. This test is the thing that makes that deliberate
    rather than accidental.
    """
    # Arrange
    expected = "SCITEX_APP_HUB_URL"
    # Act
    actual = HUB_URL_ENV
    # Assert
    assert actual == expected
