#!/usr/bin/env python3
"""Validate make-figure generated outputs.

This script protects the current generated panels while the schema and renderer
contracts evolve. It runs structural checks, renders each HTML file in headless
Chrome, crops the generated panel at native canvas size, and compares it to a
stored baseline screenshot.
"""

from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import os
from pathlib import Path
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
from typing import Iterable

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
BASELINES = OUTPUTS / "_regression-baselines"
DEFAULT_THRESHOLD = 0.005
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@contextlib.contextmanager
def serve_repo() -> Iterable[str]:
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_address[1]}"
        finally:
            server.shutdown()
            thread.join(timeout=2)


def chrome_bin() -> str:
    return os.environ.get("CHROME_BIN") or DEFAULT_CHROME


def run_chrome(args: list[str]) -> subprocess.CompletedProcess[str]:
    command = [chrome_bin(), "--headless", "--disable-gpu", *args]
    return subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def discover_outputs() -> list[tuple[Path, Path]]:
    pairs = []
    for html in sorted(OUTPUTS.glob("*/*.html")):
      json_path = html.with_suffix(".json")
      if json_path.exists():
          pairs.append((html, json_path))
    return pairs


def load_spec(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def near_border(pixel: tuple[int, int, int]) -> bool:
    return all(abs(channel - 208) <= 8 for channel in pixel[:3])


def run_lengths(row: list[bool]) -> Iterable[tuple[int, int]]:
    start = None
    for index, value in enumerate(row + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            yield start, index
            start = None


def vertical_score(image: Image.Image, x: int, y: int, height: int) -> int:
    max_y = min(image.height, y + height)
    return sum(1 for yy in range(y, max_y) if near_border(image.getpixel((x, yy))))


def find_frame_crop(image: Image.Image, width: int, height: int) -> tuple[int, int, int, int]:
    target_run = width + 2
    max_y = image.height - height - 1
    max_x = image.width - width - 1
    for y in range(0, max(0, max_y)):
        row = [near_border(image.getpixel((x, y))) for x in range(image.width)]
        for start, end in run_lengths(row):
            run = end - start
            if abs(run - target_run) > 6 or start > max_x:
                continue
            left_score = vertical_score(image, start, y, height + 2)
            right_score = vertical_score(image, start + width + 1, y, height + 2)
            if left_score >= height * 0.9 and right_score >= height * 0.9:
                return (start + 1, y + 1, start + 1 + width, y + 1 + height)
    raise RuntimeError(f"Could not locate {width}x{height} generated frame in browser screenshot")


def capture_panel(html: Path, spec: dict, base_url: str, output: Path) -> None:
    width = int(spec["canvas"]["width"])
    height = int(spec["canvas"]["height"])
    window_width = max(800, width + 260)
    window_height = max(700, height + 220)
    url = f"{base_url}/{html.relative_to(ROOT).as_posix()}"
    with tempfile.TemporaryDirectory() as tmpdir:
        page_png = Path(tmpdir) / "page.png"
        result = run_chrome([
            "--hide-scrollbars",
            f"--window-size={window_width},{window_height}",
            f"--screenshot={page_png}",
            url,
        ])
        if result.returncode != 0 or not page_png.exists():
            raise RuntimeError(f"Chrome screenshot failed for {html}: {result.stderr.strip()}")
        image = Image.open(page_png).convert("RGB")
        crop_box = find_frame_crop(image, width, height)
        image.crop(crop_box).save(output)


def dump_dom(html: Path, base_url: str) -> str:
    url = f"{base_url}/{html.relative_to(ROOT).as_posix()}"
    result = run_chrome(["--virtual-time-budget=3000", "--dump-dom", url])
    if result.returncode != 0:
        raise RuntimeError(f"Chrome DOM dump failed for {html}: {result.stderr.strip()}")
    return result.stdout


def structural_checks(html: Path, json_path: Path, spec: dict, dom: str) -> list[str]:
    errors = []
    html_text = html.read_text(errors="ignore")
    for key in ("schema", "id", "source", "canvas", "panels"):
        if key not in spec:
            errors.append(f"{json_path}: missing top-level `{key}`")
    canvas = spec.get("canvas", {})
    if not isinstance(canvas.get("width"), int) or not isinstance(canvas.get("height"), int):
        errors.append(f"{json_path}: canvas width/height must be integers")
    if "drawImage" in html_text:
        errors.append(f"{html}: contains drawImage")
    if "background-image" in html_text:
        errors.append(f"{html}: contains background-image")
    for tag in re.findall(r"<img\b[^>]*>", html_text, flags=re.IGNORECASE):
        if 'id="reference"' not in tag and "class=\"reference\"" not in tag:
            errors.append(f"{html}: non-QA img tag `{tag[:120]}`")
    mismatches = sorted(set(re.findall(r'data-[a-zA-Z0-9_-]*validation="mismatch"', dom)))
    if mismatches:
        errors.append(f"{html}: renderer validation mismatch {', '.join(mismatches)}")
    tick_labels = set(re.findall(r'data-role="tick-label"[^>]*data-axis="([^"]+)"[^>]*data-value="([^"]+)"', dom))
    tick_marks = set(re.findall(r'data-role="axis-tick-mark"[^>]*data-axis="([^"]+)"[^>]*data-value="([^"]+)"', dom))
    if tick_labels or tick_marks:
        missing_marks = sorted(tick_labels - tick_marks)
        missing_labels = sorted(tick_marks - tick_labels)
        if missing_marks:
            errors.append(f"{html}: tick labels missing marks {missing_marks}")
        if missing_labels:
            errors.append(f"{html}: tick marks missing labels {missing_labels}")
    return errors


def compare_images(current: Path, baseline: Path, threshold: float) -> tuple[bool, str]:
    if not baseline.exists():
        return False, f"missing baseline {baseline}; run with --update-baselines"
    a = Image.open(current).convert("RGB")
    b = Image.open(baseline).convert("RGB")
    if a.size != b.size:
        return False, f"dimension mismatch current={a.size} baseline={b.size}"
    changed = 0
    total_abs = 0
    total = a.size[0] * a.size[1]
    current_bytes = a.tobytes()
    baseline_bytes = b.tobytes()
    for index in range(0, len(current_bytes), 3):
        delta = sum(abs(current_bytes[index + channel] - baseline_bytes[index + channel]) for channel in range(3))
        total_abs += delta
        if delta > 6:
            changed += 1
    ratio = changed / max(1, total)
    mean_abs = total_abs / max(1, total * 3)
    ok = ratio <= threshold
    return ok, f"changed={ratio:.4%} mean_abs={mean_abs:.3f} threshold={threshold:.4%}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-baselines", action="store_true", help="write baseline screenshots")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="changed-pixel threshold")
    parser.add_argument("--outputs", nargs="*", help="optional HTML or output directories to validate")
    args = parser.parse_args()

    pairs = discover_outputs()
    if args.outputs:
        wanted = {Path(item).resolve() for item in args.outputs}
        expanded = set()
        for item in wanted:
            if item.is_dir():
                expanded.update(path.resolve() for path in item.glob("*.html"))
            else:
                expanded.add(item)
        pairs = [(html, json_path) for html, json_path in pairs if html.resolve() in expanded or html.parent.resolve() in expanded]
    if not pairs:
        print("No generated outputs found", file=sys.stderr)
        return 2

    BASELINES.mkdir(parents=True, exist_ok=True)
    errors = []
    with serve_repo() as base_url, tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for html, json_path in pairs:
            spec = load_spec(json_path)
            panel_id = spec.get("id") or html.stem
            baseline = BASELINES / f"{panel_id}.png"
            current = tmp / f"{panel_id}.png"
            print(f"== {panel_id}")
            try:
                dom = dump_dom(html, base_url)
                errors.extend(structural_checks(html, json_path, spec, dom))
                capture_panel(html, spec, base_url, current)
                if args.update_baselines:
                    current.replace(baseline)
                    print(f"baseline updated: {baseline.relative_to(ROOT)}")
                else:
                    ok, message = compare_images(current, baseline, args.threshold)
                    print(message)
                    if not ok:
                        errors.append(f"{html}: visual regression {message}")
            except Exception as exc:
                errors.append(f"{html}: {exc}")

    if errors:
        print("\nValidation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("\nValidation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
