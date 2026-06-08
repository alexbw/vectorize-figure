#!/usr/bin/env python3
"""Validate vectorize-figure generated outputs.

This script protects the current generated panels while the schema and renderer
contracts evolve. It runs structural checks, renders each HTML file in headless
Chrome, crops the generated panel at native canvas size, and compares it to a
stored baseline screenshot.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
from html.parser import HTMLParser
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
import urllib.parse

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
BASELINES = OUTPUTS / "_regression-baselines"
DEFAULT_THRESHOLD = 0.005
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_DOM_TIMEOUT = 8
DEFAULT_SCREENSHOT_TIMEOUT = 60
SOURCE_RASTER_RE = re.compile(r"reference-0[1-8].*\.(?:png|jpg|jpeg|webp)", re.IGNORECASE)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


@contextlib.contextmanager
def serve_repo() -> Iterable[str]:
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with ThreadingTCPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_address[1]}"
        finally:
            server.shutdown()
            thread.join(timeout=2)


def chrome_bin() -> str:
    return os.environ.get("CHROME_BIN") or DEFAULT_CHROME


def run_chrome(args: list[str], timeout: int = 30, attempts: int = 2) -> subprocess.CompletedProcess[str]:
    command = [
        chrome_bin(),
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--no-first-run",
        *args,
    ]
    last_timeout = None
    for _ in range(attempts):
        try:
            return subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            if "--dump-dom" in args and "</html>" in stdout.lower():
                return subprocess.CompletedProcess(command, 0, stdout, stderr)
            last_timeout = exc
    snippet = " ".join(str(part) for part in args[-3:])
    raise RuntimeError(f"Chrome timed out after {attempts} attempt(s) of {timeout}s: {snippet}") from last_timeout


def is_current_output(html: Path) -> bool:
    if OUTPUTS / "full-figure-batch" in html.parents:
        return True
    return html.parent.name.endswith("-vectorize-figure-batch")


def discover_outputs(active_only: bool = True) -> list[tuple[Path, Path]]:
    pairs = []
    for html in sorted(OUTPUTS.rglob("*.html")):
        if BASELINES in html.parents:
            continue
        if active_only and not is_current_output(html):
            continue
        json_path = html.with_suffix(".json")
        if json_path.exists():
            pairs.append((html, json_path))
    return pairs


def load_spec(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def near_border(pixel: tuple[int, int, int]) -> bool:
    return all(abs(channel - 208) <= 8 for channel in pixel[:3])


def near_page_background(pixel: tuple[int, int, int]) -> bool:
    return all(abs(channel - 238) <= 10 for channel in pixel[:3])


def near_surface_background(pixel: tuple[int, int, int]) -> bool:
    return all(channel >= 248 for channel in pixel[:3])


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
    for y in range(0, max(0, max_y)):
        row = [near_surface_background(image.getpixel((x, y))) for x in range(image.width)]
        for start, end in run_lengths(row):
            run = end - start
            if abs(run - width) > 4 or start > max_x:
                continue
            left_edge = start - 1
            right_edge = start + width
            if left_edge < 0 or right_edge >= image.width:
                continue
            outside = [image.getpixel((left_edge, y)), image.getpixel((right_edge, y))]
            if not all(near_page_background(pixel) or near_border(pixel) for pixel in outside):
                continue
            corner_points = [
                (start, y),
                (start + width - 1, y),
                (start, y + height - 1),
                (start + width - 1, y + height - 1),
            ]
            if all(near_surface_background(image.getpixel(point)) for point in corner_points):
                return (start, y, start + width, y + height)
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
        ], timeout=DEFAULT_SCREENSHOT_TIMEOUT)
        if result.returncode != 0 or not page_png.exists():
            raise RuntimeError(f"Chrome screenshot failed for {html}: {result.stderr.strip()}")
        image = Image.open(page_png).convert("RGB")
        crop_box = find_frame_crop(image, width, height)
        image.crop(crop_box).save(output)


def dump_dom(html: Path, base_url: str) -> str:
    url = f"{base_url}/{html.relative_to(ROOT).as_posix()}"
    result = run_chrome(["--virtual-time-budget=3000", "--dump-dom", url], timeout=DEFAULT_DOM_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(f"Chrome DOM dump failed for {html}: {result.stderr.strip()}")
    return result.stdout


class SurfaceParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    GENERATED_IDS = {"surface", "candidate", "figure", "svg-layer", "heatmap-layer", "overlay-svg", "residual-canvas"}

    def __init__(self) -> None:
        super().__init__()
        self.surface_depths: list[int] = []
        self.has_generated_surface = False
        self.image_tags: list[str] = []
        self.source_refs: list[str] = []
        self.embedded_image_refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs, startend=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs, startend=True)

    def _handle_tag(self, tag: str, attrs: list[tuple[str, str | None]], startend: bool) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if not self.surface_depths and self._is_generated_surface(tag, attr_map):
            self.has_generated_surface = True
            if tag not in self.VOID_TAGS and not startend:
                self.surface_depths.append(1)
            self._audit_attrs(tag, attr_map)
            return
        if not self.surface_depths:
            return
        self._audit_attrs(tag, attr_map)
        if not startend and tag not in self.VOID_TAGS:
            self.surface_depths[-1] += 1

    def _audit_attrs(self, tag: str, attr_map: dict[str, str]) -> None:
        if tag in {"img", "image"}:
            self.image_tags.append(tag)
        for key in ("src", "href", "xlink:href"):
            value = attr_map.get(key, "")
            decoded_value = urllib.parse.unquote(value)
            if SOURCE_RASTER_RE.search(decoded_value):
                self.source_refs.append(f"{tag}.{key}={value}")
            if decoded_value.strip().lower().startswith("data:image/"):
                self.embedded_image_refs.append(f"{tag}.{key}=data:image")

    def _is_generated_surface(self, tag: str, attr_map: dict[str, str]) -> bool:
        text = " ".join(
            attr_map.get(key, "")
            for key in ("id", "class", "aria-label", "data-role")
        ).lower()
        if any(token in text for token in ("qa", "reference", "source raster")):
            return False
        node_id = attr_map.get("id", "")
        classes = set(attr_map.get("class", "").split())
        if node_id == "surface" or attr_map.get("data-role") == "generated-candidate":
            return True
        if node_id in self.GENERATED_IDS and tag in {"canvas", "div", "figure", "svg"}:
            return True
        if classes & {"candidate", "candidate-wrap", "figure-frame", "figure-wrap"}:
            return True
        return "generated" in text and tag in {"canvas", "div", "figure", "section", "svg"}

    def handle_endtag(self, tag: str) -> None:
        if not self.surface_depths or tag in self.VOID_TAGS:
            return
        self.surface_depths[-1] -= 1
        if self.surface_depths[-1] <= 0:
            self.surface_depths.pop()


def audit_rendered_surface(html: Path, dom: str) -> list[str]:
    errors = []
    parser = SurfaceParser()
    parser.feed(dom)
    if not parser.has_generated_surface:
        errors.append(f"{html}: rendered DOM missing a generated surface")
    if parser.image_tags:
        errors.append(f"{html}: rendered generated surface contains image elements {sorted(set(parser.image_tags))}")
    if parser.source_refs:
        errors.append(f"{html}: rendered generated surface references source raster {sorted(set(parser.source_refs))}")
    if parser.embedded_image_refs:
        errors.append(f"{html}: rendered generated surface contains embedded image data URIs {sorted(set(parser.embedded_image_refs))}")
    return errors


def scan_json_for_source_images(json_path: Path, spec: dict, panel_id: str) -> list[str]:
    errors = []

    def looks_like_source_raster(value: str) -> bool:
        lower = urllib.parse.unquote(value).lower()
        if lower.startswith("data:image/"):
            return True
        if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return False
        return panel_id in lower or "assets/reference/" in lower or "assets/full-reference/" in lower or SOURCE_RASTER_RE.search(lower) is not None

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
                        errors.append(f"{json_path}: generated JSON references source raster or embedded image at {'.'.join(child_path)}: {child}")
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + (str(index),))

    visit(spec)
    return errors


def structural_checks(html: Path, json_path: Path, spec: dict, dom: str) -> list[str]:
    errors = []
    html_text = html.read_text(errors="ignore")
    panel_id = str(spec.get("id") or html.stem)
    for key in ("schema", "id", "source", "canvas", "panels"):
        if key not in spec:
            errors.append(f"{json_path}: missing top-level `{key}`")
    canvas = spec.get("canvas", {})
    if not isinstance(canvas.get("width"), int) or not isinstance(canvas.get("height"), int):
        errors.append(f"{json_path}: canvas width/height must be integers")
    source = spec.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if isinstance(source_path, str) and not re.match(r"https?://", source_path):
        resolved_source = (json_path.parent / source_path).resolve()
        if not resolved_source.exists():
            errors.append(f"{json_path}: source.path does not exist relative to spec: {source_path}")
    elif source_path is None:
        errors.append(f"{json_path}: missing source.path")
    errors.extend(scan_json_for_source_images(json_path, spec, panel_id))
    if re.search(r"\bdrawImage\s*\(", html_text):
        errors.append(f"{html}: contains drawImage")
    if "background-image" in html_text:
        errors.append(f"{html}: contains background-image")
    for tag in re.findall(r"<img\b[^>]*>", html_text, flags=re.IGNORECASE):
        lower_tag = tag.lower()
        qa_reference = "reference" in lower_tag or "qa" in lower_tag
        if 'id="reference"' not in tag and "class=\"reference\"" not in tag and not qa_reference:
            errors.append(f"{html}: non-QA img tag `{tag[:120]}`")
        src_match = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        if src_match:
            src = src_match.group(1)
            if not src.startswith(("http://", "https://", "data:")) and "${" not in src:
                resolved_src = (html.parent / src).resolve()
                if not resolved_src.exists():
                    errors.append(f"{html}: img src does not exist relative to HTML: {src}")
    mismatches = sorted(set(re.findall(r'data-[a-zA-Z0-9_-]*validation="mismatch"', dom)))
    if mismatches:
        errors.append(f"{html}: renderer validation mismatch {', '.join(mismatches)}")
    errors.extend(audit_rendered_surface(html, dom))
    tick_labels = set(re.findall(r'data-role="tick-label"[^>]*data-axis="([^"]+)"[^>]*data-value="([^"]+)"', dom))
    tick_marks = set(re.findall(r'data-role="(?:axis-tick-mark|colorbar-tick-mark)"[^>]*data-axis="([^"]+)"[^>]*data-value="([^"]+)"', dom))
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


def validate_output(
    index: int,
    html: Path,
    json_path: Path,
    spec: dict,
    panel_id: str,
    base_url: str,
    tmp: Path,
    structural_only: bool,
    update_baselines: bool,
    threshold: float,
) -> tuple[list[str], list[str]]:
    errors = []
    messages = []
    baseline = BASELINES / f"{panel_id}.png"
    current = tmp / f"{index:04d}-{panel_id}.png"
    try:
        dom = dump_dom(html, base_url)
        errors.extend(structural_checks(html, json_path, spec, dom))
        if structural_only:
            return errors, messages
        capture_panel(html, spec, base_url, current)
        if update_baselines:
            current.replace(baseline)
            messages.append(f"baseline updated: {baseline.relative_to(ROOT)}")
        else:
            ok, message = compare_images(current, baseline, threshold)
            messages.append(message)
            if not ok:
                errors.append(f"{html}: visual regression {message}")
    except Exception as exc:
        errors.append(f"{html}: {exc}")
    return errors, messages


def output_label(html: Path, panel_id: str) -> str:
    rel_parent = html.parent.relative_to(ROOT)
    return f"{panel_id} [{rel_parent}]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-baselines", action="store_true", help="write baseline screenshots")
    parser.add_argument("--structural-only", action="store_true", help="skip screenshot and baseline comparison")
    parser.add_argument("--all-variants", action="store_true", help="include historical/test output variants in default discovery")
    parser.add_argument("--allow-duplicate-ids", action="store_true", help="allow repeated spec ids across selected outputs")
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("VALIDATE_JOBS", "1")), help="parallel output validation workers")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="changed-pixel threshold")
    parser.add_argument("--outputs", nargs="*", help="optional HTML or output directories to validate")
    args = parser.parse_args()

    pairs = discover_outputs(active_only=not args.all_variants and not args.outputs)
    if args.outputs:
        wanted = {Path(item).resolve() for item in args.outputs}
        expanded = set()
        for item in wanted:
            if item.is_dir():
                expanded.update(path.resolve() for path in item.rglob("*.html"))
            else:
                expanded.add(item)
        pairs = [(html, json_path) for html, json_path in pairs if html.resolve() in expanded or html.parent.resolve() in expanded]
    if not pairs:
        print("No generated outputs found", file=sys.stderr)
        return 2

    BASELINES.mkdir(parents=True, exist_ok=True)
    errors = []
    seen_ids: dict[str, Path] = {}
    enforce_unique_ids = not args.allow_duplicate_ids and not args.all_variants
    jobs = max(1, args.jobs)
    with serve_repo() as base_url, tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        work = []
        for index, (html, json_path) in enumerate(pairs):
            spec = load_spec(json_path)
            panel_id = str(spec.get("id") or html.stem)
            if enforce_unique_ids and panel_id in seen_ids:
                errors.append(f"{html}: duplicate spec id `{panel_id}` also used by {seen_ids[panel_id]}")
            else:
                seen_ids[panel_id] = html
            print(f"== {output_label(html, panel_id)}", flush=True)
            work.append((index, html, json_path, spec, panel_id))

        if jobs == 1:
            for item in work:
                item_errors, messages = validate_output(
                    *item,
                    base_url,
                    tmp,
                    args.structural_only,
                    args.update_baselines,
                    args.threshold,
                )
                errors.extend(item_errors)
                for message in messages:
                    print(message, flush=True)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                future_to_item = {
                    executor.submit(
                        validate_output,
                        *item,
                        base_url,
                        tmp,
                        args.structural_only,
                        args.update_baselines,
                        args.threshold,
                    ): item
                    for item in work
                }
                retry_items = []
                total = len(future_to_item)
                for completed, future in enumerate(concurrent.futures.as_completed(future_to_item), start=1):
                    item_errors, messages = future.result()
                    if item_errors:
                        retry_items.append(future_to_item[future])
                    else:
                        errors.extend(item_errors)
                    for message in messages:
                        print(message, flush=True)
                    if completed == total or completed % 10 == 0:
                        print(f"completed {completed}/{total}", flush=True)
                if retry_items:
                    print(f"retrying {len(retry_items)} failed output(s) sequentially", flush=True)
                    for item in retry_items:
                        item_errors, messages = validate_output(
                            *item,
                            base_url,
                            tmp,
                            args.structural_only,
                            args.update_baselines,
                            args.threshold,
                        )
                        errors.extend(item_errors)
                        for message in messages:
                            print(message, flush=True)

    if errors:
        print("\nValidation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("\nValidation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
