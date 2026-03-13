#!/bin/bash
# Timestamp: 2026-03-13
# File: examples/00_run_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Running all scitex-app examples ==="
echo

for script in "$SCRIPT_DIR"/[0-9][0-9]_*.py; do
    [ -f "$script" ] || continue
    echo "--- Running: $(basename "$script") ---"
    python "$script"
    echo
done

echo "=== All examples completed ==="
