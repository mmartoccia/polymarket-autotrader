#!/bin/bash
# Collect current trading state snapshot

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$SCRIPT_DIR" || exit 1

python3 scripts/collect_snapshot.py "$@"
