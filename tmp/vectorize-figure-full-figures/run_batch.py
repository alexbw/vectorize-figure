#!/usr/bin/env python3
import concurrent.futures
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO / "assets" / "full-reference"
OUT_ROOT = REPO / "outputs" / "full-figure-batch"
LOG_DIR = REPO / "tmp" / "vectorize-figure-full-figures" / "logs"
STATUS_PATH = REPO / "tmp" / "vectorize-figure-full-figures" / "status.jsonl"
DEFAULT_TIMEOUT_SECONDS = 30 * 60


def figure_id_for(source: Path) -> str:
    return source.stem


def prompt_for(figure_id: str, source: Path, outdir: Path) -> str:
    rel_source = source.relative_to(REPO)
    rel_json = outdir.relative_to(REPO) / f"{figure_id}.json"
    rel_html = outdir.relative_to(REPO) / f"{figure_id}.html"
    return (
        f"$vectorize-figure {rel_source}. "
        "Generate an independent first-pass reconstruction of this full multi-panel composite "
        "for visual inspection. Do not crop it into separate output files; infer the panel "
        "inventory and reconstruct the full 1536x1024 figure as one editable HTML/JSON pair. "
        f"Write outputs only to {rel_json} and {rel_html}. "
        "Use the vectorize-figure skill contract and the repository command/skill code. Generated "
        "visual layers must not reuse or display the source raster; source imagery is only for "
        "external QA/viewer comparison. Do not use `drawImage(...)` anywhere in reconstruction "
        "HTML, including offscreen/generated canvases. Do not use CSS background images, CSS "
        "`url(...)`, `<img>`, SVG `<image>`, raster `href`/`xlink:href`, `data:image`, or the "
        "source PNG as a generated layer. Use SVG/DOM for editable axes, labels, legends, and "
        "annotations; use canvas only for generated dense fields. Keep the JSON semantic and "
        "editable, with explicit panel boxes, plot boxes, ticks, labels, legends, colorbars, "
        "helper strips, and provenance notes. Verify JSON validity and search the output for "
        "accidental source-raster reuse. If the whole-composite reconstruction cannot pass "
        "syntax, no-raster-reuse, rendered-pixel, or visual-readability checks, report that "
        "the next pass should crop all visible subpanels and run `$vectorize-figure` on each "
        "subpanel before assembling the composite. Do not modify skills, commands, source assets, docs, "
        "or unrelated files."
    )


