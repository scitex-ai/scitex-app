App Development Guide
=====================

SciTeX apps are self-contained Django plugins that integrate into the
SciTeX Cloud workspace. This guide covers the full lifecycle: scaffold,
validate, install-dev, and submit.

.. contents:: Contents
   :local:
   :depth: 2

Role of Each Package
--------------------

.. code-block:: text

   scitex-app  (this package) — developer SDK: scaffold, validate, install
   scitex-hub                 — platform: mounts apps, handles security, routing
   figrecipe                  — reference app: see how a real app is built

``scitex-app`` is the **only** package app developers need to install.
``scitex-hub`` is the platform; developers interact with it only through
the server URL and API token.


Scaffold a New App
------------------

Use ``scitex-app app init`` to generate a complete app skeleton:

.. code-block:: bash

   # Scaffold in current directory (uses directory name as app name)
   scitex-app app init .

   # Scaffold with explicit name, label, icon, and description
   scitex-app app init /path/to/my_app \
       --name my_awesome_app \
       --label "My Awesome App" \
       --icon "fas fa-flask" \
       --description "Analyses spectral data"

   # Scaffold a React+Vite frontend instead of plain HTML
   scitex-app app init . --frontend react

   # Overwrite existing files
   scitex-app app init . --overwrite

.. note::
   The app module name must end with ``_app`` or ``-app``.
   If it does not, the CLI appends the suffix automatically.

Generated Structure (HTML frontend)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   my_awesome_app/
   ├── __init__.py
   ├── apps.py                          # AppConfig subclass
   ├── views.py                         # Django view
   ├── urls.py                          # URL patterns
   ├── tests.py                         # Basic test stubs
   ├── skill.py                         # MCP skill definition
   ├── manifest.json                    # App metadata + privileges
   ├── pyproject.toml                   # Dual-mode packaging
   ├── README.md
   ├── LICENSE
   ├── .gitignore
   ├── .agents/agents.json              # Agent integration config
   ├── AGENTS.md                        # Developer docs for agents
   ├── docs/PLATFORM.md                 # Platform integration notes
   ├── templates/my_awesome_app/
   │   ├── index.html
   │   └── index_partial.html
   └── static/my_awesome_app/css/
       └── my_awesome_app.css

React frontend adds:

.. code-block:: text

   ├── package.json
   ├── vite.config.ts
   ├── tsconfig.json
   └── src/
       ├── main.tsx
       ├── App.tsx
       └── store.ts                     # Zustand state store


Python API (programmatic scaffold)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from scitex_app.appmaker import init_app

   created = init_app(
       target_dir="/path/to/my_awesome_app",
       name="my_awesome_app",
       label="My Awesome App",
       icon="fas fa-flask",
       description="Analyses spectral data",
       frontend_type="html",   # or "react"
       overwrite=False,
   )

   print(f"Created {len(created)} files")
   for path in created:
       print(f"  + {path}")

``init_app`` returns the list of relative paths that were written.
Files that already exist are skipped unless ``overwrite=True``.


Validate an App
---------------

Run the full validation pipeline before installing or submitting:

.. code-block:: bash

   scitex-app app validate .
   scitex-app app validate /path/to/my_awesome_app

Exit code 0 on success, 1 on failure.

Validation Checks
~~~~~~~~~~~~~~~~~

The validator runs these checks in order:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Check
     - What it verifies
   * - **Structure**
     - Required files exist (``views.py``, ``urls.py``, ``manifest.json``,
       ``apps.py``, ``LICENSE``, ``README.md``, partial template,
       ``.agents/agents.json``)
   * - **Security**
     - No forbidden Python patterns: ``subprocess``, ``os.system``,
       ``eval()``, ``exec()``, ``__import__``
   * - **Manifest**
     - Valid JSON, all required keys present (``name``, ``slug``,
       ``label``, ``version``, ``icon``, ``license``), semver version
   * - **Templates**
     - ``index.html`` extends ``global_base.html``, defines
       ``{% block content %}``, does not override platform frame blocks
   * - **CSS**
     - No ``!important`` on protected shell selectors, no hiding footer,
       no deprecated ``--color-*`` variables
   * - **Dependencies**
     - ``manifest.json`` has a well-formed ``dependencies`` object

Python API (programmatic validation)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from scitex_app.appmaker import validate

   errors = validate("/path/to/my_awesome_app")

   if not errors:
       print("App is valid")
   else:
       for err in errors:
           print(f"  ✗ {err}")

``validate`` returns an empty list when all checks pass.


Dev-Install on SciTeX Cloud
----------------------------

After local validation passes, install the app directly on a running
SciTeX Cloud server for development testing:

