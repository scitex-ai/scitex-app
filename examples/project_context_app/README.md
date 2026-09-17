# Project Context — reference consumer

A minimal, project-scoped SciTeX app that consumes the project-context contract
in `scitex_app.project_context`. It exists so the contract has an executable
example rather than only a docstring: **copy this** when your app needs to know
which project the user is working in.

The contract's own rules live in [`docs/PROJECT_CONTEXT.md`](../../docs/PROJECT_CONTEXT.md).
This README is about what a consumer does.

## The whole consumer, in three lines

```python
from scitex_app.project_context import project_context

def projects(request):
    return render(request, "project_context/projects.html", project_context(request))
```

That is it. The view does not learn who serves the projects, does not build a
URL for the change action, and does not fall back to a project of its own
choosing — the three things consumers get wrong.

## Render all four states

`project_state` is one of `ok`, `none`, `denied`, `unavailable`, and each one
means something different to the person reading the page:

| State | What the template should say |
| --- | --- |
| `ok` | the active project's **name** (`active_project.name`) |
| `none` | "choose a project" — an invitation, not an error |
| `denied` | "that project is not available to you", and the current one is unchanged |
| `unavailable` | "projects are temporarily unavailable" — an outage, not an empty list |

Rendering `none` and `unavailable` identically is the subtle version of the bug:
both look like "no projects", and the visitor cannot tell "you have not chosen
one" from "the service is down" — two different problems with two different
remedies. `projects.html` here renders them as two different sentences.

`active_project` carries **`id` and `name`, and never a path**. There is no
field to leak, so "do not display internal paths" needs no discipline from you.

## Changing the project

The context carries a **command name**, not a URL:

```python
def change(request):
    try:
        project = change_project(request, request.POST.get("project", ""))
    except ProjectDeniedError as exc:
        return HttpResponseForbidden(str(exc))      # 403 — a permission answer
    except ProjectUnavailableError as exc:
        return HttpResponse(str(exc), status=503)   # 503 — an outage, not a denial
    return JsonResponse(project.as_dict())
```

Two refusals, two different meanings, and neither of them silently succeeds. A
`change_project` that is refused **changes nothing**: the previously active
project is still active.

Because the operation is named (`scitex.project.change`), the same action is
reachable from a click, a keystroke, a recorded macro and an agent. A URL-bound
implementation breaks the moment the app's mount prefix changes; a named one
does not.

## Running it standalone

```bash
python -c "
from scitex_app.embed import run_standalone
run_standalone('project_context', port=8066, open_browser=False, working_dir='./projects')
"
```

`run_standalone()` registers the standalone provider, so the picker lists the
folders under `working_dir`. Nothing is selected until you select it — a fresh
session resolves to `none` and shows the picker. That is deliberate: no example
project is ever created or chosen on a user's behalf.

A leaf that wants the shell around this page should merge the same context into
`scitex_ui.branding.shell_context(...)` — see the SDK's own tests for that
composition.

## Running its tests

```bash
pytest examples/project_context_app/tests/
```

`testpaths` is `["tests"]`, so this example's suite is **not** collected by CI —
true of `hello_world_app` too. The command above is how it is run.

The provider-backed assertions skip themselves where scitex-ui is absent (as
scitex-app's own CI runs); the arms that hold with no provider at all still run
there, because "a page never 500s when the project service is unreachable" is
the state a fresh host is actually in.
