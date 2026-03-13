MCP Server
==========

SciTeX App provides an MCP (Model Context Protocol) server for AI agents
to interact with the file storage SDK.

Available Tools
---------------

.. list-table::
   :header-rows: 1

   * - Tool
     - Description
   * - ``app_read_file``
     - Read a file through the SDK backend
   * - ``app_write_file``
     - Write content to a file
   * - ``app_list_files``
     - List files in a directory
   * - ``app_file_exists``
     - Check if a file exists
   * - ``app_delete_file``
     - Delete a file
   * - ``app_copy_file``
     - Copy a file
   * - ``app_rename_file``
     - Rename/move a file

Starting the Server
-------------------

.. code-block:: bash

   scitex-app mcp start

Configuration
-------------

Add to your MCP client configuration:

.. code-block:: json

   {
     "mcpServers": {
       "scitex-app": {
         "command": "scitex-app",
         "args": ["mcp", "start"]
       }
     }
   }
