#!/usr/bin/env python3
"""
Context loader for the repo-context skill.

Phases:
    overview       List all components with purposes and dependencies.
    detail         Load full README bodies for selected modules (+ deps).
    plans          List all plan files with focus and NOW/NEXT streams.
    plan-detail    Load full plan bodies for selected plans.

Usage:
    python3 context_loader.py --phase overview
    python3 context_loader.py --phase detail --modules core/parser,core/fetcher
    python3 context_loader.py --phase plans
    python3 context_loader.py --phase plan-detail --modules applications/foo/_plan.md

Tool-directory detection (for "Related Tools" in detail output) scans the
directories named in `--tool-dirs` (comma-separated). Defaults to `tools,scripts`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    extract_file_body,
    extract_yaml_frontmatter,
    find_all_plans,
    find_all_readmes,
    find_project_root,
    truncate,
)


def _normalize_dep(dep: Any) -> Optional[str]:
    """Pull a dependency name out of the several shapes we accept."""
    if isinstance(dep, str):
        return dep
    if isinstance(dep, dict):
        if "component" in dep:
            return dep["component"]
        if len(dep) == 1:
            return next(iter(dep.keys()))
    return None


def _collect_dependencies(metadata: Dict[str, Any]) -> List[str]:
    deps: List[str] = []
    component = metadata.get("component") or {}
    for dep in component.get("depends_on") or []:
        if name := _normalize_dep(dep):
            deps.append(name)
    for dep in (metadata.get("interfaces") or {}).get("dependencies") or []:
        if name := _normalize_dep(dep):
            deps.append(name)
    return deps


def discover(
    root_dir: Path,
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Return (components, containers) keyed by module path relative to root."""
    components: Dict[str, Dict[str, Any]] = {}
    containers: Dict[str, Dict[str, Any]] = {}

    for readme_path in find_all_readmes(root_dir):
        if readme_path.parent == root_dir:
            continue  # root README is handled as CLAUDE.md territory

        metadata, _err = extract_yaml_frontmatter(readme_path)
        if not metadata:
            continue

        relative = readme_path.relative_to(root_dir)
        module_path = str(relative.parent)

        if component := metadata.get("component"):
            components[module_path] = {
                "path": module_path,
                "readme": str(relative),
                "name": component.get("name", relative.parent.name),
                "purpose": component.get("does", component.get("purpose", "")),
                "import": component.get("import", ""),
                "key_methods": component.get("key_methods", []),
                "dependencies": _collect_dependencies(metadata),
            }
        elif container := metadata.get("container"):
            containers[module_path] = {
                "path": module_path,
                "readme": str(relative),
                "name": container.get("name", relative.parent.name),
                "purpose": container.get("does", ""),
                "type": container.get("type", ""),
                "contains": container.get("contains", []),
            }

    return components, containers


def discover_plans(root_dir: Path) -> Dict[str, Dict[str, Any]]:
    plans: Dict[str, Dict[str, Any]] = {}
    for plan_path in find_all_plans(root_dir):
        metadata, _err = extract_yaml_frontmatter(plan_path)
        if not metadata or "plan" not in metadata:
            continue
        relative = str(plan_path.relative_to(root_dir))
        plan = metadata["plan"]
        plans[relative] = {
            "path": relative,
            "name": plan.get("name", plan_path.stem),
            "for": plan.get("for", ""),
            "type": plan.get("type", ""),
            "status": plan.get("status", ""),
            "last_updated": str(plan.get("last_updated", "")),
            "focus": plan.get("focus", ""),
            "streams": plan.get("streams", []),
            "questions": plan.get("questions", []),
            "decisions": plan.get("decisions", []),
        }
    return plans


