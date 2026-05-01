#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Basic file operations with the App SDK.

Covers write/list/read/exists/copy/rename/delete against the default
filesystem backend, scoped to the session's auto-managed SDIR_RUN.

Usage:
    python 01_basic_file_operations.py
"""

from pathlib import Path

import scitex as stx

from scitex_app.sdk import get_files


@stx.session
def main(
    CONFIG=stx.session.INJECTED,
    logger=stx.session.INJECTED,
):
    """Exercise every FilesBackend method against a session-managed dir."""
    project_dir = Path(CONFIG.SDIR_RUN) / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    files = get_files(project_dir)
    logger.info(f"Backend: {files}")

    # Write files
    files.write("data/config.yaml", "key: value\ncount: 42\n")
    files.write("data/notes.txt", "Research notes here.")
    files.write("output/result.csv", "x,y\n1,2\n3,4\n")
    logger.info("Written 3 files")

    # List files
    all_files = files.list("data")
    logger.info(f"Files in data/: {all_files}")

    yaml_files = files.list("data", extensions=[".yaml"])
    logger.info(f"YAML files: {yaml_files}")

    # Read file
    content = files.read("data/config.yaml")
    logger.info(f"Config content:\n{content}")

    # Check existence
    logger.info(f"config.yaml exists: {files.exists('data/config.yaml')}")
    logger.info(f"missing.txt exists: {files.exists('missing.txt')}")

    # Copy and rename
    files.copy("data/config.yaml", "data/config_backup.yaml")
    files.rename("data/notes.txt", "data/research_notes.txt")
    logger.info(f"After copy+rename: {files.list('data')}")

    # Delete
    files.delete("data/config_backup.yaml")
    logger.info(f"After delete: {files.list('data')}")

    logger.info("\nDone!")
    return 0


if __name__ == "__main__":
    main()
