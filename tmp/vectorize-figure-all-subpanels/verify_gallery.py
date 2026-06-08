#!/usr/bin/env python3
import argparse
import importlib.util
import math
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8766/outputs/vectorize-figure-batch-gallery.html"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_TIMEOUT = 60
GROUPS = [
    ("reference-01-place-code-opto", ["A", "B", "C", "D", "E", "F"]),
    ("reference-02-decision-dynamics", ["A", "B", "C", "D", "E", "F", "G", "H"]),
    ("reference-03-learning-remapping", ["A", "B", "C", "D", "E", "F", "G"]),
    ("reference-04-motor-manifold", ["A", "B", "C", "D", "E", "F", "G", "H", "I"]),
    ("reference-05-grid-remapping", ["A", "B", "C", "D", "E", "F"]),
    ("reference-06-replay-stimulation", ["A", "B", "C", "D", "E", "F", "G", "H"]),
    ("reference-07-cross-region-small-multiples", ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]),
    ("reference-08-neuropixels-central-heatmap", ["A", "B", "C", "D", "E", "F", "G", "H"]),
]
PANELS = [f"{prefix}-{letter}" for prefix, letters in GROUPS for letter in letters]
DEFAULT_PANELS = [
    "reference-01-place-code-opto-A",
    "reference-03-learning-remapping-F",
    "reference-07-cross-region-small-multiples-F",
    "reference-08-neuropixels-central-heatmap-A",
]


def load_viewer_helpers():
    helper_path = REPO / "tmp" / "vectorize-figure-full-figures" / "verify_viewer.py"
    spec = importlib.util.spec_from_file_location("verify_viewer_helpers", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer_helpers()


def check_server(base_url: str) -> None:
    with urllib.request.urlopen(base_url, timeout=3) as response:
        if response.status != 200:
            raise RuntimeError(f"{base_url} returned HTTP {response.status}")


def ensure_server(base_url: str) -> subprocess.Popen | None:
    try:
        check_server(base_url)
        return None
    except Exception:
        if base_url != DEFAULT_BASE_URL:
            raise
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8766", "--bind", "127.0.0.1"],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            check_server(base_url)
            return proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"Could not start HTTP server for {base_url}")


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_chrome(cmd: list[str], timeout: int = DEFAULT_TIMEOUT, attempts: int = 2) -> subprocess.CompletedProcess:
    last_error = None
    for _ in range(attempts):
        try:
            return subprocess.run(cmd, cwd=REPO, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            last_error = exc
    raise RuntimeError(f"Chrome failed after {attempts} attempt(s) of {timeout}s: {' '.join(cmd[-3:])}") from last_error


def capture(chrome: str, url: str, output: Path) -> None:
    run_chrome([
        chrome,
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--hide-scrollbars",
        "--no-first-run",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=3000",
        "--window-size=1400,900",
        f"--screenshot={output}",
        url,
    ])


def dump_dom(chrome: str, url: str) -> str:
    result = run_chrome([
        chrome,
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--no-first-run",
        "--virtual-time-budget=1000",
        "--dump-dom",
        url,
    ])
    return result.stdout


def body_dataset(chrome: str, url: str) -> dict[str, str]:
    dom = dump_dom(chrome, url)
    body_match = re.search(r"<body\b[^>]*>", dom)
    body = body_match.group(0) if body_match else ""
    return dict(re.findall(r'\bdata-([a-z0-9_-]+)="([^"]*)"', body))


def dom_state(chrome: str, url: str) -> tuple[str | None, str | None]:
    data = body_dataset(chrome, url)
    return data.get("panel"), data.get("mode")


def generated_surface_ok(data: dict[str, str]) -> bool:
    surface_display = data.get("generated-surface-display")
    reference_display = data.get("internal-reference-display")
    generated_frame_display = data.get("generated-frame-display")
    outer_reference_display = data.get("outer-reference-display")
    return (
        data.get("gen-ready") == "1"
        and generated_frame_display not in {None, "", "none"}
        and outer_reference_display == "none"
        and surface_display not in {None, "", "none", "missing"}
        and reference_display in {"none", "missing"}
    )


def iter_stage_pixels(image: tuple[int, int, bytes, int]):
    width, height, pixels, channels = image
    left = min(width, 72)
    top = min(height, 56)
    for y in range(top, height):
        for x in range(left, width):
            index = (y * width + x) * channels
            yield pixels[index : index + min(channels, 3)]


def stage_stats(image: tuple[int, int, bytes, int]) -> dict:
    count = 0
    total = 0.0
    total_sq = 0.0
    for pixel in iter_stage_pixels(image):
        value = pixel[0] if len(pixel) == 1 else 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]
        count += 1
        total += value
        total_sq += value * value
    mean = total / max(1, count)
    variance = max(0.0, (total_sq / max(1, count)) - (mean * mean))
    return {"pixels": count, "mean": mean, "stddev": math.sqrt(variance)}