def _dep_to_module_path(dep: str, components: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Resolve a dep like `core.fetcher` to a module path key in `components`.

    Exact-match only (on the tail): the dep must equal the module's path
    after substituting `/` for `.`. This avoids false matches between
    components that share substrings (e.g. `core.parser` vs `core.preparser`).
    """
    target = dep.replace(".", "/").strip("/")
    if target in components:
        return target
    # Fall back to exact-tail match when caller used a short name
    for path in components:
        if path == target or path.endswith("/" + target):
            return path
    return None


def resolve_dependencies(
    selected: Sequence[str],
    components: Dict[str, Dict[str, Any]],
    depth: int = 2,
) -> Set[str]:
    resolved = set(selected)
    frontier = set(selected)
    for _ in range(depth):
        next_frontier: Set[str] = set()
        for module in frontier:
            if module not in components:
                continue
            for dep in components[module]["dependencies"]:
                if resolved_path := _dep_to_module_path(dep, components):
                    if resolved_path not in resolved:
                        resolved.add(resolved_path)
                        next_frontier.add(resolved_path)
        frontier = next_frontier
        if not frontier:
            break
    return resolved


def find_related_tools(
    root_dir: Path,
    components: Dict[str, Dict[str, Any]],
    tool_dirs: Iterable[str],
) -> Dict[str, List[str]]:
    """Find tool scripts that import or reference each component.

    Match rules:
    1. If the component declares `import: "from pkg.mod import ..."`, match on
       the exact `pkg.mod` dotted path (anchored to word boundaries).
    2. Fall back to matching the component's module dotted path
       (e.g. `core.parser`) as a dotted token.
    """
    import re

    result: Dict[str, List[str]] = {path: [] for path in components}
    search_dirs = [root_dir / d for d in tool_dirs if (root_dir / d).exists()]
    if not search_dirs:
        return result

    # Pre-compute a regex per component
    patterns: Dict[str, re.Pattern[str]] = {}
    for path, info in components.items():
        import_stmt = info.get("import", "") or ""
        dotted = path.replace("/", ".")
        # Extract the `pkg.mod` from `from pkg.mod import ...`
        m = re.match(r"\s*from\s+([\w\.]+)\s+import", import_stmt)
        dotted_from_import = m.group(1) if m else ""
        candidates = [p for p in (dotted_from_import, dotted) if p]
        if not candidates:
            continue
        # Word boundary: avoid matching `core.parser` inside `core.preparser`
        alternatives = "|".join(re.escape(c) for c in set(candidates))
        patterns[path] = re.compile(rf"(?<![\w.]){alternatives}(?![\w.])")

    for search_dir in search_dirs:
        for tool_file in search_dir.rglob("*.py"):
            try:
                content = tool_file.read_text(encoding="utf-8")
            except OSError:
                continue
            relative = str(tool_file.relative_to(root_dir))
            for path, pattern in patterns.items():
                if pattern.search(content):
                    result[path].append(relative)

    return result


def format_overview(
    components: Dict[str, Dict[str, Any]],
    containers: Dict[str, Dict[str, Any]],
) -> str:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for path, info in components.items():
        top = path.split("/", 1)[0]
        groups.setdefault(top, []).append(info)

    total = len(components)
    lines = [
        "# Repository Components",
        "",
        f"**{total} components** with YAML frontmatter discovered.",
        "",
    ]

    for group_name in sorted(groups):
        lines.append(f"## {group_name}/")
        lines.append("")
        # Container for this top-level group, if any
        for cpath, cinfo in containers.items():
            if cpath == group_name:
                lines.append(
                    f"- _{cinfo['name']}_ ({cinfo.get('type', 'container')})"
                    f" — {truncate(cinfo['purpose'])}"
                )
        for comp in sorted(groups[group_name], key=lambda x: x["path"]):
            lines.append(f"- **{comp['name']}** (`{comp['path']}`)")
            if comp["purpose"]:
                lines.append(f"  {truncate(comp['purpose'])}")
            if comp["dependencies"]:
                preview = ", ".join(comp["dependencies"][:3])
                if len(comp["dependencies"]) > 3:
                    preview += f" (+{len(comp['dependencies']) - 3} more)"
                lines.append(f"  *Depends on:* {preview}")
        lines.append("")

    lines += ["---", "Select module path(s) to load detailed context."]
    return "\n".join(lines)


def format_detail(
    modules: Sequence[str],
    components: Dict[str, Dict[str, Any]],
    component_tools: Dict[str, List[str]],
    root_dir: Path,
    include_deps: bool,
) -> str:
    all_modules = (
        resolve_dependencies(modules, components)
        if include_deps
        else set(modules)
    )

    lines = [
        "# Detailed Context",
        "",
        f"**Selected:** {', '.join(modules)}",
    ]
    if include_deps and len(all_modules) > len(modules):
        extra = sorted(all_modules - set(modules))
        lines.append(f"**Dependencies included:** {', '.join(extra)}")
    lines.append("")

    missing = [m for m in modules if m not in components]
    for m in missing:
        lines.append(f"> Not found: `{m}`")
    if missing:
        lines.append("")

    for module_path in sorted(all_modules):
        info = components.get(module_path)
        if not info:
            continue
        readme_path = root_dir / info["readme"]

        lines.append(f"## {info['name']}")
        lines.append("")
        lines.append(f"**Location:** `{module_path}`")
        if info["import"]:
            lines.append(f"**Import:** `{info['import']}`")
        if info["key_methods"]:
            methods = ", ".join(
                f"`{m.split('(')[0]}`" for m in info["key_methods"][:5]
            )
            lines.append(f"**Methods:** {methods}")
        lines.append("")

        if body := extract_file_body(readme_path):
            lines.append(body)

        lines += ["", "---", ""]

    related = {t for m in all_modules for t in component_tools.get(m, [])}
    if related:
        lines.append("## Related Tools")
        lines.append("")
        for tool_path in sorted(related):
            lines.append(f"- `{tool_path}`")
        lines.append("")

    return "\n".join(lines)


def format_plans_overview(plans: Dict[str, Dict[str, Any]]) -> str:
    if not plans:
        return "No plans with YAML frontmatter found."

    active = {k: v for k, v in plans.items() if v["status"] == "active"}
    other = {k: v for k, v in plans.items() if v["status"] != "active"}

    lines = [
        "# Plans",
        "",
        f"**{len(plans)} plans** discovered ({len(active)} active).",
        "",
    ]

    if active:
        lines += ["## Active Plans", ""]
        for path, plan in sorted(active.items()):
            lines.append(f"### {plan['name']}")
            lines.append(f"**Type:** {plan['type']} | **For:** `{plan['for']}`")
            if plan["focus"]:
                lines.append(f"**Focus:** {plan['focus']}")

            now = [
                s for s in plan.get("streams") or []
                if isinstance(s, dict) and s.get("priority") == "now"
            ]
            if now:
                lines.append("**NOW:**")
                for s in now:
                    status = s.get("status", "")
                    blocked = (
                        f" (blocked by: {s['blocked_by']})"
                        if s.get("blocked_by") else ""
                    )
                    progress = ""
                    if s.get("tasks"):
                        progress = f" [{s.get('done', 0)}/{s['tasks']}]"
                    lines.append(
                        f"  - {s['name']} ({status}{progress}){blocked}"
                    )

            next_ = [
                s for s in plan.get("streams") or []
                if isinstance(s, dict) and s.get("priority") == "next"
            ]
            if next_:
                lines.append(
                    "**Next:** " + ", ".join(s["name"] for s in next_)
                )

            lines.append(f"**Path:** `{path}`")
            lines.append("")

    if other:
        lines += ["## Other Plans", ""]
        for path, plan in sorted(other.items()):
            lines.append(
                f"- **{plan['name']}** ({plan['status']}) - `{path}`"
            )
        lines.append("")

    questions = [
        (p["name"], q) for p in plans.values() for q in p.get("questions", [])
    ]
    if questions:
        lines += ["## Open Questions", ""]
        for plan_name, q in questions:
            lines.append(f"- [{plan_name}] {q}")
        lines.append("")

    decisions: List[Dict[str, str]] = []
    for plan in plans.values():
        for d in plan.get("decisions", []):
            if isinstance(d, dict):
                decisions.append({
                    "plan": plan["name"],
                    "decision": d.get("decision", ""),
                    "date": str(d.get("date", "")),
                })
    if decisions:
        decisions.sort(key=lambda x: x["date"], reverse=True)
        lines += ["## Recent Decisions", ""]
        for d in decisions[:10]:
            lines.append(f"- [{d['plan']}] {d['decision']} ({d['date']})")
        lines.append("")

    lines += ["---", "Select plan path(s) to load full content."]
    return "\n".join(lines)


def format_plan_detail(
    plan_paths: Sequence[str],
    plans: Dict[str, Dict[str, Any]],
    root_dir: Path,
) -> str:
    lines = [
        "# Plan Detail",
        "",
        f"**Selected:** {', '.join(plan_paths)}",
        "",
    ]
    for plan_path in sorted(plan_paths):
        plan = plans.get(plan_path)
        if not plan:
            lines.append(f"## {plan_path} (not found)")
            lines.append("")
            continue

        full_path = root_dir / plan_path

        lines.append(f"## {plan['name']}")
        lines.append("")
        lines.append(
            f"**Type:** {plan['type']} | **Status:** {plan['status']} "
            f"| **For:** `{plan['for']}`"
        )
        if plan["focus"]:
            lines.append(f"**Focus:** {plan['focus']}")
        lines.append(f"**Updated:** {plan['last_updated']}")
        lines.append("")

        streams = plan.get("streams") or []
        if streams:
            lines += ["### Streams", ""]
            for s in streams:
                if not isinstance(s, dict):
                    continue
                status = s.get("status", "")
                priority = s.get("priority", "")
                progress = (
                    f" [{s.get('done', 0)}/{s['tasks']}]"
                    if s.get("tasks") else ""
                )
                blocked = (
                    f" **blocked by:** {s['blocked_by']}"
                    if s.get("blocked_by") else ""
                )
                lines.append(
                    f"- [{priority}] **{s['name']}** "
                    f"({status}{progress}){blocked}"
                )
            lines.append("")

        if body := extract_file_body(full_path):
            lines += ["### Content", "", body]

        lines += ["", "---", ""]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover and load repository context from READMEs and plan files"
    )
    parser.add_argument(
        "--phase",
        choices=["overview", "detail", "plans", "plan-detail"],
        default="overview",
    )
    parser.add_argument(
        "--modules",
        type=str,
        help="Comma-separated module or plan paths (for detail/plan-detail phases)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
    )
    parser.add_argument("--no-deps", action="store_true")
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument(
        "--tool-dirs",
        type=str,
        default="tools,scripts",
        help="Comma-separated dirs to scan for related tools (default: tools,scripts)",
    )

    args = parser.parse_args()
    root_dir = find_project_root()

    if args.phase in ("plans", "plan-detail"):
        plans = discover_plans(root_dir)
        if args.phase == "plans":
            if args.format == "json":
                print(json.dumps({"plans": list(plans.values())}, indent=2, default=str))
            else:
                print(format_plans_overview(plans))
            return
        if not args.modules:
            print("Error: --modules required for plan-detail phase", file=sys.stderr)
            sys.exit(1)
        paths = [m.strip() for m in args.modules.split(",") if m.strip()]
        print(format_plan_detail(paths, plans, root_dir))
        return

    components, containers = discover(root_dir)
    if not components:
        print("No components with YAML frontmatter found.", file=sys.stderr)
        print(
            "Add frontmatter to README.md files. See SKILL.md for the schema.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.phase == "overview":
        if args.format == "json":
            print(json.dumps({
                "project_root": str(root_dir),
                "components": list(components.values()),
                "containers": list(containers.values()),
            }, indent=2, default=str))
        else:
            print(format_overview(components, containers))
        return

    if not args.modules:
        print("Error: --modules required for detail phase", file=sys.stderr)
        sys.exit(1)

    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    tool_dirs = [d.strip() for d in args.tool_dirs.split(",") if d.strip()]
    component_tools = (
        {} if args.no_tools
        else find_related_tools(root_dir, components, tool_dirs)
    )
    print(format_detail(
        modules=modules,
        components=components,
        component_tools=component_tools,
        root_dir=root_dir,
        include_deps=not args.no_deps,
    ))


if __name__ == "__main__":
    main()
