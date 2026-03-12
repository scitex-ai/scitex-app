#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: docs/sphinx/conf.py

"""Sphinx configuration for scitex-app documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "SciTeX App"
copyright = "2024-2026, Yusuke Watanabe"
author = "Yusuke Watanabe"

try:
    from importlib.metadata import version

    release = version("scitex-app")
except Exception:
    release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx_rtd_theme",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

myst_enable_extensions = [
    "dollarmath",
    "colon_fence",
    "deflist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
