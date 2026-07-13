Installation
============

Basic
-----

.. code-block:: bash

   pip install scitex-app

``click``, ``rich``, and ``scitex-config`` are base dependencies, always installed.

All features
------------

Chat (anthropic/litellm), cloud, Django integration, and MCP tools:

.. code-block:: bash

   pip install scitex-app[all]

Development
-----------

.. code-block:: bash

   git clone git@github.com:ywatanabe1989/scitex-app.git
   cd scitex-app
   pip install -e ".[dev]"
