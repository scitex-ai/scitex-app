"""Every route RELATIVE. That is what makes the app mountable anywhere.

No leading slashes here: `include()` supplies the prefix, so the same file
serves `/` standalone and `/apps/u/hello_world/` embedded, unchanged.
"""

from django.urls import path

from . import views

app_name = "hello_world"

urlpatterns = [
    path("", views.page, name="page"),
    path("api/greet", views.greet, name="greet"),
]
