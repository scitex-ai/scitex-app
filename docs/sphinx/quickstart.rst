Quickstart
==========

Python API
----------

.. code-block:: python

   from scitex_app.sdk import get_files

   # Local filesystem (default)
   files = get_files("./my_project")

   # Read and write files
   content = files.read("config/settings.yaml")
   files.write("output/result.csv", csv_text)

   # List and check files
   yaml_files = files.list("config", extensions=[".yaml"])
   if files.exists("output/result.csv"):
       print("Result ready")

Cloud mode
----------

When ``SCITEX_API_TOKEN`` is set, the SDK automatically routes through
the cloud REST API:

.. code-block:: python

   import os
   os.environ["SCITEX_API_TOKEN"] = "your-token"

   files = get_files()  # auto-detects cloud backend
   content = files.read("data/input.csv")

Custom backends
---------------

Register custom storage backends:

.. code-block:: python

   from scitex_app.sdk import register_backend

   register_backend("s3", my_s3_factory)
   files = get_files(backend="s3")
