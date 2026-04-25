---
description: Load repository context interactively. Discovers components from YAML frontmatter, asks which to focus on, auto-resolves dependencies.
allowed-tools: Bash(python3:*), Read, AskUserQuestion
---

# Interactive Repository Context Loader

## Step 1: Discover Components

Run the discovery phase to find all components with YAML frontmatter:

```bash
python3 .claude/skills/repo-context/scripts/context_loader.py --phase overview
```

This shows all discovered components grouped by directory, with purposes and dependencies.

## Step 2: Ask User Which Module(s) to Focus On

After showing the overview, use AskUserQuestion to ask which module(s) the user wants to work on.

Present the discovered component paths as options (e.g., `src/api`, `core/models`). Allow selecting multiple.

## Step 3: Load Detailed Context

Based on selection, run:

```bash
python3 .claude/skills/repo-context/scripts/context_loader.py --phase detail --modules "<selected_paths>"
```

This loads:
- Full README content for selected modules
- Auto-resolved dependencies from YAML `depends_on`
- Related tools that reference the components

## Step 4: Remind About Standards

After loading, remind the user:
- Components need YAML frontmatter in README.md to be discoverable
- Template at `.claude/skills/repo-context/templates/component-readme.md`
- Validate with: `python3 .claude/skills/repo-context/scripts/validate_readmes.py`
