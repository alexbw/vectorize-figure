#!/usr/bin/env python3
"""Audit denotational relationship metadata in active vectorize-figure specs.

The audit is intentionally warning-only by default. It reports where specs still
rely on source-calibrated pixels or renderer conventions instead of explicit
relationships between data, transforms, layout objects, marks, and annotations.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"

RELATIONSHIP_FIELDS = {
    "anchorTo",
    "children",
    "clipToOwner",
    "derivesFrom",
    "exclusionZone",
    "ownerBox",
    "parent",
    "sourceEvidence",
    "usesTransform",
}
MARK_TYPES = {
    "area",
    "bar",
    "bracket",
    "circle",
    "ellipse",
    "heatmap",
    "imageRecipe",
    "line",
    "lineSeries",
    "path",
    "raster",
    "rect",
    "scatter",
    "violin",
}
ANNOTATION_TYPES = {"annotation", "arrow", "bracket", "callout", "label", "text"}
COLORBAR_KEYS = {"colorbar", "colorBar"}


@dataclass(frozen=True)
class ObjectRecord:
    path: str
    value: dict[str, Any]


def is_current_output(html: Path) -> bool:
    if OUTPUTS / "full-figure-batch" in html.parents:
        return True
    return html.parent.name.endswith("-vectorize-figure-batch")


def discover_specs(active_only: bool = True) -> list[Path]:
    specs: list[Path] = []
    for html in sorted(OUTPUTS.rglob("*.html")):
        if active_only and not is_current_output(html):
            continue
        spec = html.with_suffix(".json")
        if spec.exists():
            specs.append(spec)
    return specs


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def walk_objects(value: Any, path: tuple[str, ...] = ()) -> list[ObjectRecord]:
    records: list[ObjectRecord] = []
    if isinstance(value, dict):
        if "id" in value or "type" in value or "bbox" in value or "text" in value:
            records.append(ObjectRecord(".".join(path) or "$", value))
        for key, child in value.items():
            records.extend(walk_objects(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            records.extend(walk_objects(child, path + (str(index),)))
    return records


def type_name(record: ObjectRecord) -> str:
    value = record.value
    explicit = value.get("type") or value.get("kind") or value.get("markType")
    if explicit:
        return str(explicit)
    leaf = record.path.rsplit(".", 1)[-1]
    if leaf in COLORBAR_KEYS:
        return "colorbar"
    if leaf.lower().endswith("label") or "text" in value:
        return "text"
    if "ticks" in value and "line" in value:
        return "axis"
    return "object"


def under(path: str, key: str) -> bool:
    return f".{key}." in f".{path}." or path.endswith(f".{key}")


def has_any(value: dict[str, Any], keys: set[str]) -> bool:
    return any(key in value for key in keys)


def has_position_anchor(value: dict[str, Any]) -> bool:
    return (
        "anchorTo" in value
        or "ownerBox" in value
        or "bbox" in value
        or "xValue" in value
        or "yValue" in value
        or value.get("positioning") == "page"
    )


def is_colorbar(record: ObjectRecord) -> bool:
    lower_path = record.path.lower()
    lower_type = type_name(record).lower()
    return "colorbar" in lower_path or "colorbar" in lower_type


def is_mark(record: ObjectRecord) -> bool:
    lower_type = type_name(record).lower()
    return under(record.path, "marks") or lower_type in {item.lower() for item in MARK_TYPES}


def is_annotation(record: ObjectRecord) -> bool:
    lower_type = type_name(record).lower()
    return under(record.path, "annotations") or lower_type in ANNOTATION_TYPES


def warning_key(message: str) -> str:
    return message.split(":", 1)[0]


def audit_spec(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    records = walk_objects(spec)
    relationship_counts = Counter()
    object_type_counts = Counter()
    warnings: list[str] = []

    for record in records:
        value = record.value
        obj_type = type_name(record)
        object_type_counts[obj_type] += 1
        for field in RELATIONSHIP_FIELDS:
            if field in value:
                relationship_counts[field] += 1

        if is_mark(record) and type_name(record).lower() != "text" and not has_any(value, {"usesTransform", "anchorTo", "ownerBox"}):
            warnings.append(f"mark-without-relationship: {record.path}")

        if obj_type.lower() == "text" and "x" in value and "y" in value and not has_position_anchor(value):
            warnings.append(f"text-absolute-unanchored: {record.path}")

        if is_annotation(record) and not has_position_anchor(value):
            warnings.append(f"annotation-without-anchor: {record.path}")

        if is_colorbar(record):
            if "orientation" not in value:
                warnings.append(f"colorbar-missing-orientation: {record.path}")
            if "tickSide" not in value and "ticks" in value:
                warnings.append(f"colorbar-missing-tickSide: {record.path}")
            if "tickDirection" not in value and "ticks" in value:
                warnings.append(f"colorbar-missing-tickDirection: {record.path}")
            scale_keys = {"colorScale", "colorScaleId", "scaleId", "usesScale", "usesColorScale"}
            if not has_any(value, scale_keys):
                warnings.append(f"colorbar-missing-color-scale-reference: {record.path}")

        if "ticks" in value and isinstance(value["ticks"], list):
            for index, tick in enumerate(value["ticks"]):
                if isinstance(tick, dict) and "label" in tick and "value" not in tick:
                    warnings.append(f"tick-label-missing-value: {record.path}.ticks.{index}")

        if value.get("sourceCalibrated") is True and not has_any(value, {"provenance", "sourceEvidence"}):
            warnings.append(f"source-calibrated-without-evidence: {record.path}")

    top_level_counts = {key: int(key in spec) for key in ("coordinateSystems", "layoutObjects", "sourceEvidence", "validation", "provenance")}
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "id": spec.get("id") or path.stem,
        "objects": len(records),
        "topLevel": top_level_counts,
        "objectTypes": dict(sorted(object_type_counts.items())),
        "relationships": dict(sorted(relationship_counts.items())),
        "warnings": warnings,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    top_level = Counter()
    relationships = Counter()
    object_types = Counter()
    warning_counts = Counter()
    warning_examples: dict[str, list[str]] = defaultdict(list)

    for result in results:
        top_level.update({key: count for key, count in result["topLevel"].items() if count})
        relationships.update(result["relationships"])
        object_types.update(result["objectTypes"])
        for warning in result["warnings"]:
            key = warning_key(warning)
            warning_counts[key] += 1
            if len(warning_examples[key]) < 8:
                warning_examples[key].append(f"{result['path']}: {warning}")

    return {
        "specs": len(results),
        "objects": sum(result["objects"] for result in results),
        "topLevelSpecs": dict(sorted(top_level.items())),
        "relationships": dict(sorted(relationships.items())),
        "objectTypes": dict(sorted(object_types.items())),
        "warnings": dict(sorted(warning_counts.items())),
        "warningExamples": dict(sorted(warning_examples.items())),
    }


def render_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"IR relationship audit: specs={summary['specs']} objects={summary['objects']} warnings={sum(summary['warnings'].values())}",
        "",
        "Top-level fields:",
    ]
    for key, count in summary["topLevelSpecs"].items():
        lines.append(f"  {key}: {count}")
    lines.append("")
    lines.append("Relationship fields:")
    for key, count in summary["relationships"].items():
        lines.append(f"  {key}: {count}")
    lines.append("")
    lines.append("Warnings:")
    if not summary["warnings"]:
        lines.append("  none")
    for key, count in summary["warnings"].items():
        lines.append(f"  {key}: {count}")
        for example in summary["warningExamples"].get(key, [])[:4]:
            lines.append(f"    - {example}")
    return "\n".join(lines)


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# IR Relationship Audit",
        "",
        f"- Specs: {summary['specs']}",
        f"- Objects: {summary['objects']}",
        f"- Warnings: {sum(summary['warnings'].values())}",
        "",
        "## Warning Counts",
        "",
    ]
    if not summary["warnings"]:
        lines.append("No warnings.")
    else:
        for key, count in summary["warnings"].items():
            lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Warning Examples", ""])
    for key, examples in summary["warningExamples"].items():
        lines.append(f"### `{key}`")
        for example in examples:
            lines.append(f"- `{example}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-variants", action="store_true", help="include historical/test output variants")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--output", type=Path, help="optional report output path")
    parser.add_argument("--fail-on-warnings", action="store_true", help="return nonzero if warnings are present")
    args = parser.parse_args()

    specs = discover_specs(active_only=not args.all_variants)
    if not specs:
        print("No generated specs found", file=sys.stderr)
        return 2

    results = [audit_spec(path, load_json(path)) for path in specs]
    report = {"summary": aggregate(results), "files": results}
    if args.format == "json":
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    elif args.format == "markdown":
        output = render_markdown(report)
    else:
        output = render_text(report) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output, end="")

    warning_total = sum(report["summary"]["warnings"].values())
    return 1 if args.fail_on_warnings and warning_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
