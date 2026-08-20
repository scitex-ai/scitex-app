"""The whole point of the mount contract, in one file.

Both lines below include the SAME app at DIFFERENT prefixes, with no change to
the app itself. Visit either and the page works, because the server tells the
browser which one it is serving.

In production you would pick one. Both are here so the demo can prove the
claim rather than assert it.
"""

from django.urls import include, path

urlpatterns = [
    # Mounted under a prefix — what scitex-hub does with a published app.
    path("apps/u/hello_world/", include("hello_world.urls", namespace="embedded")),
    # Mounted at the root — standalone. Must stay LAST: it matches everything
    # under "", so anything after it is unreachable.
    path("", include("hello_world.urls", namespace="standalone")),
]

# WHY THE TWO `namespace=` ARGUMENTS, since a real app needs neither:
# hello_world/urls.py sets `app_name = "hello_world"`, so including it twice
# registers that namespace twice and Django warns (urls.W005) that reverse()
# cannot resolve it unambiguously. Distinct instance namespaces make each mount
# reversible on its own — `reverse("standalone:page")` vs `reverse("embedded:page")`.
#
# This is an artifact of the DEMO mounting one app twice in one process to prove
# the claim. Mount an app once, as production does, and you write the plain
# `include("hello_world.urls")` with no namespace argument at all.
