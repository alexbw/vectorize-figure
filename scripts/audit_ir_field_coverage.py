#!/usr/bin/env python3
"""Audit semantic IR field coverage for vectorize-figure outputs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Iterable, NamedTuple


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DEFAULT_MANIFEST = ROOT / "schemas" / "ir-field-coverage.json"

VALID_STATUSES = {"rendered", "preserved", "validated", "provenance-only", "deprecated", "ignored"}
KNOWN_VALIDATORS = {
    "audit_semantic_layout_contract",
    "audit_explicit_axis_rendering",
    "audit_side_strip_rendering",
    "audit_layout_qa_report",
    "audit_figure_ir_relationships",
    "structural_checks",
    "scan_json_for_source_images",
}
STRICT_SEMANTIC_SEGMENTS = {
    "alignment",
    "alignments[]",
    "originAlignment",
    "origin_alignment",
    "offsetFromDataBbox",
    "offset_from_data_bbox",
    "components[]",
    "exclusionZone",
    "exclusion_zone",
}


class FieldOccurrence(NamedTuple):
    spec: Path
    path: str


class CoverageMatch(NamedTuple):
    status: tuple[str, ...]
    source: str
    manifest_entry: dict[str, Any] | None = None


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


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return load_json(path)


def array_item_path(path: tuple[str, ...], value: Any) -> tuple[str, ...]:
    if not path:
        return ("[]",)
    current = list(path)
    key = current[-1]
    if key == "layoutObjects" and isinstance(value, dict) and value.get("type"):
        current[-1] = f"layoutObjects[type={value['type']}]"
    else:
        current[-1] = f"{key}[]"
    return tuple(current)


def walk_field_paths(value: Any, path: tuple[str, ...] = ()) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (str(key),)
            yield ".".join(child_path)
            yield from walk_field_paths(child, child_path)
    elif isinstance(value, list):
        for child in value:
            yield from walk_field_paths(child, array_item_path(path, child))


def strip_type_predicate(segment: str) -> str:
    if "[type=" in segment:
        return segment.split("[type=", 1)[0] + "[]"
    return segment


def token_matches(pattern: str, actual: str) -> bool:
    if pattern == actual or pattern == "*":
        return True
    if pattern.endswith("[]") and strip_type_predicate(actual) == pattern:
        return True
    if "[type=*]" in pattern and actual.startswith(pattern.split("[type=*]", 1)[0] + "[type="):
        return True
    return False


def path_matches(pattern: str, path: str) -> bool:
    pattern_tokens = pattern.split(".")
    path_tokens = path.split(".")
    if len(pattern_tokens) != len(path_tokens):
        return False
    return all(token_matches(pattern_token, path_token) for pattern_token, path_token in zip(pattern_tokens, path_tokens))


def manifest_entry_for(path: str, fields: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    if path in fields:
        entry = fields[path]
        if isinstance(entry, dict):
            return path, entry
    for pattern, entry in fields.items():
        if pattern == path:
            continue
        if isinstance(entry, dict) and path_matches(pattern, path):
            return pattern, entry
    return None


def normalized_segments(path: str) -> list[str]:
    return [strip_type_predicate(segment) for segment in path.split(".")]


def is_under_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}.") for prefix in prefixes)


def has_provenance_segment(path: str, allowed: Iterable[str]) -> bool:
    segments = normalized_segments(path)
    allowed_roots = {item.split(".", 1)[0] for item in allowed}
    return any(segment in allowed_roots for segment in segments)


def has_rendered_subtree(path: str, rendered_subtrees: Iterable[str]) -> bool:
    segments = normalized_segments(path)
    return any(segment in rendered_subtrees for segment in segments)


def is_strict_semantic_child(path: str) -> bool:
    segments = normalized_segments(path)
    return any(segment in STRICT_SEMANTIC_SEGMENTS for segment in segments[:-1])


def leaf_name(path: str) -> str:
    return strip_type_predicate(path.rsplit(".", 1)[-1])


def classify_path(path: str, manifest: dict[str, Any]) -> CoverageMatch | None:
    fields = manifest.get("fields") or {}
    if not isinstance(fields, dict):
        return None
    matched = manifest_entry_for(path, fields)
    if matched is not None:
        pattern, entry = matched
        statuses = entry.get("status") or []
        if isinstance(statuses, str):
            statuses = [statuses]
        return CoverageMatch(tuple(str(status) for status in statuses), pattern, entry)

    defaults = manifest.get("defaults") or {}
    allowed_provenance = defaults.get("allowedProvenancePaths") or []
    if has_provenance_segment(path, allowed_provenance):
        return CoverageMatch(("provenance-only",), "defaults.allowedProvenancePaths")

    rendered_subtrees = set(defaults.get("renderedSubtrees") or [])
    if has_rendered_subtree(path, rendered_subtrees):
        return CoverageMatch(("rendered",), "defaults.renderedSubtrees")

    validated_prefixes = defaults.get("validatedPrefixes") or []
    if is_under_any(path, validated_prefixes):
        return CoverageMatch(("validated",), "defaults.validatedPrefixes")

    rendered_prefixes = defaults.get("renderedPrefixes") or []
    if is_under_any(path, rendered_prefixes):
        return CoverageMatch(("rendered",), "defaults.renderedPrefixes")

    rendered_leaf_fields = set(defaults.get("renderedLeafFields") or [])
    if leaf_name(path) in rendered_leaf_fields and not is_strict_semantic_child(path):
        return CoverageMatch(("rendered",), "defaults.renderedLeafFields")

    return None


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    fields = manifest.get("fields")
    if not isinstance(fields, dict):
        return ["manifest `fields` must be an object"]
    for pattern, entry in fields.items():
        if not isinstance(entry, dict):
            errors.append(f"{pattern}: manifest entry must be an object")
            continue
        statuses = entry.get("status")
        if isinstance(statuses, str):
            statuses = [statuses]
        if not isinstance(statuses, list) or not statuses:
            errors.append(f"{pattern}: manifest entry must include nonempty status")
            continue
        invalid = [str(status) for status in statuses if str(status) not in VALID_STATUSES]
        if invalid:
            errors.append(f"{pattern}: invalid status: {', '.join(invalid)}")
        if "validated" in statuses:
            validators = entry.get("validators") or []
            if not validators:
                errors.append(f"{pattern}: validated field must name at least one validator")
            unknown = [str(name) for name in validators if str(name) not in KNOWN_VALIDATORS]
            if unknown:
                errors.append(f"{pattern}: unknown validator: {', '.join(unknown)}")
        if "preserved" in statuses and not entry.get("rendererEvidence"):
            errors.append(f"{pattern}: preserved field must declare rendererEvidence")
        if "ignored" in statuses and not entry.get("reason"):
            errors.append(f"{pattern}: ignored field must include reason")
        if "deprecated" in statuses and not (entry.get("reason") or entry.get("migration")):
            errors.append(f"{pattern}: deprecated field must include reason or migration")
    return errors


def output_specs_from_arg(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        raise FileNotFoundError(path)
    return sorted(candidate for candidate in path.rglob("*.json") if candidate.is_file())


def collect_occurrences(specs: Iterable[Path]) -> list[FieldOccurrence]:
    occurrences: list[FieldOccurrence] = []
    for spec_path in specs:
        spec = load_json(spec_path)
        for field_path in walk_field_paths(spec):
            occurrences.append(FieldOccurrence(spec_path, field_path))
    return occurrences


def audit_specs(specs: list[Path], manifest: dict[str, Any], strict_high_risk: bool = False) -> dict[str, Any]:
    manifest_errors = validate_manifest(manifest)
    defaults = manifest.get("defaults") or {}
    high_risk_prefixes = defaults.get("highRiskPrefixes") or []
    occurrences = collect_occurrences(specs)
    unique_paths = sorted({occurrence.path for occurrence in occurrences})
    coverage_by_path = {path: classify_path(path, manifest) for path in unique_paths}

    unclassified = [occurrence for occurrence in occurrences if coverage_by_path[occurrence.path] is None]
    unclassified_high_risk = [
        occurrence for occurrence in unclassified
        if is_under_any(occurrence.path, high_risk_prefixes)
    ]
    strict_failures = unclassified_high_risk if strict_high_risk else []

    path_examples: dict[str, list[str]] = defaultdict(list)
    for occurrence in unclassified_high_risk:
        relative = occurrence.spec.relative_to(ROOT).as_posix() if occurrence.spec.is_relative_to(ROOT) else occurrence.spec.as_posix()
        if len(path_examples[occurrence.path]) < 4:
            path_examples[occurrence.path].append(relative)

    status_counts = Counter()
    source_counts = Counter()
    for match in coverage_by_path.values():
        if match is None:
            continue
        source_counts[match.source] += 1
        status_counts.update(match.status)

    return {
        "specs": len(specs),
        "fields": len(occurrences),
        "uniqueFields": len(unique_paths),
        "classified": sum(1 for match in coverage_by_path.values() if match is not None),
        "statusCounts": dict(sorted(status_counts.items())),
        "sourceCounts": dict(sorted(source_counts.items())),
        "manifestErrors": manifest_errors,
        "unclassified": unclassified,
        "unclassifiedHighRisk": unclassified_high_risk,
        "unclassifiedHighRiskExamples": dict(sorted(path_examples.items())),
        "strictFailures": strict_failures,
    }


def render_report(report: dict[str, Any]) -> str:
    lines = [
        (
            "IR field coverage audit: "
            f"specs={report['specs']} fields={report['fields']} "
            f"unique={report['uniqueFields']} classified={report['classified']} "
            f"unclassified={len(report['unclassified'])} "
            f"strict_failures={len(report['strictFailures']) + len(report['manifestErrors'])}"
        )
    ]
    if report["manifestErrors"]:
        lines.append("")
        lines.append("Manifest errors:")
        for error in report["manifestErrors"][:20]:
            lines.append(f"- {error}")
        if len(report["manifestErrors"]) > 20:
            lines.append(f"- ... {len(report['manifestErrors']) - 20} more")
    if report["unclassifiedHighRiskExamples"]:
        lines.append("")
        lines.append("Unclassified high-risk fields:")
        for field_path, examples in list(report["unclassifiedHighRiskExamples"].items())[:30]:
            example = examples[0] if examples else "unknown"
            lines.append(f"- {example}: {field_path}")
        if len(report["unclassifiedHighRiskExamples"]) > 30:
            lines.append(f"- ... {len(report['unclassifiedHighRiskExamples']) - 30} more paths")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="coverage manifest path")
    parser.add_argument("--output", type=Path, action="append", help="JSON file or output directory to audit")
    parser.add_argument("--all-variants", action="store_true", help="include historical/test output variants")
    parser.add_argument("--strict-high-risk", action="store_true", help="fail unknown fields under high-risk semantic paths")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if args.output:
        specs: list[Path] = []
        for output in args.output:
            specs.extend(output_specs_from_arg(output))
    else:
        specs = discover_specs(active_only=not args.all_variants)
    report = audit_specs(specs, manifest, strict_high_risk=args.strict_high_risk)
    print(render_report(report))
    if report["manifestErrors"]:
        return 1
    if args.strict_high_risk and report["strictFailures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
