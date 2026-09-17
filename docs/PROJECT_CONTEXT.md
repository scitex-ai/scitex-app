# Project context

One project is selected once and carried across every leaf app.
SSOT: scitex-hub PR 923, `docs/product/PRIVATE_BETA_LOGIN_TO_WOW.md`.

## Who owns what

| Package | Owns |
| --- | --- |
| `scitex-hub` | user/project **authority** and integration. It knows which projects a user may access and serves that as the host provider. |
| `scitex-ui` | the **provider protocol** (`ProjectProvider`, `ProjectEntry`, `resolve_project`) and the picker's rendering. |
| `scitex-app` | **this contract**: what a leaf app is handed, the fail-closed states around it, and the named command that changes it. |

`scitex_app.project_context` deliberately does **not** re-implement
`scitex_ui.project_scope.resolve_project`. A second implementation would be a
forked producer with no link to the first, and the two would drift. Resolution
runs through scitex-ui's code path, so there is one precedence rule, not two.

## The descriptor

`ActiveProject` is what a leaf may see: `id` and `name`, and **no path field at
all**. scitex-ui's `ProjectEntry` also carries `detail`, which
`LocalProjectProvider` fills with a filesystem path; that field is
provider-internal. A descriptor without a path field cannot leak one, so the
product rule ("displays user-facing project names, never internal `MASTER/`
paths") is structural rather than something a view has to remember.

`name` is the display label. An entry with no name falls back to its `id` —
never to a path and never to an invented label.

## States

`ProjectResolution` has one shape for every outcome, so a caller never has to
guess which keys exist.

| State | Meaning | What the app shows |
| --- | --- | --- |
| `ok` | a project is selected and the user may access it | the project |
| `none` | nothing selected, or the stored project is gone | **its picker** — not an error |
| `denied` | an explicit project was asked for and is not accessible | denied |
| `unavailable` | no provider could answer (absent, unconfigured, or failed) | unavailable |

`denied` covers both "no such project" and "not yours". They are **not
distinguished**, because telling them apart would confirm that another user's
project exists.

`unavailable` deliberately does not collapse into `none`: "we could not ask"
must not render as "you have none".

## Fail-closed rules

1. An explicit project (`?project=`, or the `explicit` argument) **wins**, and
   *becomes* the stored one so the choice survives the next navigation.
2. An explicit project that is not accessible is **denied**, and **never falls
   back** to the stored one. Silently substituting a project nobody asked for is
   the failure this rule exists to stop.
3. Otherwise the stored project, if it is still accessible.
4. Otherwise `none`. **Nothing is auto-selected**, and no example project is
   ever created or chosen on a user's behalf.
5. A provider that raises yields `unavailable` — never a 500, never `none`, and
   never an `ok` with a guessed project.
6. A refused `change_project` **changes nothing**: the previous selection stays.

## Consuming it

Register the context processor and every template of the mounted app receives
the context without its view passing anything:

```python
TEMPLATES[0]["OPTIONS"]["context_processors"] += [
    "scitex_app.project_context.project_context",
]
```

```django
{% if active_project %}
  <span data-project="{{ active_project.id }}">{{ active_project.name }}</span>
{% elif project_state == "unavailable" %}
  <span>Projects are temporarily unavailable.</span>
{% else %}
  <button data-command="{{ project_command }}">Choose a project</button>
{% endif %}
```

`project_command` carries the command **name** rather than a URL, so a click, a
keystroke, a recorded macro and an agent all address the same operation and none
of them breaks when the mount prefix changes:

```python
from scitex_app.project_context import CHANGE_PROJECT_COMMAND   # "scitex.project.change"

change_project(request, "neuro-paper")   # raises ProjectDeniedError if not accessible
```

## Hosting it

A host registers its provider once; nothing else in the SDK needs to know who
serves it:

```python
SCITEX_PROJECT_PROVIDER = "myhost.projects.HostProjectProvider"  # dotted path
SCITEX_PROJECT_PROVIDER_URL = "api_project_scope"                # URL name
```

## Standalone

`run_standalone()` registers `scitex_app.project_context.StandaloneProjectProvider`
under `SCITEX_PROJECT_PROVIDER` when scitex-ui is installed, and adds the
context processor to `TEMPLATES`. A standalone project-scoped app therefore has
a working picker that lists the folders under `SCITEX_WORKING_DIR`.

Registration is **inert for a user-scoped app**: the picker is gated on the
app's declared `scope`, so a provider nothing consults cannot conjure a
selector. Nothing is selected by construction — the standalone provider reports
no last-visited project until a user or a command stores one.

## Migration notes

There is nothing to migrate: this is a new surface and no existing behaviour
changes for an app that does not register the context processor.

- **Standalone launchers** gain two settings they did not have
  (`SCITEX_PROJECT_PROVIDER` and one extra context processor). Both are inert
  for user-scoped apps. A launcher that configures Django *itself* — before
  calling `run_standalone()` — gets neither, because `_configure_django()`
  returns early when settings are already configured. Same caveat as every other
  standalone setting; see `05_standalone.md`.
- **Hub and other hosts** must register a provider before any project-scoped app
  can resolve a project. Until then every app reports `unavailable`, which is
  the honest state rather than a blank page.
- **Leaf apps** opt in by registering the context processor (or calling
  `resolve_active_project()` directly). Until they do, nothing about them
  changes.
