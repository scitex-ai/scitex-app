"""Routes RELATIVE, so the app mounts anywhere (mount contract)."""

from django.urls import path

from . import views

app_name = "project_context"

urlpatterns = [
    path("", views.projects, name="projects"),
    path("change", views.change, name="change"),
]