def stage_diff(left_image: tuple[int, int, bytes, int], right_image: tuple[int, int, bytes, int]) -> dict:
    left_pixels = list(iter_stage_pixels(left_image))
    right_pixels = list(iter_stage_pixels(right_image))
    if len(left_pixels) != len(right_pixels):
        raise ValueError("stage crop pixel counts differ")
    different = 0
    total_abs = 0
    for left, right in zip(left_pixels, right_pixels):
        delta = sum(abs(int(l) - int(r)) for l, r in zip(left, right))
        if delta:
            different += 1
            total_abs += delta
    return {"pixels": len(left_pixels), "different": different, "mean_abs_delta": total_abs / max(1, len(left_pixels))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the subpanel batch gallery GEN/REF rendering.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--chrome", default=DEFAULT_CHROME)
    parser.add_argument("--all", action="store_true", help="verify all 62 panels instead of representative panels")
    parser.add_argument("--keep", action="store_true", help="keep screenshots under tmp/vectorize-figure-all-subpanels/gallery-checks")
    parser.add_argument("panels", nargs="*", help="panel ids to verify")
    args = parser.parse_args()

    if not Path(args.chrome).exists():
        print(f"Chrome not found: {args.chrome}", file=sys.stderr)
        return 2

    requested = PANELS if args.all else (args.panels or DEFAULT_PANELS)
    unknown = [panel for panel in requested if panel not in PANELS]
    if unknown:
        print(f"Unknown panel(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    server_proc = ensure_server(args.base_url)
    outdir = REPO / "tmp" / "vectorize-figure-all-subpanels" / "gallery-checks"
    outdir.mkdir(parents=True, exist_ok=True)
    failures = 0
    try:
        for panel_id in requested:
            gen_url = f"{args.base_url}?panel={panel_id}&mode=generated"
            ref_url = f"{args.base_url}?panel={panel_id}&mode=reference"
            gen_path = outdir / f"{panel_id}-gen.png"
            ref_path = outdir / f"{panel_id}-ref.png"
            try:
                gen_data = body_dataset(args.chrome, gen_url)
                ref_data = body_dataset(args.chrome, ref_url)
                gen_state = (gen_data.get("panel"), gen_data.get("mode"))
                ref_state = (ref_data.get("panel"), ref_data.get("mode"))
                capture(args.chrome, gen_url, gen_path)
                capture(args.chrome, ref_url, ref_path)
                gen = VIEWER.read_png(gen_path)
                ref = VIEWER.read_png(ref_path)
                gen_stats = stage_stats(gen)
                ref_stats = stage_stats(ref)
                diff = stage_diff(gen, ref)
                state_ok = gen_state == (panel_id, "generated") and ref_state == (panel_id, "reference")
                surface_ok = generated_surface_ok(gen_data)
                min_diff_pixels = diff["pixels"] * 0.01
                ok = (
                    state_ok
                    and surface_ok
                    and gen_stats["stddev"] > 1
                    and ref_stats["stddev"] > 1
                    and diff["different"] > min_diff_pixels
                    and diff["mean_abs_delta"] > 1
                )
                status = "ok" if ok else "FAIL"
                print(
                    f"{status} {panel_id}: state={gen_state}/{ref_state} "
                    f"outer={gen_data.get('generated-frame-display')}/{gen_data.get('outer-reference-display')} "
                    f"surface={gen_data.get('gen-ready')}/{gen_data.get('generated-surface-display')} "
                    f"internal_ref={gen_data.get('internal-reference-display')} "
                    f"gen_std={gen_stats['stddev']:.2f} ref_std={ref_stats['stddev']:.2f} "
                    f"diff_pixels={diff['different']}/{diff['pixels']} mean_abs_delta={diff['mean_abs_delta']:.3f}",
                    flush=True,
                )
            except Exception as exc:
                ok = False
                print(f"FAIL {panel_id}: {exc}", file=sys.stderr, flush=True)
            if not ok:
                failures += 1
            if not args.keep:
                gen_path.unlink(missing_ok=True)
                ref_path.unlink(missing_ok=True)
    finally:
        stop_server(server_proc)
    if failures:
        print(f"FAIL subpanel gallery: total={len(requested)} failed={failures}", file=sys.stderr)
    else:
        print(f"OK subpanel gallery: total={len(requested)} failed=0")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
