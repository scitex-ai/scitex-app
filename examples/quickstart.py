#!/usr/bin/env python3
"""Quickstart for scitex-app: list registered backends + simple file ops.

Demonstrates the public API surface, registered backends, and a minimal
read/write/list/tree round-trip against a temporary directory.

Usage:
    python quickstart.py
"""

import logging
import tempfile

import scitex_app
from scitex_app import build_tree, get_files
from scitex_app.sdk import _registry

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    public = [n for n in dir(scitex_app) if not n.startswith("_")]
    logger.info(f"scitex_app public symbols: {public}")
    logger.info(f"registered backends: {sorted(_registry.keys())}")

    with tempfile.TemporaryDirectory() as tmp:
        files = get_files(tmp)
        logger.info(f"\nbackend instance: {files}")
        files.write("notes/hello.txt", "hello world\n")
        files.write("data/sample.csv", "x,y\n1,2\n")
        listing = files.list("")
        logger.info(f"top-level entries: {listing}")
        tree = build_tree(files, "")
        logger.info(f"tree depth-1 keys: {[node.get('name') for node in tree]}")

    return 0


if __name__ == "__main__":
    main()
