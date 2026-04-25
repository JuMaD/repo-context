"""
Shared helpers for the repo-context skill.

Kept minimal on purpose — both context_loader.py and validate_readmes.py
must be runnable standalone (`python3 scripts/context_loader.py ...`), so
this module has no third-party deps beyond PyYAML (which the scripts
already require).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)


# Directories never scanned for READMEs or plans.
EXCLUDE_DIRS = frozenset({
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "archive",
    "z_archive",
    "dist",
    "build",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "egg-info",
    ".eggs",
    ".claude",
})


# Plan-file naming convention: any markdown file starting with `_plan` or
# matching `_<word>_plan*` (e.g. `_eval_plan.md`, `_feedback_plan.md`).
# Files must use the underscore prefix to be discovered — this avoids
# accidentally picking up narrative docs like `rollout_plan.md`.
PLAN_GLOBS: Tuple[str, ...] = (
    "**/_plan*.md",
    "**/_*_plan*.md",
)


def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk upward from `start` (or cwd) looking for a repo marker."""
    current = (start or Path.cwd()).resolve()
    markers = (".git", "pyproject.toml", "package.json")
    for parent in [current, *current.parents]:
        if any((parent / m).exists() for m in markers):
            return parent
    return current


def extract_yaml_frontmatter(
    file_path: Path,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse `---\\n...\\n---` frontmatter. Returns (metadata, error_message)."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"Read error: {e}"

    if not content.startswith("---"):
        return None, "No YAML frontmatter"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None, "Malformed frontmatter (missing closing ---)"

    try:
        return yaml.safe_load(match.group(1)) or {}, None
    except yaml.YAMLError as e:
        return None, f"YAML error: {e}"


def extract_file_body(file_path: Path) -> str:
    """Return file content after the YAML frontmatter block."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    if content.startswith("---"):
        match = re.match(r"^---\n.*?\n---\n?(.*)", content, re.DOTALL)
        if match:
            return match.group(1).strip()
    return content.strip()


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def find_all_readmes(root_dir: Path) -> List[Path]:
    """All README.md files below `root_dir`, excluding vendor/build dirs."""
    return sorted(
        p for p in root_dir.rglob("README.md") if not _is_excluded(p)
    )


def find_all_plans(root_dir: Path) -> List[Path]:
    """All plan files (`_plan*.md`, `_<word>_plan*.md`) below `root_dir`."""
    plans: set[Path] = set()
    for pattern in PLAN_GLOBS:
        for p in root_dir.glob(pattern):
            if not _is_excluded(p):
                plans.add(p)
    return sorted(plans)


def truncate(text: str, max_chars: int = 97, suffix: str = "...") -> str:
    """Truncate at a whitespace boundary where possible to avoid mid-word cuts."""
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    last_space = window.rfind(" ")
    if last_space > max_chars - 20:
        window = window[:last_space]
    return window.rstrip() + suffix
