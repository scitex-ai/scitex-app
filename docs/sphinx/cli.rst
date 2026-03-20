CLI Reference
=============

Overview
--------

.. code-block:: bash

   scitex-app --help
   scitex-app --help-recursive


App Development Commands
------------------------

The ``app`` subgroup covers the full app development lifecycle.
See :doc:`app_development` for a worked example.

.. code-block:: bash

   scitex-app app --help

**Scaffold**

.. code-block:: bash

   scitex-app app init [TARGET_DIR] [OPTIONS]

   Options:
     -n, --name TEXT         App module name (must end with _app)
     -l, --label TEXT        Human-readable label
     -i, --icon TEXT         Font Awesome icon class  [default: fas fa-puzzle-piece]
     -d, --description TEXT  Short description
     -f, --frontend [html|react]
                             Frontend type            [default: html]
     --overwrite             Overwrite existing files

   Examples:
     scitex-app app init .
     scitex-app app init . -n my_app -l "My App" -i "fas fa-flask"
     scitex-app app init . --frontend react

**Validate**

.. code-block:: bash

   scitex-app app validate [APP_DIR]

   Examples:
     scitex-app app validate .
     scitex-app app validate /path/to/my_app

   Exit code: 0 = all checks passed, 1 = validation errors found.

**Dev-Install**

.. code-block:: bash

   scitex-app app dev-install [APP_DIR] [OPTIONS]

   Options:
     -s, --server TEXT   SciTeX Cloud server URL   [env: SCITEX_SERVER_URL]
                                                   [default: http://127.0.0.1:8000]
     -t, --token TEXT    JWT access token          [env: SCITEX_API_TOKEN]
     -o, --owner TEXT    Gitea username (auto-detected from token if omitted)
     -r, --repo TEXT     Gitea repo name (derived from manifest if omitted)

   Examples:
     scitex-app app dev-install .
     scitex-app app dev-install . --server http://my-server:8000

**Submit**

.. code-block:: bash

   scitex-app app submit [APP_DIR] [OPTIONS]

   Options:
     -s, --server TEXT   SciTeX Cloud server URL  [env: SCITEX_SERVER_URL]
     -t, --token TEXT    JWT access token         [env: SCITEX_API_TOKEN]

   Examples:
     scitex-app app submit .
     scitex-app app submit . --server https://scitex.example.com


File Commands
-------------

.. code-block:: bash

   scitex-app read <path> [--root DIR] [--binary]
   scitex-app list [DIR] [--root DIR] [--ext .yaml]
   scitex-app exists <path> [--root DIR]


Integration
-----------

.. code-block:: bash

   scitex-app list-python-apis [-v|-vv|-vvv]
   scitex-app mcp start
   scitex-app mcp list-tools [-v|-vv|-vvv]
   scitex-app mcp doctor
   scitex-app mcp installation
