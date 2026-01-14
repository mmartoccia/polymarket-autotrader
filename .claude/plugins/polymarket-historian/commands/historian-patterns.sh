#!/bin/bash
# Analyze trade patterns and generate insights

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$SCRIPT_DIR" || exit 1

python3 scripts/analyze_patterns.py "$@"