.. code-block:: bash

   # Install using environment variables for credentials
   export SCITEX_API_TOKEN="your-jwt-token"
   export SCITEX_SERVER_URL="http://127.0.0.1:8000"

   scitex-app app install-dev .

   # Or pass options explicitly
   scitex-app app install-dev . \
       --server http://my-server:8000 \
       --token  "$SCITEX_API_TOKEN"

On success the app appears immediately in the workspace sidebar.

.. important::
   The server must have access to the app source files (shared volume,
   NFS mount, or cloned repo). Dev-install registers the local path;
   it does not upload files.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Description
   * - ``SCITEX_API_TOKEN``
     - JWT Bearer token (obtain from *Settings → API Tokens* in the UI)
   * - ``SCITEX_SERVER_URL``
     - Base URL of the SciTeX Cloud server (default: ``http://127.0.0.1:8000``)

Python API
~~~~~~~~~~

.. code-block:: python

   from scitex_app.appmaker._dev_install import dev_install

   result = dev_install(
       app_dir=".",
       server_url="http://127.0.0.1:8000",
       token="your-jwt-token",
   )

   if result["success"]:
       print("Installed:", result.get("module_name"))
   else:
       print("Failed:", result["errors"])

``dev_install`` runs local validation first and returns early with
``{"success": False, "errors": [...]}`` if validation fails.


Submit for Publication
----------------------

Once the app is ready for public release, submit it for review:

.. code-block:: bash

   scitex-app app submit .

   # Or with explicit server and token
   scitex-app app submit /path/to/my_awesome_app \
       --server https://scitex.example.com \
       --token  "$SCITEX_API_TOKEN"

This validates the app locally, then opens a pull-request on the
``scitex-apps`` registry repository for maintainer review.

.. code-block:: python

   from scitex_app.appmaker._publish import publish

   result = publish(
       app_dir=".",
       server_url="https://scitex.example.com",
       token="your-jwt-token",
   )

   if result["success"]:
       print("PR URL:", result["pr_url"])


Manifest Reference
------------------

Every app must include a ``manifest.json`` at its root:

.. code-block:: json

   {
     "name":        "my_awesome_app",
     "slug":        "my-awesome-app",
     "label":       "My Awesome App",
     "version":     "0.1.0",
     "icon":        "fas fa-flask",
     "description": "Analyses spectral data",
     "license":     "AGPL-3.0",

     "frontend_type": "html",

     "privileges": [
       {"type": "filesystem", "scope": "project"},
       {"type": "network",    "scope": "none"},
       {"type": "api",        "scope": "scitex"}
     ],

     "dependencies": {
       "python": ["numpy>=1.24", "pandas>=2.0"],
       "system": [],
       "node":   [],
       "r":      []
     }
   }

Required fields: ``name``, ``slug``, ``label``, ``version``, ``icon``, ``license``.

Privilege Scopes
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Type
     - Valid scopes
   * - ``filesystem``
     - ``project``, ``readonly``, ``none``
   * - ``network``
     - ``none``, ``allowlist``
   * - ``api``
     - ``scitex``, ``llm``, ``none``


CSS Rules
---------

App CSS is isolated from the platform shell. Follow these rules:

- **Use** ``--workspace-*`` and ``--text-*`` CSS custom properties
- **Do not use** deprecated ``--color-*`` variables
- **Do not apply** ``!important`` to platform shell selectors:

  .. code-block:: text

     .stx-shell-sidebar, .stx-shell-sidebar__title,
     .panel-resizer, footer

- **Do not hide** the footer (``footer { display: none }`` is blocked)
- **Do not override** workspace frame template blocks:
  ``workspace_worktree_pane``, ``workspace_ai_pane``,
  ``workspace_viewer_pane``, ``workspace_apps_pane``


Typical Workflow
----------------

.. code-block:: bash

   # 1. Scaffold
   mkdir ~/proj/my_awesome_app
   scitex-app app init ~/proj/my_awesome_app --name my_awesome_app

   # 2. Edit source files in your editor
   cd ~/proj/my_awesome_app
   # ... implement views.py, templates, etc. ...

   # 3. Validate locally
   scitex-app app validate .

   # 4. Dev-install on a running server for live testing
   export SCITEX_API_TOKEN="..."
   scitex-app app install-dev . --server http://127.0.0.1:8000

   # 5. Iterate: edit → validate → install-dev
   # (The server hot-reloads on file changes)

   # 6. Submit when ready
   scitex-app app submit .


See Also
--------

- :doc:`quickstart` — SDK usage (file I/O, backends)
- :doc:`cli` — Full CLI reference
- :doc:`api/scitex_app` — Python API reference
- `APP_DEVELOPER_GUIDE.md <https://github.com/ywatanabe1989/scitex-app/blob/main/docs/APP_DEVELOPER_GUIDE.md>`_ — Detailed guide for AI coding agents
- `figrecipe <https://figrecipe.readthedocs.io/>`_ — Reference app built on this SDK
