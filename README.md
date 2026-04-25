# repo-context

Hierarchical, lazy-loaded repository context for [Claude Code](https://claude.ai/code). Instead of stuffing every module summary into a root `CLAUDE.md`, each component in your repo owns its own metadata in its `README.md`, and Claude loads only what's relevant to the current task.

Ships as a Claude Code plugin with two slash commands (`/repo-context`, `/repo-plans`) and the Python scripts that power them.

## Table of contents

- [Why](#why)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Schemas](#schemas)
- [Documentation](#documentation)
- [Requirements](#requirements)
- [Repository layout](#repository-layout)
- [Contributing](#contributing)
- [License](#license)

## Why

A growing `CLAUDE.md` eventually hits two problems:

1. **Cost** — every module summary gets loaded on every turn, whether relevant or not.
2. **Drift** — the root file lags behind the code because it lives far from the thing it describes.

`repo-context` solves both by colocating metadata with the code it describes (YAML frontmatter in each component's `README.md`) and loading it on demand via slash commands.

## Features

- **Component discovery** — every `README.md` with `component:` or `container:` frontmatter becomes a discoverable node.
- **Plan discovery** — every `_plan.md` or `_<word>_plan.md` with `plan:` frontmatter surfaces roadmap state (focus, NOW/NEXT streams, open questions, recent decisions).
- **Auto-resolved dependencies** — loading a component in detail pulls in its declared `depends_on` components too.
- **Related-tool detection** — scripts under `tools/` or `scripts/` that import a component show up alongside it.
- **Linter with autofix** — `validate_readmes.py --fix` inserts stub frontmatter into files that don't have any.
- **Static extractor** — `extract_repo_context.py` produces a one-shot Markdown or YAML document at five verbosity levels. Good for CI, generated docs, or piping to another LLM.
- **Safe defaults** — skips `.git`, `node_modules`, `.venv`, build/cache dirs, and `.claude` itself.

## Installation

### Option A — As a Claude Code plugin (recommended)

One-command install from Claude Code:

```
/plugin install github.com/JuMaD/repo-context
```

Claude Code registers both slash commands and the skill automatically. The plugin manifest declares `pyyaml` as a dependency, so no separate pip step is needed.

To uninstall:

```
/plugin uninstall repo-context
```

### Option B — Manual drop-in

If you want the skill checked into one specific project (so teammates get it via `git pull`):

```bash
cd <target-repo>
mkdir -p .claude/skills .claude/commands
cp -R <path-to-this-repo>/skills/repo-context .claude/skills/
cp    <path-to-this-repo>/commands/*.md       .claude/commands/
pip install pyyaml   # or: uv add pyyaml
```

See [`skills/repo-context/INSTALL.md`](./skills/repo-context/INSTALL.md) for the full walkthrough, the post-install `CLAUDE.md` nudge, and troubleshooting.

## Quick start

From any repo with READMEs that have YAML frontmatter:

```
/repo-context    # interactive: pick modules, auto-resolve deps
/repo-plans      # interactive: active plans, NOW/NEXT streams
```

No frontmatter yet? Let the linter stub it for you:

```bash
python3 .claude/skills/repo-context/scripts/validate_readmes.py --fix --dry-run  # preview
python3 .claude/skills/repo-context/scripts/validate_readmes.py --fix            # apply
```

You can also drive the scripts directly:

```bash
# List every discoverable component
python3 .claude/skills/repo-context/scripts/context_loader.py --phase overview

# Deep dive on one or more modules (auto-resolves depends_on)
python3 .claude/skills/repo-context/scripts/context_loader.py \
    --phase detail --modules core/parser,apps/example_app

# One-shot static context document
python3 .claude/skills/repo-context/scripts/extract_repo_context.py --level 1

# Lint frontmatter (use --strict in CI)
python3 .claude/skills/repo-context/scripts/validate_readmes.py --strict
```

## How it works

1. A **component** is any directory whose `README.md` starts with `component:` or `container:` YAML frontmatter.
2. A **plan** is any `_plan*.md` or `_<word>_plan*.md` with `plan:` frontmatter (the underscore prefix keeps narrative docs like `rollout_plan.md` from being mis-classified).
3. The scripts walk the repo from its root (auto-detected via `.git`, `pyproject.toml`, or `package.json`), skipping `.git`, `node_modules`, `.venv`, build/cache dirs, and `.claude` itself.
4. Root `README.md` is skipped — it's treated as `CLAUDE.md` territory.
5. Dependency resolution is **exact-match** on the dotted path, so `core.parser` will not incorrectly resolve to `core/preparser`.

## Schemas

### Component README — minimal

```yaml
---
component:
  name: "Human-readable name"
  does: "One sentence — what does this component take in and return?"
---
```

### Component README — recommended

```yaml
---
component:
  name: Parser
  does: "Takes raw text, returns a typed AST."
  import: "from core.parser import Parser"
  key_methods:
    - "parse(source: str) -> AST"
  depends_on:
    - component: core.fetcher
      why: "Loads source files before parsing."
---
```

### Container README (directory index)

```yaml
---
container:
  name: Core Libraries
  does: "Reusable, application-agnostic building blocks."
  type: index           # index | documentation | testing | infrastructure | tools
  contains:
    - core/parser
    - core/fetcher
---
```

### Plan file

```yaml
---
plan:
  name: "Parser v2"
  for: "core/parser"
  type: architecture    # roadmap | architecture | runbook | eval | implementation | feature
  status: active        # active | paused | completed | archived | retired
  last_updated: 2026-04-23
  focus: "Required when status=active — what to prioritize now."
  streams:
    - name: "Typed AST"
      priority: now     # now | next | later | done
      status: in_progress
      tasks: 5
      done: 2
---
```

Full schemas, all fields, and filled-in examples live in [`skills/repo-context/SKILL.md`](./skills/repo-context/SKILL.md), [`skills/repo-context/templates/`](./skills/repo-context/templates/), and [`skills/repo-context/examples/`](./skills/repo-context/examples/).

## Documentation

| Doc | Purpose |
|-----|---------|
| [`skills/repo-context/SKILL.md`](./skills/repo-context/SKILL.md) | Full schemas, slash-command reference, script flags |
| [`skills/repo-context/INSTALL.md`](./skills/repo-context/INSTALL.md) | Both install paths, troubleshooting, adoption workflow |
| [`skills/repo-context/templates/`](./skills/repo-context/templates/) | Empty frontmatter stubs |
| [`skills/repo-context/examples/`](./skills/repo-context/examples/) | Filled-in component, CLI, container, and plan examples |

## Requirements

- Python 3.10+
- [PyYAML](https://pyyaml.org/) 6+ (installed automatically when used via the plugin; manual drop-in users install it themselves)

## Repository layout

```
repo-context/
├── .claude-plugin/
│   └── plugin.json              ← plugin manifest
├── skills/
│   └── repo-context/
│       ├── SKILL.md             ← skill manifest
│       ├── INSTALL.md
│       ├── scripts/
│       │   ├── _common.py
│       │   ├── context_loader.py
│       │   ├── extract_repo_context.py
│       │   └── validate_readmes.py
│       ├── templates/
│       └── examples/
├── commands/
│   ├── repo-context.md
│   └── repo-plans.md
├── README.md
├── LICENSE
└── .gitignore
```

## Contributing

Issues and pull requests welcome. If you're proposing a schema change, please open an issue first so we can talk through compatibility — existing frontmatter in downstream repos is the main constraint.

## License

MIT — see [`LICENSE`](./LICENSE).
