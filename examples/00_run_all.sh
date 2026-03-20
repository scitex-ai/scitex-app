#!/bin/bash
# Timestamp: 2026-03-13
# File: examples/00_run_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Run all scitex-app examples.

Options:
    -h, --help    Show this help message
EOF
}

case "${1:-}" in
-h | --help)
    usage
    exit 0
    ;;
esac

echo "=== Running all scitex-app examples ==="
echo

for script in "$SCRIPT_DIR"/[0-9][0-9]_*.py; do
    [ -f "$script" ] || continue
    echo "--- Running: $(basename "$script") ---"
    python "$script"
    echo
done

echo "=== All examples completed ==="
