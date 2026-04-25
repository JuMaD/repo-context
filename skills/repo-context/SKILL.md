---
name: repo-context
description: Hierarchical context loading from READMEs with YAML frontmatter. Discovers components, asks which to focus on, auto-resolves dependencies.
---

# Repository Context Loader

Structured, lazy-loaded context for any codebase whose components declare YAML frontmatter in their `README.md` files. Instead of stuffing every module summary into a root `CLAUDE.md`, each component owns its own metadata and Claude loads only what's relevant to the task.

## Quick start

```bash
/repo-context        # interactive: pick modules, load with deps
/repo-plans          # interactive: show active plans and NOW/NEXT streams
```

Or drive the scripts directly:

```bash
# Non-interactive listing (stdout)
python3 .claude/skills/repo-context/scripts/context_loader.py --phase overview

# Deep dive on one or more modules (auto-resolves depends_on)
python3 .claude/skills/repo-context/scripts/context_loader.py \
    --phase detail --modules core/parser,apps/example_app

# One-shot static context doc (levels 0/1/full/plans/diagrams)
python3 .claude/skills/repo-context/scripts/extract_repo_context.py --level 1

# Lint READMEs and plans
python3 .claude/skills/repo-context/scripts/validate_readmes.py
```

## Installation

See [`INSTALL.md`](./INSTALL.md) for both paths:

- **Plugin** (one-command install via `/plugin install`) — recommended for sharing across repos.
- **Manual drop-in** (copy `.claude/skills/repo-context/` and the two slash commands).

## Directory layout

```
.claude/skills/repo-context/
├── SKILL.md                     ← this file
├── INSTALL.md                   ← manual + plugin install paths
├── scripts/
│   ├── _common.py               ← shared frontmatter/discovery helpers
│   ├── context_loader.py        ← interactive overview/detail + plans
│   ├── extract_repo_context.py  ← non-interactive batch extractor
│   └── validate_readmes.py      ← linter, with --fix for stub frontmatter
├── templates/
│   ├── component-readme.md      ← component schema, empty
│   ├── container-readme.md      ← container schema, empty
│   └── plan.md                  ← plan schema, empty
└── examples/
    ├── library-component.md     ← filled-in reusable-library component
    ├── cli-tool.md              ← filled-in CLI tool (type: cli)
    ├── container.md             ← filled-in directory-index README
    └── _plan.md                 ← filled-in active architecture plan
```

The plugin manifest lives at the repo root in [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json) — see the root [`README.md`](../../README.md) for packaging details.

## How discovery works

1. Every `README.md` with YAML frontmatter is a potential component or container.
2. Every `_plan*.md` or `_<word>_plan*.md` with `plan:` frontmatter is a plan.
3. Standard ignore list: `.git`, `.venv`, `node_modules`, `__pycache__`, `dist`, `build`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `archive`, `z_archive`, `.claude`, and a few others (see `scripts/_common.py`).
4. Root-level `README.md` is skipped (treat it as CLAUDE.md territory).

## Schemas

### Component README

Required:

```yaml
---
component:
  name: "Human-readable name"
  does: "One sentence — what does this component take in and return?"
---
```

Recommended (skip `import`/`key_methods` for CLI-style components by adding `type: cli`):

```yaml
---
component:
  name: Foo Bar
  does: "Takes X, returns Y."
  import: "from pkg.foo import Bar"
  key_methods:
    - "method(arg: Type) -> ReturnType"
  depends_on:
    - component: other.module
      why: "What this dependency provides"
  interfaces:
    external_apis:
      - name: ExampleAPI
        purpose: "What we use it for"
        env_vars: [EXAMPLE_API_KEY]
---
```

See [`templates/component-readme.md`](./templates/component-readme.md) (empty schema) and [`examples/library-component.md`](./examples/library-component.md), [`examples/cli-tool.md`](./examples/cli-tool.md) (filled-in).

### Container README (directory index)

For aggregator READMEs at directory roots (`core/README.md`, `applications/README.md`):

```yaml
---
container:
  name: "Directory Name"
  does: "One sentence — what's under this directory."
  type: index            # index | documentation | testing | infrastructure | tools
  contains:
    - path/to/component1
    - path/to/component2
---
```

See [`templates/container-readme.md`](./templates/container-readme.md) and [`examples/container.md`](./examples/container.md).

### Plan file (`_plan.md`, `_<stream>_plan.md`)

