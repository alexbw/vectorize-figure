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


REPO = Path("/Users/alex/Code/scientific-figure-reconstruction")
SOURCE_DIR = REPO / "assets" / "reference"
LOG_DIR = REPO / "tmp" / "make-figure-all-subpanels" / "logs"
STATUS_PATH = REPO / "tmp" / "make-figure-all-subpanels" / "status.jsonl"
DEFAULT_TIMEOUT_SECONDS = 20 * 60


def panel_id_for(source: Path) -> str:
    return source.name.removesuffix("-reference.png")


def prompt_for(panel_id: str, source: Path, outdir: Path) -> str:
    rel_source = source.relative_to(REPO)
    rel_json = outdir.relative_to(REPO) / f"{panel_id}.json"
    rel_html = outdir.relative_to(REPO) / f"{panel_id}.html"
    return (
        f"$make-figure {rel_source}. "
        "Generate an independent first-pass reconstruction for visual inspection. "
        f"Write outputs only to {rel_json} and {rel_html}. "
        "Use the make-figure skill contract and the repository command/skill code: "
        "generated visual layers must not reuse the source raster; the source may appear only "
        "as a clearly labeled QA/reference view. For this batch harness, do not include any "
        "`drawImage(...)` call in the generated HTML at all, even for offscreen or generated canvases; "
        "draw dense fields directly with canvas primitives, ImageData writes, SVG, or DOM. "
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
        "raster_reuse_hits": [],
    }
    if spec.exists():
        try:
            json.loads(spec.read_text())
            result["json_valid"] = True
        except Exception as exc:
            result["json_error"] = str(exc)

    suspicious = re.compile(r"drawImage|background-image|background:\s*url|url\((?!#)|-reference\.png")
    allowed = (
        "source.path",
        "spec.source.path",
        "reference.src",
        '"path":',
        "'path':",
    )
    for path in (html, spec):
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
            if not suspicious.search(line):
                continue
            if "sourceReuseForbiddenPatterns" in line:
                continue
            if "-reference.png" in line and any(token in line for token in allowed):
                continue
            result["raster_reuse_hits"].append(f"{path.relative_to(REPO)}:{lineno}:{line.strip()}")
    return result


def run_one(source: Path, timeout_seconds: int) -> dict:
    started = time.time()
    panel_id = panel_id_for(source)
    outdir = REPO / "outputs" / f"{panel_id}-make-figure-batch"
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
