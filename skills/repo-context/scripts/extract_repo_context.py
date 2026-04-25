#!/usr/bin/env python3
"""
Non-interactive repo context extractor.

Sibling to `context_loader.py`. Where `context_loader.py` is designed for
interactive slash-command use (user picks modules), this script produces a
single static document at one of several verbosity levels — useful for
piping into a file, committing as generated docs, or handing to a remote LLM.

Levels:
    0          One-line overview per component (~150 tokens).
    1          Component summaries with key methods and deps (~800 tokens).
    full       Complete README content for modules matching --scope.
    plans      Cross-cutting roadmap view from all _plan*.md files.
    diagrams   All Mermaid files from the diagrams directory.

Usage:
    python3 extract_repo_context.py --level 0
    python3 extract_repo_context.py --level 1
    python3 extract_repo_context.py --level full --scope core/parser,core/fetcher
    python3 extract_repo_context.py --level plans
    python3 extract_repo_context.py --level diagrams --diagrams-dir docs/architecture
    python3 extract_repo_context.py --format yaml
    python3 extract_repo_context.py --output REPO_CONTEXT.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    extract_file_body,
    extract_yaml_frontmatter,
    find_all_plans,
    find_all_readmes,
    find_project_root,
    truncate,
    yaml,
)


def _repo_title(root_dir: Path, override: Optional[str]) -> str:
    if override:
        return override
    return root_dir.name.replace("_", " ").replace("-", " ").title()


def extract_tool_sections(tools_readme: Path) -> List[Dict[str, Optional[str]]]:
    r"""Parse tool entries from a `tools/README.md`.

    Expects each tool to be a `###` or `####` section with a backtick-wrapped
    name, e.g. `### \`my_tool.py\``. The skill doesn't require this file to
    exist — it's a convenience for repos that already maintain a tool index.
    """
    if not tools_readme.exists():
        return []
    content = tools_readme.read_text(encoding="utf-8")
    pattern = (
        r"#{3,4}\s+`([^`]+)`\s*\n(.*?)"
        r"(?=#{3,4}\s+`|#{2,3}\s+[^`]|---|\Z)"
    )
    tools: List[Dict[str, Optional[str]]] = []
    for match in re.finditer(pattern, content, re.DOTALL):
        name = match.group(1)
        body = match.group(2).strip()
        purpose_match = re.match(r"(.*?)(?:\n\n|\n```)", body, re.DOTALL)
        purpose = purpose_match.group(1).strip() if purpose_match else body[:200]
        usage_match = re.search(r"```(?:bash)?\n(.*?)\n```", body, re.DOTALL)
        usage = usage_match.group(1).strip() if usage_match else None
        tools.append({"name": name, "purpose": purpose, "usage": usage})
    return tools


def find_mermaid_diagrams(diagrams_dir: Path, root_dir: Path) -> List[Tuple[str, str]]:
    if not diagrams_dir.exists():
        return []
    out: List[Tuple[str, str]] = []
    for path in diagrams_dir.rglob("*.mermaid"):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Warning: could not read {path}: {e}", file=sys.stderr)
            continue
        out.append((str(path.relative_to(root_dir)), content))
    return sorted(out)


def _component_one_liner(metadata: Dict[str, Any], fallback_name: str) -> Tuple[str, str]:
    comp = metadata.get("component") or {}
    name = comp.get("name", fallback_name)
    purpose = comp.get("does", comp.get("purpose", ""))
    if "." in purpose:
        purpose = purpose.split(".")[0] + "."
    else:
        purpose = truncate(purpose, max_chars=77)
    return name, purpose


def generate_level_0(
    title: str,
    core_modules: Sequence[Tuple[str, Dict[str, Any]]],
    other_components: Sequence[Tuple[str, Dict[str, Any]]],
) -> str:
    lines = [f"# {title} — System Overview", "", "## Core Modules", ""]
    for path, metadata in core_modules:
        name, purpose = _component_one_liner(metadata, Path(path).parent.name)
        lines.append(f"- **{name}**: {purpose}")
    if other_components:
        lines += ["", "## Other Components", ""]
        for path, metadata in other_components:
            name, purpose = _component_one_liner(metadata, Path(path).parent.name)
            lines.append(f"- **{name}**: {purpose}")
    lines += [
        "",
        "---",
        "Use `--level 1` for methods/deps, `--level full --scope <module>` for complete docs.",
    ]
    return "\n".join(lines)


def generate_level_1(
    title: str,
    core_modules: Sequence[Tuple[str, Dict[str, Any]]],
    tools: Sequence[Dict[str, Optional[str]]],
    other_components: Sequence[Tuple[str, Dict[str, Any]]],
) -> str:
    lines = [f"# {title} Repository Context", "", "**Auto-generated**", ""]

    if core_modules:
        lines += ["## Core Modules", ""]
        for path, metadata in core_modules:
            comp = metadata.get("component") or {}
            interfaces = metadata.get("interfaces") or {}
            name = comp.get("name", Path(path).parent.name)
            lines += [f"### {name}", ""]
            if purpose := comp.get("purpose", comp.get("does")):
                lines += [f"**Purpose:** {purpose}", ""]
            if import_path := comp.get("import"):
                lines += [f"**Import:** `{import_path}`", ""]
            if key_methods := comp.get("key_methods"):
                methods = ", ".join(f"`{m}`" for m in key_methods[:5])
                lines += [f"**Methods:** {methods}", ""]
            io_parts: List[str] = []
            if input_type := comp.get("input"):
                io_parts.append(f"In: `{input_type}`")
            if output_type := comp.get("output"):
                io_parts.append(f"Out: `{output_type}`")
            if io_parts:
                lines += [f"**I/O:** {' | '.join(io_parts)}", ""]
            if deps := interfaces.get("dependencies"):
                dep_names: List[str] = []
                for dep in deps:
                    if isinstance(dep, str):
                        dep_names.append(dep)
                    elif isinstance(dep, dict) and dep:
                        dep_names.append(next(iter(dep.keys())))
                if dep_names:
                    lines += [f"**Depends on:** {', '.join(dep_names)}", ""]

    if tools:
        lines += ["## Tools", ""]
        tool_names = [f"`{t['name']}`" for t in tools[:10]]
        lines += [" | ".join(tool_names), ""]

    if other_components:
        lines += ["## Other Components", ""]
        for path, metadata in other_components:
            name, purpose = _component_one_liner(metadata, Path(path).parent.name)
            lines.append(f"- **{name}**: {purpose}")
        lines.append("")

    lines += ["---", "Use `--level full --scope <module>` for complete documentation."]
    return "\n".join(lines)


def generate_level_full(
    title: str,
    core_modules: Sequence[Tuple[str, Dict[str, Any]]],
    tools: Sequence[Dict[str, Optional[str]]],
    other_components: Sequence[Tuple[str, Dict[str, Any]]],
    scope: Sequence[str],
    repo_root: Path,
) -> str:
    lines = [
        f"# {title} — Full Context",
        "",
        f"**Scope:** {', '.join(scope) if scope else 'all'}",
        "",
    ]

    for path, metadata in (*core_modules, *other_components):
        module_dir = str(Path(path).parent)
        if scope and not any(
            module_dir == s or module_dir.startswith(s.rstrip("/") + "/")
            for s in scope
        ):
            continue
        comp = metadata.get("component") or {}
        name = comp.get("name", Path(path).parent.name)
        lines += [f"## {name}", "", f"**Location:** `{path}`", ""]
        if body := extract_file_body(repo_root / path):
            lines += [body, "", "---", ""]

    if tools and (not scope or any("tools" in s for s in scope)):
        lines += ["## Available Tools", ""]
        for tool in tools:
            lines += [f"### {tool['name']}", "", str(tool.get("purpose", "")), ""]
            if usage := tool.get("usage"):
                lines += ["```bash", usage, "```", ""]

    return "\n".join(lines)


def generate_level_diagrams(
    title: str,
    diagrams: Sequence[Tuple[str, str]],
    diagrams_dir_label: str,
) -> str:
    if not diagrams:
        return (
            f"# {title} — Architecture Diagrams\n\n"
            f"No Mermaid files found under `{diagrams_dir_label}`."
        )
    lines = [f"# {title} — Architecture Diagrams", ""]
    for path, content in diagrams:
        name = Path(path).stem.replace("-", " ").replace("_", " ").title()
        lines += [
            f"## {name}",
            "",
            f"**File:** `{path}`",
            "",
            "```mermaid",
            content.strip(),
            "```",
            "",
        ]
    return "\n".join(lines)


def generate_level_plans(title: str, root_dir: Path) -> str:
    plans: List[Tuple[str, Dict[str, Any]]] = []
    for plan_path in find_all_plans(root_dir):
        metadata, _err = extract_yaml_frontmatter(plan_path)
        if not metadata or "plan" not in metadata:
            continue
        plans.append((str(plan_path.relative_to(root_dir)), metadata["plan"]))

    if not plans:
        return f"# {title} — Plans\n\nNo plans with YAML frontmatter found."

    active = [(p, m) for p, m in plans if m.get("status") == "active"]
    other = [(p, m) for p, m in plans if m.get("status") != "active"]

    lines = [
        f"# {title} — Plans",
        "",
        f"**{len(plans)} plans** ({len(active)} active)",
        "",
    ]

    now_streams: List[Dict[str, Any]] = []
    next_streams: List[Dict[str, Any]] = []
    later_streams: List[Dict[str, Any]] = []

    for path, plan in active:
        for s in plan.get("streams") or []:
            if not isinstance(s, dict):
                continue
            entry = {
                "name": s.get("name", ""),
                "plan": plan.get("name", path),
                "status": s.get("status", ""),
                "tasks": s.get("tasks"),
                "done": s.get("done", 0),
                "blocked_by": s.get("blocked_by", ""),
            }
            bucket = {
                "now": now_streams,
                "next": next_streams,
                "later": later_streams,
            }.get(s.get("priority", "later"))
            if bucket is not None:
                bucket.append(entry)

    def fmt(s: Dict[str, Any]) -> str:
        progress = f" [{s['done']}/{s['tasks']}]" if s["tasks"] else ""
        blocked = f" (blocked by: {s['blocked_by']})" if s["blocked_by"] else ""
        return f"- **{s['name']}** [{s['plan']}] ({s['status']}{progress}){blocked}"

    for header, bucket in (("Now", now_streams), ("Next", next_streams), ("Later", later_streams)):
        if bucket:
            lines += [f"## {header}", ""]
            lines += [fmt(s) for s in bucket]
            lines.append("")

    if active:
        lines += ["## Active Plan Focus", ""]
        for path, plan in active:
            lines.append(
                f"- **{plan.get('name', path)}** "
                f"({plan.get('type', '')}): {plan.get('focus', '')}"
            )
        lines.append("")

    if other:
        lines += ["## Other Plans", ""]
        for path, plan in other:
            lines.append(
                f"- **{plan.get('name', path)}** ({plan.get('status', '')}) - `{path}`"
            )
        lines.append("")

    questions: List[Tuple[str, str]] = []
    for path, plan in plans:
        for q in plan.get("questions") or []:
            questions.append((plan.get("name", path), q))
    if questions:
        lines += ["## Open Questions", ""]
        for plan_name, q in questions:
            lines.append(f"- [{plan_name}] {q}")
        lines.append("")

    decisions: List[Dict[str, str]] = []
    for path, plan in plans:
        for d in plan.get("decisions") or []:
            if isinstance(d, dict):
                decisions.append({
                    "plan": plan.get("name", path),
                    "decision": d.get("decision", ""),
                    "date": str(d.get("date", "")),
                })
    if decisions:
        decisions.sort(key=lambda x: x["date"], reverse=True)
        lines += ["## Recent Decisions", ""]
        for d in decisions[:10]:
            lines.append(f"- [{d['plan']}] {d['decision']} ({d['date']})")
        lines.append("")

    return "\n".join(lines)


def generate_yaml_output(
    repo_name: str,
    core_modules: Sequence[Tuple[str, Dict[str, Any]]],
    tools: Sequence[Dict[str, Optional[str]]],
    other_components: Sequence[Tuple[str, Dict[str, Any]]],
) -> str:
    context: Dict[str, Any] = {
        "repository": repo_name,
        "core_modules": [{"path": p, **m} for p, m in core_modules],
        "tools": list(tools),
        "other_components": [{"path": p, **m} for p, m in other_components],
    }
    return yaml.dump(context, default_flow_style=False, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract repository context from READMEs, plans, and diagrams",
    )
    parser.add_argument("--output", "-o", type=Path, help="Output file (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "yaml"],
        default="markdown",
    )
    parser.add_argument(
        "--level",
        "-l",
        choices=["0", "1", "full", "plans", "diagrams"],
        default="1",
    )
    parser.add_argument(
        "--scope",
        "-s",
        type=str,
        help="Comma-separated module paths (only for --level full)",
    )
    parser.add_argument(
        "--core-prefix",
        type=str,
        default="core/",
        help="Path prefix that marks 'core' modules (default: core/).",
    )
    parser.add_argument(
        "--tools-readme",
        type=str,
        default="tools/README.md",
        help="Path to the tools index README (default: tools/README.md).",
    )
    parser.add_argument(
        "--diagrams-dir",
        type=str,
        default="docs/diagrams",
        help="Directory with Mermaid files (default: docs/diagrams).",
    )
    parser.add_argument(
        "--repo-name",
        type=str,
        help="Override the repo title (default: derived from project root dir name).",
    )

    args = parser.parse_args()
    root_dir = find_project_root()
    title = _repo_title(root_dir, args.repo_name)

    scope = [s.strip() for s in (args.scope or "").split(",") if s.strip()]

    print("Scanning repository for READMEs...", file=sys.stderr)
    readmes = find_all_readmes(root_dir)
    print(f"  Found {len(readmes)} README files", file=sys.stderr)

    core_modules: List[Tuple[str, Dict[str, Any]]] = []
    other_components: List[Tuple[str, Dict[str, Any]]] = []
    core_prefix = args.core_prefix.rstrip("/") + "/"

    for readme in readmes:
        if readme.parent == root_dir:
            continue
        relative = str(readme.relative_to(root_dir))
        metadata, _err = extract_yaml_frontmatter(readme)
        # Only emit components — containers are directory-index metadata, not
        # things to show in the component listing.
        if not metadata or "component" not in metadata:
            continue
        bucket = core_modules if relative.startswith(core_prefix) else other_components
        bucket.append((relative, metadata))

    print(f"  {len(core_modules)} core, {len(other_components)} other", file=sys.stderr)

    tools = extract_tool_sections(root_dir / args.tools_readme)
    if tools:
        print(f"  Found {len(tools)} tool entries in {args.tools_readme}", file=sys.stderr)

    if args.format == "yaml":
        output = generate_yaml_output(title, core_modules, tools, other_components)
    elif args.level == "0":
        output = generate_level_0(title, core_modules, other_components)
    elif args.level == "1":
        output = generate_level_1(title, core_modules, tools, other_components)
    elif args.level == "full":
        output = generate_level_full(
            title, core_modules, tools, other_components, scope, root_dir
        )
    elif args.level == "plans":
        output = generate_level_plans(title, root_dir)
    else:  # diagrams
        diagrams = find_mermaid_diagrams(root_dir / args.diagrams_dir, root_dir)
        output = generate_level_diagrams(title, diagrams, args.diagrams_dir)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote {len(output)} chars to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