```yaml
---
plan:
  name: "Plan name"
  for: "component/path"
  type: roadmap              # roadmap | architecture | runbook | eval | implementation | feature
  status: active             # active | paused | completed | archived | retired
  last_updated: 2026-01-15
  focus: "Required when status=active — what to prioritize now"
  streams:
    - name: "Stream name"
      priority: now           # now | next | later | done
      status: in_progress     # not_started | in_progress | blocked | done | implemented
      tasks: 5
      done: 2
      blocked_by: ""
  questions:
    - "Open question"
  decisions:
    - decision: "What was decided"
      date: 2026-01-15
      context: "Why"
---
```

Naming convention: plans must start with an underscore (`_plan.md`, `_eval_plan.md`, `_rollout_plan.md`). Files without the underscore prefix are ignored so narrative docs don't get mis-classified.

See [`templates/plan.md`](./templates/plan.md) and [`examples/_plan.md`](./examples/_plan.md).

## Slash commands

### `/repo-context`

1. Runs `context_loader.py --phase overview` to list all components grouped by top-level directory.
2. Uses `AskUserQuestion` to ask which module(s) to load in detail.
3. Runs `context_loader.py --phase detail --modules <selection>` — pulls full READMEs plus auto-resolved dependencies and any related tool scripts under `tools/` or `scripts/`.

### `/repo-plans`

1. Runs `context_loader.py --phase plans` to show active plans with focus and NOW/NEXT streams, open questions, and recent decisions.
2. Asks which plan(s) to load in full.
3. Runs `context_loader.py --phase plan-detail --modules <paths>` for complete plan bodies.

## Scripts in detail

### `context_loader.py`

Four phases: `overview`, `detail`, `plans`, `plan-detail`. JSON output with `--format json`. Tool-directory detection is configurable via `--tool-dirs` (default `tools,scripts`).

Dependency resolution is exact-match on the dotted path (e.g. `core.parser` maps to module path `core/parser`). No loose substring matching — `core.parser` will not incorrectly resolve to `core/preparser`.

### `extract_repo_context.py`

Non-interactive sibling. Produces a single static document at one of five levels:

| Level | Tokens | Best for |
|-------|--------|----------|
| `0` | ~150 | Quick orientation, one-liner per component. |
| `1` | ~800 | Component summaries with methods, I/O, and deps. Default. |
| `full` | 2000+ | Complete READMEs for modules matching `--scope`. |
| `plans` | varies | Cross-cutting roadmap across all plan files. |
| `diagrams` | varies | Embeds all Mermaid files from `--diagrams-dir`. |

Also accepts `--format yaml` for machine-readable output, `--repo-name` to override the auto-derived title, and `--core-prefix` / `--tools-readme` / `--diagrams-dir` if your repo uses different conventions.

### `validate_readmes.py`

Reports missing frontmatter, schema errors, and soft warnings:

```bash
python3 scripts/validate_readmes.py                  # report
python3 scripts/validate_readmes.py --verbose        # + warnings
python3 scripts/validate_readmes.py --strict         # exit 1 on any error — good for CI
python3 scripts/validate_readmes.py --json           # machine-readable
python3 scripts/validate_readmes.py --fix            # insert stub frontmatter into files that have none
python3 scripts/validate_readmes.py --fix --dry-run  # preview --fix without writing
```

`--fix` only touches files that have **no** frontmatter. It refuses to overwrite existing frontmatter, even if malformed — the error report tells you where to edit by hand.

## Typical adoption workflow

1. Drop the skill into `.claude/skills/repo-context/` (see [`INSTALL.md`](./INSTALL.md)).
2. Run `python3 scripts/validate_readmes.py --fix --dry-run` to preview which READMEs need stubs.
3. Run without `--dry-run` to insert stubs.
4. Edit the touched files, replacing `TODO:` placeholders using [`templates/`](./templates/) and [`examples/`](./examples/) as references.
5. `python3 scripts/validate_readmes.py` to confirm validation is clean.
6. `/repo-context` in Claude Code to verify everything shows up.

## Interaction with `CLAUDE.md`

This skill does **not** replace `CLAUDE.md`. Use them complementarily:

- `CLAUDE.md`: always-relevant, project-wide context (env setup, commands, conventions, safety rules). Loaded into every conversation.
- `repo-context` skill: component-level context, loaded on demand. Replaces the "what lives in `core/`, `applications/`, `evals/`" section that would otherwise bloat CLAUDE.md.

To make Claude actually reach for the skill, add a one-liner to `CLAUDE.md`:

```markdown
## Context Loading

When entering plan mode or starting substantial work, run `/repo-context`
first to load relevant component context before exploring the codebase.
```
