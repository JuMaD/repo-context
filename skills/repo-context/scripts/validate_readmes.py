#!/usr/bin/env python3
"""
Validate README.md and plan files for YAML frontmatter compliance.

Usage:
    python3 validate_readmes.py                 # report
    python3 validate_readmes.py --verbose       # + warnings
    python3 validate_readmes.py --json          # machine-readable
    python3 validate_readmes.py --strict        # exit 1 if any invalid
    python3 validate_readmes.py --fix           # insert stub frontmatter where missing
    python3 validate_readmes.py --fix --dry-run # show what --fix would write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    extract_yaml_frontmatter,
    find_all_plans,
    find_all_readmes,
    find_project_root,
)


COMPONENT_REQUIRED = ["component.name", "component.does"]
COMPONENT_RECOMMENDED = [
    "component.import",
    "component.key_methods",
    "component.depends_on",
]

CONTAINER_REQUIRED = ["container.name", "container.does"]
CONTAINER_RECOMMENDED = ["container.type", "container.contains"]

PLAN_REQUIRED = [
    "plan.name",
    "plan.for",
    "plan.type",
    "plan.status",
    "plan.last_updated",
]
PLAN_RECOMMENDED = ["plan.focus", "plan.streams"]

PLAN_VALID_TYPES = {"roadmap", "architecture", "runbook", "eval", "implementation", "feature"}
PLAN_VALID_STATUSES = {"active", "paused", "completed", "archived", "retired"}
PLAN_STREAM_PRIORITIES = {"now", "next", "later", "done"}
PLAN_STREAM_STATUSES = {"not_started", "in_progress", "blocked", "done", "implemented"}
PLAN_INACTIVE_STATUSES = {"archived", "completed", "retired"}


def _get_nested(data: Dict[str, Any], field_path: str) -> Optional[Any]:
    current: Any = data
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_readme(readme_path: Path, root_dir: Path) -> Dict[str, Any]:
    relative = readme_path.relative_to(root_dir)
    result: Dict[str, Any] = {
        "path": str(relative),
        "valid": False,
        "has_frontmatter": False,
        "schema_type": None,
        "errors": [],
        "warnings": [],
    }

    metadata, err = extract_yaml_frontmatter(readme_path)
    if err:
        result["errors"].append(err)
        return result

    result["has_frontmatter"] = True
    is_component = "component" in (metadata or {})
    is_container = "container" in (metadata or {})

    if is_component:
        result["schema_type"] = "component"
        required, recommended = COMPONENT_REQUIRED, COMPONENT_RECOMMENDED
    elif is_container:
        result["schema_type"] = "container"
        required, recommended = CONTAINER_REQUIRED, CONTAINER_RECOMMENDED
    else:
        result["errors"].append("Missing: component or container root key")
        return result

    for field in required:
        value = _get_nested(metadata, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            result["errors"].append(f"Missing: {field}")

    is_cli_component = (
        is_component
        and (metadata.get("component") or {}).get("type")
        in ("cli", "tool", "script", "eval")
    )
    for field in recommended:
        if is_cli_component and field in ("component.import", "component.key_methods"):
            continue
        if _get_nested(metadata, field) is None:
            result["warnings"].append(f"Missing: {field}")

    if is_component:
        comp = metadata.get("component") or {}
        does = comp.get("does", "")
        if does and not does.strip().endswith((".", "!", "?")):
            result["warnings"].append("component.does should end with punctuation")
        import_stmt = comp.get("import", "")
        if import_stmt and not import_stmt.startswith(("from ", "import ")):
            result["warnings"].append(
                "component.import should start with 'from' or 'import'"
            )

    if is_container:
        cont = metadata.get("container") or {}
        does = cont.get("does", "")
        if does and not does.strip().endswith((".", "!", "?")):
            result["warnings"].append("container.does should end with punctuation")

    result["valid"] = not result["errors"]
    return result


def validate_plan(plan_path: Path, root_dir: Path) -> Dict[str, Any]:
    relative = plan_path.relative_to(root_dir)
    result: Dict[str, Any] = {
        "path": str(relative),
        "valid": False,
        "has_frontmatter": False,
        "schema_type": "plan",
        "errors": [],
        "warnings": [],
    }

    metadata, err = extract_yaml_frontmatter(plan_path)
    if err:
        result["errors"].append(err)
        return result

    result["has_frontmatter"] = True
    if "plan" not in (metadata or {}):
        result["errors"].append("Missing: plan root key")
        return result

    plan = metadata["plan"] or {}

    for field in PLAN_REQUIRED:
        value = _get_nested(metadata, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            result["errors"].append(f"Missing: {field}")

    inactive = str(plan.get("status", "")) in PLAN_INACTIVE_STATUSES
    for field in PLAN_RECOMMENDED:
        if inactive:
            continue
        if _get_nested(metadata, field) is None:
            result["warnings"].append(f"Missing: {field}")

    plan_type = plan.get("type")
    if plan_type and str(plan_type) not in PLAN_VALID_TYPES:
        result["errors"].append(
            f"Invalid plan.type: '{plan_type}' "
            f"(must be one of: {', '.join(sorted(PLAN_VALID_TYPES))})"
        )

    plan_status = plan.get("status")
    if plan_status and str(plan_status) not in PLAN_VALID_STATUSES:
        result["errors"].append(
            f"Invalid plan.status: '{plan_status}' "
            f"(must be one of: {', '.join(sorted(PLAN_VALID_STATUSES))})"
        )

    if str(plan_status) == "active" and not plan.get("focus"):
        result["errors"].append("Active plans require plan.focus")

    for i, stream in enumerate(plan.get("streams") or []):
        if not isinstance(stream, dict):
            result["errors"].append(f"Stream {i}: must be a mapping")
            continue
        if not stream.get("name"):
            result["errors"].append(f"Stream {i}: missing name")
        priority = stream.get("priority")
        if priority and str(priority) not in PLAN_STREAM_PRIORITIES:
            result["warnings"].append(
                f"Stream '{stream.get('name', i)}': invalid priority '{priority}'"
            )
        status = stream.get("status")
        if status and str(status) not in PLAN_STREAM_STATUSES:
            result["warnings"].append(
                f"Stream '{stream.get('name', i)}': invalid status '{status}'"
            )

    for i, dec in enumerate(plan.get("decisions") or []):
        if isinstance(dec, dict):
            if not dec.get("decision"):
                result["warnings"].append(f"Decision {i}: missing decision text")
            if not dec.get("date"):
                result["warnings"].append(f"Decision {i}: missing date")

    result["valid"] = not result["errors"]
    return result


def validate_all(root_dir: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for readme in find_all_readmes(root_dir):
        if readme.parent == root_dir:
            continue
        results.append(validate_readme(readme, root_dir))
    for plan in find_all_plans(root_dir):
        results.append(validate_plan(plan, root_dir))
    return results


# ─── --fix support ────────────────────────────────────────────────────────────

COMPONENT_STUB = '''---
component:
  name: {name}
  does: "TODO: one sentence — what does this component take in and return?"
  # import: "from {dotted_path} import MainClass"
  # key_methods:
  #   - "method(arg: Type) -> ReturnType"
  # depends_on:
  #   - component: other.module
  #     why: "What this dependency provides"
---

'''

PLAN_STUB = '''---
plan:
  name: "TODO: plan name"
  for: "{for_path}"
  type: roadmap            # roadmap | architecture | runbook | eval | implementation | feature
  status: active           # active | paused | completed | archived | retired
  last_updated: {today}
  focus: "TODO: what to prioritize now"
---

'''


def _stub_for_readme(readme_path: Path, root_dir: Path) -> str:
    relative = readme_path.relative_to(root_dir)
    module_dir = relative.parent
    name = module_dir.name.replace("_", " ").replace("-", " ").title()
    dotted = str(module_dir).replace("/", ".")
    return COMPONENT_STUB.format(name=name, dotted_path=dotted)


def _stub_for_plan(plan_path: Path, root_dir: Path) -> str:
    from datetime import date
    relative = plan_path.relative_to(root_dir)
    return PLAN_STUB.format(
        for_path=str(relative.parent),
        today=date.today().isoformat(),
    )


def fix_missing_frontmatter(
    root_dir: Path,
    dry_run: bool,
) -> List[Dict[str, str]]:
    """Insert stub frontmatter at the top of files that don't yet have any.

    Only touches files that have NO frontmatter. Will not overwrite invalid
    or malformed frontmatter — those are reported as errors and left alone
    for the author to fix by hand.
    """
    changes: List[Dict[str, str]] = []

    for readme in find_all_readmes(root_dir):
        if readme.parent == root_dir:
            continue
        metadata, err = extract_yaml_frontmatter(readme)
        if metadata is not None or err != "No YAML frontmatter":
            continue
        stub = _stub_for_readme(readme, root_dir)
        original = readme.read_text(encoding="utf-8")
        new_content = stub + original.lstrip("\n")
        changes.append({"path": str(readme.relative_to(root_dir)), "kind": "readme"})
        if not dry_run:
            readme.write_text(new_content, encoding="utf-8")

    for plan in find_all_plans(root_dir):
        metadata, err = extract_yaml_frontmatter(plan)
        if metadata is not None or err != "No YAML frontmatter":
            continue
        stub = _stub_for_plan(plan, root_dir)
        original = plan.read_text(encoding="utf-8")
        new_content = stub + original.lstrip("\n")
        changes.append({"path": str(plan.relative_to(root_dir)), "kind": "plan"})
        if not dry_run:
            plan.write_text(new_content, encoding="utf-8")

    return changes


# ─── reporting ────────────────────────────────────────────────────────────────


def print_report(results: List[Dict[str, Any]], verbose: bool) -> None:
    readmes = [r for r in results if r["schema_type"] != "plan"]
    plans = [r for r in results if r["schema_type"] == "plan"]
    valid = sum(1 for r in results if r["valid"])
    with_fm = sum(1 for r in results if r["has_frontmatter"])
    total = len(results)

    print("=" * 50)
    print("README & Plan Validation Report")
    print("=" * 50)
    print(f"\nScanned: {total} ({len(readmes)} READMEs, {len(plans)} plans)")
    print(f"With frontmatter: {with_fm} | Valid: {valid}")

    missing = [r for r in results if not r["has_frontmatter"]]
    errors = [r for r in results if r["has_frontmatter"] and r["errors"]]
    warnings = [r for r in results if r["valid"] and r["warnings"]]

    if missing:
        print(f"\n## Missing Frontmatter ({len(missing)})")
        for r in missing:
            print(f"  {r['path']}")
        print("\n  Run with --fix to insert stub frontmatter.")

    if errors:
        print(f"\n## Has Errors ({len(errors)})")
        for r in errors:
            print(f"  {r['path']}")
            for e in r["errors"]:
                print(f"    - {e}")

    if verbose and warnings:
        print(f"\n## Warnings ({len(warnings)})")
        for r in warnings:
            print(f"  {r['path']}")
            for w in r["warnings"]:
                print(f"    - {w}")

    print("\n" + "=" * 50)

    if missing or errors:
        print("\nComponent READMEs require: component.name, component.does")
        print("Container READMEs require: container.name, container.does")
        print(
            "Plan files require: plan.name, plan.for, plan.type, plan.status, "
            "plan.last_updated"
        )
        print("See SKILL.md for the full templates.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate README and plan frontmatter"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Insert stub frontmatter into files that have none.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --fix, report what would change but don't write files.",
    )

    args = parser.parse_args()
    root_dir = find_project_root()

    if args.fix:
        changes = fix_missing_frontmatter(root_dir, dry_run=args.dry_run)
        if not changes:
            print("No files need stub frontmatter — all READMEs and plans have some.")
        else:
            label = "Would insert" if args.dry_run else "Inserted"
            print(f"{label} stub frontmatter in {len(changes)} file(s):")
            for c in changes:
                print(f"  [{c['kind']}] {c['path']}")
            if not args.dry_run:
                print("\nEdit each file to fill in the TODOs, then re-run validation.")
        return

    results = validate_all(root_dir)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, args.verbose)

    if args.strict and any(not r["valid"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
