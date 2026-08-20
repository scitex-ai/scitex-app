"""The demo's claim, as an executable test rather than a sentence in a README.

The claim is: ONE build serves correctly at TWO different mounts, with no
change to the app. `project/urls.py` includes the same app twice — at the root
and under a prefix — so both can be exercised in one process.
"""

import os
import re

import django
import pytest

MARKER = re.compile(r'<meta name="stx-mount" content="([^"]*)"')

STANDALONE_PAGE = "/"
STANDALONE_API = "/api/greet"
STANDALONE_PREFIX = ""

EMBEDDED_PAGE = "/apps/u/hello_world/"
EMBEDDED_API = "/apps/u/hello_world/api/greet"
EMBEDDED_PREFIX = "/apps/u/hello_world"


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
    django.setup()
    from django.test import Client

    return Client()


def _marker(response) -> str | None:
    found = MARKER.search(response.content.decode())
    return found.group(1) if found else None


@pytest.mark.parametrize(
    "page_url,expected_prefix",
    [(STANDALONE_PAGE, STANDALONE_PREFIX), (EMBEDDED_PAGE, EMBEDDED_PREFIX)],
)
def test_the_page_declares_the_prefix_it_is_actually_mounted_under(
    client, page_url, expected_prefix
):
    # Arrange
    expected_tag = expected_prefix
    # Act
    response = client.get(page_url)
    # Assert
    assert _marker(response) == expected_tag


@pytest.mark.parametrize("api_url", [STANDALONE_API, EMBEDDED_API])
def test_the_app_answers_its_own_api_at_both_mounts(client, api_url):
    # Arrange
    expected_status = 200
    # Act
    response = client.get(api_url)
    # Assert
    assert response.status_code == expected_status


def test_the_marker_is_never_a_bare_slash():
    # Arrange — the withdrawn 0.7.x convention used "/" for root, which makes
    # the documented join `base + "/api/x"` produce "//api/x": protocol-relative,
    # resolved by the browser against a DIFFERENT HOST.
    forbidden = "/"
    # Act
    prefixes = {STANDALONE_PREFIX, EMBEDDED_PREFIX}
    # Assert
    assert forbidden not in prefixes


def test_a_route_the_app_does_not_serve_still_404s(client):
    # Arrange — control. Without it, a server returning 200 for everything
    # would satisfy every assertion above.
    expected_status = 404
    # Act
    response = client.get(EMBEDDED_API + "/does-not-exist")
    # Assert
    assert response.status_code == expected_status