def validate(figure_id: str, outdir: Path) -> dict:
    html = outdir / f"{figure_id}.html"
    spec = outdir / f"{figure_id}.json"
    result = {
        "html_exists": html.exists(),
        "json_exists": spec.exists(),
        "json_valid": False,
        "source_path_exists": False,
        "raster_reuse_hits": [],
    }
    parsed_spec = None
    if spec.exists():
        try:
            parsed_spec = json.loads(spec.read_text())
            result["json_valid"] = True
        except Exception as exc:
            result["json_error"] = str(exc)
    if parsed_spec:
        source = parsed_spec.get("source")
        source_path_value = source.get("path") if isinstance(source, dict) else None
        result["source_path"] = source_path_value
        result["source_path_exists"] = (
            isinstance(source_path_value, str)
            and not re.match(r"https?://", source_path_value)
            and (spec.parent / source_path_value).resolve().exists()
        )

    html_suspicious = re.compile(
        r"drawImage\s*\(|background-image\s*:|background:\s*url|url\(|data:image/|assets/full-reference|reference-0[1-8].*\.png"
    )
    html_allowed_context = (
        "reference.src",
        "data-reference-src",
        "img id=\"reference\"",
        "reference-image",
        "QA",
        "Reference",
        "reference",
    )
    if html.exists():
        for lineno, line in enumerate(html.read_text(errors="replace").splitlines(), start=1):
            if not html_suspicious.search(line):
                continue
            if "url(#" in line:
                continue
            if any(token in line for token in html_allowed_context):
                continue
            result["raster_reuse_hits"].append(f"{html.relative_to(REPO)}:{lineno}:{line.strip()}")

    if parsed_spec:
        source_path = f"assets/full-reference/{figure_id}.png"

        def looks_like_source_raster(value: str) -> bool:
            lower = value.lower()
            if lower.startswith("data:image/"):
                return True
            if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return False
            return source_path in value or f"{figure_id}.png" in value or "assets/full-reference/" in lower

        def scan_json(value, path: tuple[str, ...] = ()) -> None:
            if isinstance(value, dict):
                mark_type = str(value.get("type") or value.get("kind") or "").lower()
                for key, child in value.items():
                    child_path = path + (str(key),)
                    if isinstance(child, str) and looks_like_source_raster(child):
                        context = ".".join(child_path).lower()
                        source_context = "source" in context or "reference" in context or "provenance" in context
                        generated_image_context = mark_type in {"image", "img", "raster", "bitmap", "photo"}
                        if generated_image_context or not source_context:
                            result["raster_reuse_hits"].append(
                                f"{spec.relative_to(REPO)}:{'.'.join(child_path)}:{child}"
                            )
                    scan_json(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    scan_json(child, path + (str(index),))

        scan_json(parsed_spec)
    return result


def run_one(source: Path, timeout_seconds: int) -> dict:
    started = time.time()
    figure_id = figure_id_for(source)
    outdir = OUT_ROOT / figure_id
    outdir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{figure_id}.stdout.log"
    last_path = LOG_DIR / f"{figure_id}.last.txt"
    prompt = prompt_for(figure_id, source, outdir)
    cmd = [
        "codex",
        "-a",
        "never",
        "-c",
        "model_reasoning_effort=low",
        "exec",
        "-C",
        str(REPO),
        "-s",
        "workspace-write",
        "--image",
        str(source.relative_to(REPO)),
        "-o",
        str(last_path.relative_to(REPO)),
        prompt,
    ]

    status = {
        "figure_id": figure_id,
        "source": str(source.relative_to(REPO)),
        "outdir": str(outdir.relative_to(REPO)),
        "log": str(log_path.relative_to(REPO)),
        "last_message": str(last_path.relative_to(REPO)),
        "started_at": started,
    }

    existing = validate(figure_id, outdir)
    if (
        os.environ.get("SKIP_EXISTING", "1") != "0"
        and existing["html_exists"]
        and existing["json_exists"]
        and existing["json_valid"]
        and existing["source_path_exists"]
        and not existing["raster_reuse_hits"]
    ):
        status.update(
            {
                "returncode": 0,
                "timed_out": False,
                "skipped_existing": True,
                "elapsed_seconds": round(time.time() - started, 1),
                "validation": existing,
                "ok": True,
            }
        )
        return status

    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=REPO,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        first_valid_at = None
        status["timed_out"] = False
        status["terminated_after_valid_outputs"] = False
        while True:
            returncode = proc.poll()
            if returncode is not None:
                status["returncode"] = returncode
                break

            elapsed = time.time() - started
            current_validation = validate(figure_id, outdir)
            current_ok = (
                current_validation["html_exists"]
                and current_validation["json_exists"]
                and current_validation["json_valid"]
                and current_validation["source_path_exists"]
                and not current_validation["raster_reuse_hits"]
            )
            if current_ok:
                if first_valid_at is None:
                    first_valid_at = time.time()
                elif time.time() - first_valid_at >= 10:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=10)
                    status["returncode"] = proc.returncode
                    status["terminated_after_valid_outputs"] = True
                    break

            if elapsed >= timeout_seconds:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
                status["returncode"] = proc.returncode
                status["timed_out"] = True
                break

            time.sleep(5)

    status["elapsed_seconds"] = round(time.time() - started, 1)
    status["validation"] = validate(figure_id, outdir)
    status["ok"] = (
        status["returncode"] == 0
        and status["validation"]["html_exists"]
        and status["validation"]["json_exists"]
        and status["validation"]["json_valid"]
        and status["validation"]["source_path_exists"]
        and not status["validation"]["raster_reuse_hits"]
    )
    return status


def append_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATUS_PATH.open("a") as handle:
        handle.write(json.dumps(status, sort_keys=True) + "\n")


def main() -> int:
    sources = sorted(SOURCE_DIR.glob("reference-*.png"))
    requested = set(sys.argv[1:])
    if requested:
        sources = [source for source in sources if figure_id_for(source) in requested]
    if not sources:
        print("No matching full figures.", file=sys.stderr)
        return 2

    workers = int(os.environ.get("MAX_WORKERS", "2"))
    timeout_seconds = int(os.environ.get("FIGURE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Running {len(sources)} full figures with MAX_WORKERS={workers}, timeout={timeout_seconds}s")

    ok = 0
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_source = {executor.submit(run_one, source, timeout_seconds): source for source in sources}
        for future in concurrent.futures.as_completed(future_to_source):
            status = future.result()
            append_status(status)
            if status["ok"]:
                ok += 1
            else:
                failed += 1
            state = "ok" if status["ok"] else "failed"
            print(f"{state:6} {status['figure_id']} {status['elapsed_seconds']}s")
    print(f"Completed: ok={ok} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
