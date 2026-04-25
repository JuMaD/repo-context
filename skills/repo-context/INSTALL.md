# Installing the `repo-context` skill

Two ways to install this into your repo (or your global Claude Code setup). Pick one.

---

## Option A — As a Claude Code plugin (recommended)

**When to use:** you want one-command install, automatic updates, and the skill to be shareable across all your repos.

```bash
/plugin install github.com/JuMaD/repo-context
```

Claude Code registers the `/repo-context` and `/repo-plans` commands and the skill automatically. The plugin manifest at `.claude-plugin/plugin.json` declares `pyyaml` as a dependency, so no separate install step is needed.

To uninstall:
```bash
/plugin uninstall repo-context
```

---

## Option B — Manual drop-in (no plugin)

**When to use:** you want the skill inside a single repo, checked in alongside its code (so teammates get it via `git pull`), or you can't use the plugin system.

### Steps

1. **Copy the skill directory** into the target repo at `.claude/skills/repo-context/`:

   ```bash
   cp -R .claude/skills/repo-context <target-repo>/.claude/skills/
   ```

2. **Copy the two slash commands** into the target repo at `.claude/commands/`:

   ```bash
   cp .claude/commands/repo-context.md <target-repo>/.claude/commands/
   cp .claude/commands/repo-plans.md   <target-repo>/.claude/commands/
   ```

3. **Install PyYAML** in the target repo's Python environment (scripts require it):

   ```bash
   pip install pyyaml       # or: uv add pyyaml
   ```

4. **(Optional but recommended) Nudge Claude to use it.** Add a line to the target repo's `CLAUDE.md`:

   ```markdown
   ## Context Loading

   When entering plan mode or starting substantial work, run `/repo-context`
   first to load relevant component context before exploring the codebase.
   ```

   Without this nudge, Claude has the skill available but won't invoke it on its own until the user types `/repo-context`.

### Verify

```bash
# From the target repo root:
python3 .claude/skills/repo-context/scripts/validate_readmes.py
python3 .claude/skills/repo-context/scripts/context_loader.py --phase overview
```

If the overview comes back empty, your repo has no READMEs with `component:` or `container:` frontmatter yet. Run:

```bash
python3 .claude/skills/repo-context/scripts/validate_readmes.py --fix --dry-run
```

to preview which files would get stub frontmatter inserted.

---

## Usage once installed

| Command | What it does |
|---------|--------------|
| `/repo-context` | Interactive: show all components, let user pick which to load in detail (with auto-resolved deps). |
| `/repo-plans` | Interactive: show active plans with focus and NOW/NEXT streams, let user drill in. |
| `scripts/extract_repo_context.py` | Non-interactive batch extractor — produces a static Markdown or YAML document at levels 0/1/full/plans/diagrams. Good for CI, generated docs, or piping to another LLM. |
| `scripts/validate_readmes.py` | Lint README and plan frontmatter. `--fix` inserts stub frontmatter where missing. `--strict` for CI. |

## Author-the-metadata workflow

1. `python3 scripts/validate_readmes.py --fix` — inserts stubs in files with no frontmatter at all.
2. Edit each touched file, replace the `TODO:` placeholders with real content. The templates under `templates/` and filled-in examples under `examples/` show what "good" looks like.
3. `python3 scripts/validate_readmes.py` — confirm everything validates.
4. `python3 scripts/context_loader.py --phase overview` — sanity-check the component listing.

## Troubleshooting

**"No components with YAML frontmatter found."** Your READMEs have no frontmatter yet. Run `validate_readmes.py --fix` to insert stubs.

**`/repo-context` command isn't recognized.** Check that `.claude/commands/repo-context.md` exists in the repo root. Claude Code only discovers commands in `.claude/commands/` (project-scoped) or `~/.claude/commands/` (user-scoped).

**`PyYAML required` error.** Install it in whichever Python environment is on `PATH` when Claude runs `python3`. In `uv`-managed projects: `uv add pyyaml`.
