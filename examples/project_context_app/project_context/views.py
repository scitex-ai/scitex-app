"""The reference consumer: a leaf that renders and changes project context.

TWO VIEWS, because the contract has two halves and an example that shows only
the first would teach half the rule.

``projects`` renders whatever this request resolved to. It never asks who
serves the projects, never builds a URL, and never falls back to a project of
its own choosing — the three states are rendered as three different things,
which is the whole point of having three states.

``change`` is the HTTP arm of the stable named command. Note what it does NOT
do: it does not decide whether the change is allowed. Access is the provider's
answer, and this view only maps the SDK's two refusal reasons onto the two HTTP
statuses they mean. A view that made its own permission decision here would be
the second implementation of a rule that already has one.
"""

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from scitex_app.project_context import (
    ProjectDeniedError,
    ProjectUnavailableError,
    change_project,
    project_context,
)


def projects(request):
    """Render this request's project context, in whichever state it resolved to."""
    return render(request, "project_context/projects.html", project_context(request))


def change(request):
    """Apply the named command. Refusals map to their HTTP meanings, unchanged."""
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})

    try:
        project = change_project(request, request.POST.get("project", ""))
    except ProjectDeniedError as exc:
        # 403: a real permission answer. The active project is unchanged.
        return HttpResponseForbidden(str(exc))
    except ProjectUnavailableError as exc:
        # 503: "we could not ask" is not "you may not", and it is not success.
        return HttpResponse(str(exc), status=503)

    return JsonResponse(project.as_dict())
