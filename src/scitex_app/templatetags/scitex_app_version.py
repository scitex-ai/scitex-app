from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def scitex_app_version() -> str:
    """Render the scitex-app SDK's installed version.

    ``{% load scitex_app_version %}`` then ``{% scitex_app_version %}``.
    Reads importlib.metadata via the shared accessor; degrades to the labelled
    local fallback for an editable checkout or a missing dist. This is the tag
    a leaf app's shell (or host chrome) uses to show the version continuously
    without hardcoding it.
    """
    from scitex_app._django import package_version

    return package_version()
