#!/usr/bin/env python3
"""Quickstart for scitex-app: list registered backends + simple file ops."""

import tempfile

import scitex_app
from scitex_app import build_tree, get_files
from scitex_app.sdk import _registry


def main() -> int:
    public = [n for n in dir(scitex_app) if not n.startswith("_")]
    print(f"scitex_app public symbols: {public}")
    print(f"registered backends: {sorted(_registry.keys())}")

    with tempfile.TemporaryDirectory() as tmp:
        files = get_files(tmp)
        print(f"\nbackend instance: {files}")
        files.write("notes/hello.txt", "hello world\n")
        files.write("data/sample.csv", "x,y\n1,2\n")
        listing = files.list("")
        print(f"top-level entries: {listing}")
        tree = build_tree(files, "")
        print(f"tree depth-1 keys: {[node.get('name') for node in tree]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
