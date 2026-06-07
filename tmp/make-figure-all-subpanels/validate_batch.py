#!/usr/bin/env python3
import json
import re
from pathlib import Path


REPO = Path("/Users/alex/Code/scientific-figure-reconstruction")
SOURCES = sorted((REPO / "assets" / "reference").glob("*-reference.png"))
OUT_ROOT = REPO / "outputs"
REPORT = REPO / "tmp" / "make-figure-all-subpanels" / "validation-summary.json"


EXECUTABLE_FORBIDDEN = re.compile(
    r"\bdrawImage\s*\(|background-image\s*:|background\s*:\s*url|url\((?!#)"
)


def panel_id_for(source: Path) -> str:
    return source.name.removesuffix("-reference.png")


def validate_one(panel_id: str) -> dict:
    outdir = OUT_ROOT / f"{panel_id}-make-figure-batch"
    html = outdir / f"{panel_id}.html"
    spec = outdir / f"{panel_id}.json"
    item = {
        "panel_id": panel_id,
        "outdir": str(outdir.relative_to(REPO)),
        "html_exists": html.exists(),
        "json_exists": spec.exists(),
        "json_valid": False,
        "html_forbidden_hits": [],
        "source_candidate_hits": [],
    }

    if spec.exists():
        try:
            json.loads(spec.read_text())
            item["json_valid"] = True
        except Exception as exc:
            item["json_error"] = str(exc)

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
        and not item["html_forbidden_hits"]
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
            f"forbidden={len(item['html_forbidden_hits'])} "
            f"source_hits={len(item['source_candidate_hits'])}"
        )
        for hit in item["html_forbidden_hits"][:3]:
            print(f"  forbidden: {hit}")
        for hit in item["source_candidate_hits"][:3]:
            print(f"  source: {hit}")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
