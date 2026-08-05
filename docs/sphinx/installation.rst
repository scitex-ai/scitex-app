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
   python -m pip install --upgrade pip
   pip install -e ".[all]" --group dev

``dev`` and ``docs`` are PEP 735 dependency groups, not extras, so they are
requested with ``--group`` (pip 25.1+) and are not installable as ``.[dev]``.
They build the package rather than use it, which is why they stay out of
``pip install scitex-app[all]``.
