---
description: Load plan context interactively. Discovers plans from YAML frontmatter, shows active focus/streams, loads full plan content.
allowed-tools: Bash(python3:*), Read, AskUserQuestion
---

# Interactive Plan Context Loader

## Step 1: Discover Plans

Run the discovery phase to find all plans with YAML frontmatter:

```bash
python3 .claude/skills/repo-context/scripts/context_loader.py --phase plans
```

This shows all discovered plans grouped by status, with focus areas, NOW/NEXT streams, open questions, and recent decisions.

## Step 2: Ask User Which Plan(s) to Load

After showing the overview, use AskUserQuestion to ask which plan(s) the user wants to review in detail.

Present the discovered plan paths as options (e.g., `apps/example_app/_plan.md`). Allow selecting multiple.

## Step 3: Load Plan Detail

Based on selection, run:

```bash
python3 .claude/skills/repo-context/scripts/context_loader.py --phase plan-detail --modules "<selected_paths>"
```

This loads:
- Full plan metadata (type, status, focus, streams)
- Complete plan body content
- Stream progress and blockers

## Step 4: Summarize

After loading, summarize:
- Current focus for each selected plan
- Open questions that need answers
- Blocked streams and what's blocking them
- Key recent decisions
