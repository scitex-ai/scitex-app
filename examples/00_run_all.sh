#!/bin/bash
# File: ./examples/00_run_all.sh
# Run all scitex-app examples in sequence.

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PATH="$THIS_DIR/$(basename "$0").log"
echo >"$LOG_PATH"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "$1" | tee -a "$LOG_PATH"; }

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

main() {
    cd "$THIS_DIR"

    log "========================================"
    log "scitex-app Examples Runner"
    log "========================================"
    log ""

    # Find all numbered .py files
    local -a SCRIPTS
    mapfile -t SCRIPTS < <(find . -maxdepth 1 -name '[0-9][0-9]_*.py' | sort)
    local TOTAL=${#SCRIPTS[@]}
    local COUNT=0
    local PASSED=0
    local FAILED=0

    for script in "${SCRIPTS[@]}"; do
        local name
        name=$(basename "$script")

        COUNT=$((COUNT + 1))
        log ""
        log "[$COUNT/$TOTAL] Running $name..."

        if python "$name" >>"$LOG_PATH" 2>&1; then
            log "${GREEN}[PASS]${NC} $name"
            PASSED=$((PASSED + 1))
        else
            log "${RED}[FAIL]${NC} $name (see $LOG_PATH)"
            FAILED=$((FAILED + 1))
        fi
    done

    log ""
    log "========================================"
    log "Results: $PASSED passed, $FAILED failed"
    log "========================================"
    log ""
    log "Log: $LOG_PATH"
}

main "$@"

# EOF
