---
plan:
  # Required
  name: "Plan Name"
  for: "component/path"           # Component path (e.g., apps/example_app)
  type: roadmap                   # roadmap | architecture | runbook | eval | implementation | feature
  status: active                  # active | paused | completed | archived
  last_updated: 2026-01-01

  # Required when status=active
  focus: "What to prioritize now"

  # Optional: work streams with priority
  streams:
    - name: "Stream Name"
      priority: now               # now | next | later | done
      status: in_progress         # not_started | in_progress | blocked | done
      tasks: 5                    # Total tasks (optional)
      done: 2                     # Completed tasks (optional)
      blocked_by: ""              # Blocking stream name (optional)

  # Optional: open questions (queryable across plans)
  questions:
    - "Open question about this plan"

  # Optional: key decisions (queryable across plans)
  decisions:
    - decision: "What was decided"
      date: 2026-01-01
      context: "Why this was decided"  # optional
---

# Plan Name

## Current Focus

What's being worked on right now and why.

## Next

What comes after the current focus.

## Later / Backlog

Lower-priority items for the future.

## Changelog

| Date | Change |
|------|--------|
| 2026-01-01 | Created plan |
