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
    path("apps/u/hello_world/", include("hello_world.urls")),
    # Mounted at the root — standalone. Must stay LAST: it matches everything
    # under "", so anything after it is unreachable.
    path("", include("hello_world.urls")),
]
