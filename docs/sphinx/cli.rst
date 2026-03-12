CLI Reference
=============

Overview
--------

.. code-block:: bash

   scitex-app --help
   scitex-app --help-recursive

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
