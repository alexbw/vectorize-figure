#!/usr/bin/env python3
"""Batch driver that produced the cropped-subpanel reconstructions in outputs/.

Shells out to a coding-agent CLI (Codex here; swap the `cmd` list for your
agent of choice) once per reference panel in assets/reference/. The
`validate()` helpers in this module are exercised by
scripts/test_vectorize_figure_validators.py, so the file stays useful even if
you never rerun the batch.
"""
import concurrent.futures
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO / "assets" / "reference"
LOG_DIR = REPO / "tmp" / "vectorize-figure-all-subpanels" / "logs"
STATUS_PATH = REPO / "tmp" / "vectorize-figure-all-subpanels" / "status.jsonl"
DEFAULT_TIMEOUT_SECONDS = 20 * 60


def panel_id_for(source: Path) -> str:
    return source.name.removesuffix("-reference.png")


def prompt_for(panel_id: str, source: Path, outdir: Path) -> str:
    rel_source = source.relative_to(REPO)
    rel_json = outdir.relative_to(REPO) / f"{panel_id}.json"
    rel_html = outdir.relative_to(REPO) / f"{panel_id}.html"
    return (
        f"$vectorize-figure {rel_source}. "
        "Generate an independent first-pass reconstruction for visual inspection. "
        f"Write outputs only to {rel_json} and {rel_html}. "
        "Use the vectorize-figure skill contract and the repository command/skill code: "
        "generated visual layers must not reuse or display the source raster; source imagery is only "
        "for external QA/viewer comparison. Do not include any `drawImage(...)` call in the generated "
        "HTML at all, even for offscreen or generated canvases. Do not use CSS background images, CSS "
        "`url(...)`, `<img>`, SVG `<image>`, raster `href`/`xlink:href`, `data:image`, or the source "
        "PNG as a generated layer. Draw dense fields directly with canvas primitives, ImageData writes, SVG, or DOM. "
        "Keep the JSON semantic and editable. "
        "Verify JSON validity and search the output for any drawImage call or background source reuse. "
        "Do not modify existing output directories, docs, skills, plugins, source assets, or unrelated files."
    )


def validate(panel_id: str, outdir: Path) -> dict:
    html = outdir / f"{panel_id}.html"
    spec = outdir / f"{panel_id}.json"
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
        source_path = source.get("path") if isinstance(source, dict) else None
        result["source_path"] = source_path
        result["source_path_exists"] = (
            isinstance(source_path, str)
            and not re.match(r"https?://", source_path)
            and (spec.parent / source_path).resolve().exists()
        )

        def looks_like_source_raster(value: str) -> bool:
            lower = urllib.parse.unquote(value).lower()
            if lower.startswith("data:image/"):
                return True
            if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return False
            return panel_id in lower or "assets/reference/" in lower

        def scan_json(value, path: tuple[str, ...] = ()) -> None:
            if isinstance(value, dict):
                mark_type = str(value.get("type") or value.get("kind") or value.get("markType") or "").lower()
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

    suspicious = re.compile(r"\bdrawImage\s*\(|background-image\s*:|background:\s*url|url\((?!#)|data:image/|-reference\.png")
    for path in (html, spec):
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
            decoded_line = urllib.parse.unquote(line)
            if not suspicious.search(decoded_line):
                continue
            if "sourceReuseForbiddenPatterns" in decoded_line:
                continue
            if "-reference.png" in decoded_line:
                lower = decoded_line.lower()
                qaish = (
                    "reference" in lower
                    or "qa" in lower
                    or "spec.source.path" in decoded_line
                    or "source.path" in decoded_line
                    or '"path":' in decoded_line
                    or "'path':" in decoded_line
                )
                if qaish:
                    continue
            result["raster_reuse_hits"].append(f"{path.relative_to(REPO)}:{lineno}:{line.strip()}")
    return result


def run_one(source: Path, timeout_seconds: int) -> dict:
    started = time.time()
    panel_id = panel_id_for(source)
    outdir = REPO / "outputs" / f"{panel_id}-vectorize-figure-batch"
    outdir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{panel_id}.stdout.log"
    last_path = LOG_DIR / f"{panel_id}.last.txt"
    prompt = prompt_for(panel_id, source, outdir)
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
        "panel_id": panel_id,
        "source": str(source.relative_to(REPO)),
        "outdir": str(outdir.relative_to(REPO)),
        "log": str(log_path.relative_to(REPO)),
        "last_message": str(last_path.relative_to(REPO)),
        "started_at": started,
    }

    existing = validate(panel_id, outdir)
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
            current_validation = validate(panel_id, outdir)
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
    status["validation"] = validate(panel_id, outdir)
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
    with STATUS_PATH.open("a") as handle:
        handle.write(json.dumps(status, sort_keys=True) + "\n")


def main() -> int:
    sources = sorted(SOURCE_DIR.glob("*-reference.png"))
    requested = set(sys.argv[1:])
    if requested:
        sources = [source for source in sources if panel_id_for(source) in requested]
    if not sources:
        print("No matching source panels.", file=sys.stderr)
        return 2

    workers = int(os.environ.get("MAX_WORKERS", "3"))
    timeout_seconds = int(os.environ.get("PANEL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Running {len(sources)} panels with MAX_WORKERS={workers}, timeout={timeout_seconds}s")

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
            print(f"{state:6} {status['panel_id']} {status['elapsed_seconds']}s")
    print(f"Completed: ok={ok} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
