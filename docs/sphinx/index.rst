SciTeX App
==========

**Write-once interface for local + cloud SciTeX apps.**

SciTeX App provides a unified file storage SDK that works identically
whether your app runs locally (``pip install``) or on the cloud (scitex.ai).
Build once, deploy anywhere.

Role in SciTeX Ecosystem
------------------------

``scitex-app`` is the **runtime SDK** that apps import at execution time. It provides
backend-agnostic interfaces (``FilesBackend``, ``ScitexAppConfig``, ``AppValidator``)
so apps work locally, on the cloud, or self-hosted without code changes.

.. code-block:: text

   scitex (orchestrator, templates, CLI, MCP)
     |-- scitex-app (this package) -- runtime SDK for apps
     |-- scitex-ui                 -- React/TS component library
     +-- figrecipe                 -- reference app (figures)

- **scitex** (`docs <https://scitex-python.readthedocs.io/>`_): Orchestrator that re-exports ``scitex.app``
- **scitex-ui** (`docs <https://scitex-ui.readthedocs.io/>`_): Shared frontend components
- **figrecipe** (`docs <https://figrecipe.readthedocs.io/>`_): Reference app built on this SDK

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   quickstart
   cli
   mcp
   api/scitex_app

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
