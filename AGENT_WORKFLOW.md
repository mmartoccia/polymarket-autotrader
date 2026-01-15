# Autonomous Agent Workflow

## Overview

This codebase is structured for autonomous AI agent execution. Agents pick up the next uncompleted user story from `PRD.md` and implement it independently.

## How It Works

### 1. Read PRD.md
```bash
# See current user stories
cat PRD.md

# Find next uncompleted story
grep -A 10 "Status.*PENDING" PRD.md | head -20
```

### 2. Pick Next Story
- Stories are ordered by dependency (US-001, US-002, etc.)
- **ONLY work on PENDING stories where dependencies are met**
- Skip BLOCKED stories (waiting for data collection)

### 3. Implement Story
Each story has:
- **Description:** What needs to be built (as a user, I want...)
- **Acceptance Criteria:** Verifiable checklist (must ALL be complete)
- **Status:** ⏳ PENDING → 🔄 IN PROGRESS → ✅ COMPLETE

### 4. Mark Complete
When done:
1. Update `PRD.md` - check all boxes, change status to ✅ COMPLETE
2. Update `progress.txt` - document what was done, learnings, patterns
3. Commit with descriptive message
4. Push to GitHub

## Current Status

### Completed (US-001 to US-004):
- ✅ Database schema (agent_performance, agent_votes_outcomes)
- ✅ Agent performance tracker module
- ✅ Agent enable/disable configuration
- ✅ Bot integration (AGENT_ENABLED flags)

### Next Available (US-006):
**US-006: Create ultra_selective shadow strategy**
- Add to `simulation/strategy_configs.py`
- Higher thresholds (0.80/0.70)
- ~10 min implementation

### Blocked (US-005):
- Waiting for 100+ trades (~2-3 days)
- Cannot start yet

### Remaining (US-007 to US-019):
- 13 more stories (Weeks 2-4)
- Execute sequentially as dependencies clear

## Story Sizing

Each story is **completable in one context window (~10 min)**:
- ✅ Good: "Add column to database"
- ✅ Good: "Create Kelly sizer class"
- ❌ Too big: "Build entire dashboard"

If a story seems too big, split it into smaller stories.

## Acceptance Criteria Rules

Criteria must be **verifiable** (can be checked):
- ✅ Good: "Typecheck passes"
- ✅ Good: "File exists at path X"
- ✅ Good: "Function returns expected output"
- ❌ Bad: "Works correctly"
- ❌ Bad: "Good UX"

All stories include:
- `Typecheck passes` as final criterion
- UI stories include: `Verify changes work in browser`

## Dependencies

Stories are ordered so earlier stories don't depend on later ones:

**Correct:**
1. Schema changes
2. Backend logic
3. UI components

**Wrong:**
1. UI component (needs backend that doesn't exist!)
2. Backend logic

If dependencies aren't met, story is marked BLOCKED.

## Validation Stories

Some stories require data collection:
- US-005: Wait for 100+ trades (agent analysis)
- US-008: Wait for 100+ trades (strategy comparison)
- US-013: Wait for 100+ trades (Kelly sizing validation)

These are **BLOCKED** until data is available. Skip them and work on other stories.

## File Structure

```
PRD-strategic.md      # High-level 4-week roadmap (strategic overview)
PRD.md                # Current implementation (user stories US-001 to US-019)
progress.txt          # Learnings, patterns discovered during implementation
AGENT_WORKFLOW.md     # This file (how agents should work)
```

## Agent Checklist

Before starting a story:
- [ ] Read story description and acceptance criteria
- [ ] Verify dependencies are met (previous stories complete)
- [ ] Verify not BLOCKED (waiting for data)

While implementing:
- [ ] Check off each acceptance criterion as completed
- [ ] Run typecheck if required
- [ ] Test implementation

After completing:
- [ ] Update PRD.md status to ✅ COMPLETE
- [ ] Update progress.txt with learnings
- [ ] Commit with clear message
- [ ] Push to GitHub

## Example Workflow

```bash
# 1. Find next story
grep -B 5 "Status.*PENDING" PRD.md | head -10

# 2. Implement (e.g., US-006)
# ... write code ...

# 3. Verify acceptance criteria
python3 -m py_compile simulation/strategy_configs.py  # typecheck

# 4. Mark complete in PRD.md
# Change Status to: ✅ COMPLETE
# Check all boxes: - [x] Item

# 5. Document in progress.txt
# Add iteration entry with learnings

# 6. Commit and push
git add .
git commit -m "US-006: Create ultra_selective shadow strategy"
git push origin main
```

## Next Story to Implement

**US-006: Create ultra_selective shadow strategy**

Location: `PRD.md` line 127

Ready to implement (no blockers, dependencies met).

---

**For detailed strategic context, see `PRD-strategic.md`**
