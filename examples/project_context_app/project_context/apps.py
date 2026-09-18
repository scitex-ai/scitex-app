"""A project-scoped SciTeX app: the reference consumer of project context.

`"scope": "project"` in the manifest is what makes project selection this app's
business — a user-scoped app renders with no project switcher at all, and the
SDK says so structurally rather than by convention (see
``scitex_app._app_scope``).
"""

from scitex_app.embed import ScitexAppConfig


class ProjectContextConfig(ScitexAppConfig):
    name = "project_context"
    label = "project_context"
    verbose_name = "Project Context"
