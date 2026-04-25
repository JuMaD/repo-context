---
component:
  name: Release Notes Generator
  does: "Reads conventional commits between two refs and writes a Markdown changelog to stdout."
  type: cli
---

# Release Notes Generator

Generate Markdown release notes from conventional commits (`feat:`, `fix:`, `chore:`, …) between two git refs.

## Usage

```bash
# Default: since last tag
python3 tools/release_notes.py

# Between two refs
python3 tools/release_notes.py --from v1.2.0 --to HEAD

# Write to file instead of stdout
python3 tools/release_notes.py --output CHANGELOG-v1.3.0.md
```

## Flags

| Flag | Default | Notes |
|------|---------|-------|
| `--from` | last tag | Inclusive start ref. |
| `--to` | `HEAD` | Exclusive end ref. |
| `--output` | stdout | Path to write notes. |
| `--group-by` | `type` | `type` or `scope`. |

## Notes

- Commits without a conventional prefix are grouped under "Other".
- Merge commits are skipped.
- Breaking changes (body contains `BREAKING CHANGE:`) are surfaced to the top.
