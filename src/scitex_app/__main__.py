#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: /home/ywatanabe/proj/scitex-app/src/scitex_app/__main__.py

"""Entry point for `python -m scitex_app`.

Per scitex-dev audit-project PS105: every distribution must be runnable
via `python -m <package>`. Delegates to the Click CLI defined in
`scitex_app._cli`.
"""

from scitex_app._cli import main

if __name__ == "__main__":
    main()
