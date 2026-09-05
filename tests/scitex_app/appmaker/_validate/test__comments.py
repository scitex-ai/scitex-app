#!/usr/bin/env python3
"""Tests for scitex_app/appmaker/_validate/_comments.py."""

from __future__ import annotations

from scitex_app.appmaker._validate._comments import (
    strip_css_comments,
    strip_html_comments,
    strip_js_comments,
)


def test_a_css_comment_is_blanked_to_the_same_length():
    """BLANK, NEVER DELETE. Every rule downstream reports line and column
    numbers against the file on disk; deleting a comment shifts everything
    after it and each finding then points at the wrong place."""
    # Arrange
    source = "/* hide */\nbody{color:red}\n"
    # Act
    stripped = strip_css_comments(source)
    # Assert
    assert stripped == "          \nbody{color:red}\n"


def test_a_css_comment_marker_inside_a_string_does_not_open_a_comment():
    """`content: "/*"` is a value, not a comment. Treating it as one blanks
    every live declaration up to the next quote — turning a false POSITIVE
    into a false NEGATIVE, where the finding disappears and nothing says why.
    That trade is the one thing this module refuses."""
    # Arrange
    source = 'a{content:"/*"}\nfooter{display:none}\n'
    # Act
    stripped = strip_css_comments(source)
    # Assert — the live rule after it survives untouched.
    assert "footer{display:none}" in stripped


def test_an_unterminated_css_comment_swallows_the_rest_rather_than_nothing():
    """A file that opens `/*` and never closes it IS entirely commented out
    from that point, per CSS parsing. Stopping at the first newline instead
    would report declarations no browser applies."""
    # Arrange
    source = "body{color:red}\n/* oops\nfooter{display:none}\n"
    # Act
    stripped = strip_css_comments(source)
    # Assert
    assert "footer" not in stripped


def test_html_and_js_strippers_are_still_reachable_from_here():
    """They moved from `_prefix` when the same blindness was found in three
    more rules. This module is now the declared home; `_prefix` re-exports
    them because they were public there first."""
    # Arrange
    source = "<!-- x -->"
    # Act
    both = (strip_html_comments(source), strip_js_comments("// x"))
    # Assert
    assert both == ("          ", "    ")
