"""The two things every SciTeX app view has to get right.

1. Emit the mount marker, derived by the SDK rather than by hand.
2. Answer your own API under a relative route, so `include()` can mount the
   whole app anywhere.
"""

from django.http import JsonResponse
from django.shortcuts import render
from scitex_app.embed import mount_prefix
from scitex_ui.mount import MOUNT_DECLARED_KEY, MOUNT_PREFIX_KEY


def page(request):
    """Render the shell with the mount marker in it.

    `mount_prefix` is passed `view_path=""` because this view is registered at
    the app root in urls.py. If you move it to `path("editor/", ...)`, pass
    `view_path="editor/"` — `request.path` is the mount prefix PLUS the route
    the view occupies, and only the view knows its own route. Get it wrong and
    the SDK raises rather than handing back a plausible-looking prefix.
    """
    prefix = mount_prefix(request, view_path="")
    return render(
        request,
        "hello_world/page.html",
        {
            # scitex-ui's shell includes its own marker partial, which reads
            # these two keys. The value comes from scitex-app because the mount
            # contract is scitex-app's; the keys are scitex-ui's because the
            # template is theirs. Both packages agree on the value — verified
            # across the published wheels, not assumed.
            MOUNT_PREFIX_KEY: prefix,
            MOUNT_DECLARED_KEY: True,
        },
    )


def greet(request):
    """An app-owned API route. Registered relatively, so it moves with the app."""
    return JsonResponse({"greeting": "hello, world", "mounted_at": mount_prefix(request, view_path="api/greet")})
