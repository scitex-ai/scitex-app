#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ONE FINDING, AS A RECORD — so a consumer never has to substring-match it.

WHY THIS EXISTS. scitex-hub, the only consumer of `validate_css_canonical`,
reported on 2026-09-06:

    "To act on one programmatically a consumer must parse 'path:line: message'
     and then keyword-match the message — which is how I ended up mis-bucketing
     316 findings into 'other' on my first pass, using exactly the substring
     reasoning this rule exists to discourage."

A rule whose entire subject is "do not decide what a selector means from a
substring" was handing its output as prose and forcing its only consumer to
decide from a substring. The defect is not that the prose was bad; it is that
prose was the interface.

`rule` is the field to branch on. It is a STABLE SLUG and changing one is a
breaking change to consumers, the same as renaming a JSON key — the message
text is free to be reworded, and that is the point of separating them.

`tier` is which tier of the workspace rule fired, as a string rather than an
int because "2a" and "2b" are real tiers and 2 is not a number here.

`__str__` reproduces the exact line this rule has emitted since 0.15.2, so a
consumer that formats findings for a human keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CssFinding"]


@dataclass(frozen=True)
class CssFinding:
    """One finding. FROZEN: a finding is a record of what was read, and a
    consumer that can edit it can make the report disagree with the tree."""

    rule: str
    tier: str
    path: str
    line: int
    selector: str
    message: str
    subject: str = ""

    def __post_init__(self) -> None:
        # A finding with no position is the thing this record exists to
        # prevent: hub could not act on findings because they had to be
        # parsed, and an unparseable-BY-CONSTRUCTION finding is worse.
        if self.line < 1:
            raise ValueError(
                f"line must be 1-based, got {self.line!r} for rule "
                f"{self.rule!r} in {self.path!r}"
            )
        if not self.rule:
            raise ValueError(
                "rule is the field consumers branch on; an empty one forces "
                "them back to matching the message text"
            )
        if not self.path:
            raise ValueError("path is required — a finding names a file")

    def __str__(self) -> str:
        """The exact line emitted since 0.15.2. Kept for humans, and so this
        change adds a shape without taking the old one away."""
        return f"{self.path}:{self.line}: {self.message}"


# EOF
