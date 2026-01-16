#!/bin/bash
set -e

# Parse command line arguments
PRD_FILE=""
MAX=10
SLEEP=2

# Check if first arg is a PRD file (ends with .md)
if [[ "$1" == *.md ]]; then
    PRD_FILE="$1"
    MAX=${2:-10}
    SLEEP=${3:-2}
else
    PRD_FILE="PRD.md"
    MAX=${1:-10}
    SLEEP=${2:-2}
fi

# Derive progress file from PRD file name
# PRD.md -> progress.txt
# PRD-feature.md -> progress-feature.txt
PROGRESS_FILE="${PRD_FILE%.md}"
PROGRESS_FILE="${PROGRESS_FILE/PRD/progress}.txt"

echo "Starting Ralph - Max $MAX iterations"
echo "PRD File: $PRD_FILE"
echo "Progress File: $PROGRESS_FILE"
echo ""

for ((i=1; i<=$MAX; i++)); do
    echo "==========================================="
    echo "  Iteration $i of $MAX"
    echo "==========================================="

    result=$(claude --dangerously-skip-permissions -p "You are Ralph, an autonomous coding agent. Do exactly ONE task per iteration.

## Steps

1. Read $PRD_FILE and find the first task that is NOT complete (marked [ ]).
2. Read $PROGRESS_FILE - check the Learnings section first for patterns from previous iterations.
3. Implement that ONE task only.
4. Run tests/typecheck to verify it works.

## Critical: Only Complete If Tests Pass

- If tests PASS:
  - Update $PRD_FILE to mark the task complete (change [ ] to [x])
  - Commit your changes with message: feat: [task description]
  - Append what worked to $PROGRESS_FILE

- If tests FAIL:
  - Do NOT mark the task complete
  - Do NOT commit broken code
  - Append what went wrong to $PROGRESS_FILE (so next iteration can learn)

## Progress Notes Format

Append to $PROGRESS_FILE using this format:

## Iteration [N] - [Task Name]
- What was implemented
- Files changed
- Learnings for future iterations:
  - Patterns discovered
  - Gotchas encountered
  - Useful context
---

## Update AGENTS.md (If Applicable)

If you discover a reusable pattern that future work should know about:
- Check if AGENTS.md exists in the project root
- Add patterns like: 'This codebase uses X for Y' or 'Always do Z when changing W'
- Only add genuinely reusable knowledge, not task-specific details

## End Condition

After completing your task, check $PRD_FILE:
- If ALL tasks are [x], output exactly: <promise>COMPLETE</promise>
- If tasks remain [ ], just end your response (next iteration will continue)")

    echo "$result"
    echo ""

    if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
        echo "==========================================="
        echo "  All tasks complete after $i iterations!"
        echo "==========================================="
        exit 0
    fi

    sleep $SLEEP
done

echo "==========================================="
echo "  Reached max iterations ($MAX)"
echo "==========================================="
exit 1
