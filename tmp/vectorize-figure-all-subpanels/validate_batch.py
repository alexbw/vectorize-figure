#!/usr/bin/env python3
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SOURCES = sorted((REPO / "assets" / "reference").glob("*-reference.png"))
OUT_ROOT = REPO / "outputs"
REPORT = REPO / "tmp" / "vectorize-figure-all-subpanels" / "validation-summary.json"


EXECUTABLE_FORBIDDEN = re.compile(
    r"\bdrawImage\s*\(|background-image\s*:|background\s*:\s*url|url\((?!#)|data:image/"
)
SOURCE_RASTER_RE = re.compile(r"reference-0[1-8].*\.(?:png|jpg|jpeg|webp)", re.IGNORECASE)


def panel_id_for(source: Path) -> str:
    return source.name.removesuffix("-reference.png")


def output_dir_for(panel_id: str) -> Path:
    return OUT_ROOT / f"{panel_id}-vectorize-figure-batch"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def scan_json_for_source_images(json_path: Path, spec: dict, panel_id: str) -> list[str]:
    hits = []

    def looks_like_source_raster(value: str) -> bool:
        lower = value.lower()
        if lower.startswith("data:image/"):
            return True
        if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return False
        return panel_id in value or "assets/reference/" in lower or SOURCE_RASTER_RE.search(value) is not None

    def visit(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            kind = str(value.get("type") or value.get("kind") or value.get("markType") or "").lower()
            for key, child in value.items():
                child_path = path + (str(key),)
                if isinstance(child, str) and looks_like_source_raster(child):
                    context = ".".join(child_path).lower()
                    source_context = "source" in context or "reference" in context or "provenance" in context
                    generated_image_context = kind in {"image", "img", "raster", "bitmap", "photo"}
                    if generated_image_context or not source_context:
                        hits.append(f"{display_path(json_path)}:{'.'.join(child_path)}:{child}")
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + (str(index),))

    visit(spec)
    return hits


def validate_one(panel_id: str) -> dict:
    outdir = output_dir_for(panel_id)
    html = outdir / f"{panel_id}.html"
    spec = outdir / f"{panel_id}.json"
    item = {
        "panel_id": panel_id,
        "outdir": str(outdir.relative_to(REPO)),
        "html_exists": html.exists(),
        "json_exists": spec.exists(),
        "json_valid": False,
        "source_path_exists": False,
        "html_forbidden_hits": [],
        "json_source_hits": [],
        "source_candidate_hits": [],
    }

    parsed_spec = None
    if spec.exists():
        try:
            parsed_spec = json.loads(spec.read_text())
            item["json_valid"] = True
        except Exception as exc:
            item["json_error"] = str(exc)
    if parsed_spec:
        source = parsed_spec.get("source")
        source_path = source.get("path") if isinstance(source, dict) else None
        item["source_path"] = source_path
        item["source_path_exists"] = (
            isinstance(source_path, str)
            and not re.match(r"https?://", source_path)
            and (spec.parent / source_path).resolve().exists()
        )
        item["json_source_hits"] = scan_json_for_source_images(spec, parsed_spec, panel_id)

    if html.exists():
        for lineno, line in enumerate(html.read_text(errors="replace").splitlines(), start=1):
            if EXECUTABLE_FORBIDDEN.search(line):
                item["html_forbidden_hits"].append(f"{html.relative_to(REPO)}:{lineno}:{line.strip()}")
            if "-reference.png" in line:
                lower = line.lower()
                qaish = (
                    "reference" in lower
                    or "qa" in lower
                    or "spec.source.path" in line
                    or "source.path" in line
                )
                if not qaish:
                    item["source_candidate_hits"].append(f"{html.relative_to(REPO)}:{lineno}:{line.strip()}")

    item["ok"] = (
        item["html_exists"]
        and item["json_exists"]
        and item["json_valid"]
        and item["source_path_exists"]
        and not item["html_forbidden_hits"]
        and not item["json_source_hits"]
        and not item["source_candidate_hits"]
    )
    return item


def main() -> int:
    results = [validate_one(panel_id_for(source)) for source in SOURCES]
    summary = {
        "total": len(results),
        "ok": sum(1 for item in results if item["ok"]),
        "failed": [item for item in results if not item["ok"]],
        "results": results,
    }
    REPORT.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"total={summary['total']} ok={summary['ok']} failed={len(summary['failed'])}")
    for item in summary["failed"]:
        print(
            f"failed {item['panel_id']} "
            f"html={item['html_exists']} json={item['json_exists']} "
            f"json_valid={item['json_valid']} "
            f"source_path={item['source_path_exists']} "
            f"forbidden={len(item['html_forbidden_hits'])} "
            f"json_source={len(item['json_source_hits'])} "
            f"source_hits={len(item['source_candidate_hits'])}"
        )
        for hit in item["html_forbidden_hits"][:3]:
            print(f"  forbidden: {hit}")
        for hit in item["json_source_hits"][:3]:
            print(f"  json source: {hit}")
        for hit in item["source_candidate_hits"][:3]:
            print(f"  source: {hit}")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
