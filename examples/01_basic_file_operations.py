#!/usr/bin/env python3
# Timestamp: 2026-03-13
# File: examples/01_basic_file_operations.py

"""Basic file operations with the App SDK."""

import tempfile
from pathlib import Path

from scitex_app.sdk import get_files


def main():
    # Create a temporary project directory
    with tempfile.TemporaryDirectory() as tmpdir:
        files = get_files(tmpdir)
        print(f"Backend: {files}")

        # Write files
        files.write("data/config.yaml", "key: value\ncount: 42\n")
        files.write("data/notes.txt", "Research notes here.")
        files.write("output/result.csv", "x,y\n1,2\n3,4\n")
        print("Written 3 files")

        # List files
        all_files = files.list("data")
        print(f"Files in data/: {all_files}")

        yaml_files = files.list("data", extensions=[".yaml"])
        print(f"YAML files: {yaml_files}")

        # Read file
        content = files.read("data/config.yaml")
        print(f"Config content:\n{content}")

        # Check existence
        print(f"config.yaml exists: {files.exists('data/config.yaml')}")
        print(f"missing.txt exists: {files.exists('missing.txt')}")

        # Copy and rename
        files.copy("data/config.yaml", "data/config_backup.yaml")
        files.rename("data/notes.txt", "data/research_notes.txt")
        print(f"After copy+rename: {files.list('data')}")

        # Delete
        files.delete("data/config_backup.yaml")
        print(f"After delete: {files.list('data')}")

    print("\nDone!")


if __name__ == "__main__":
    main()
