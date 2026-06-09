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
QA_OUTPUT_RE = re.compile(
    r'<script\b[^>]*\bid=["\']figure-qa-output["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


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


def page_url(html: Path, base_url: str, query: str | None = None) -> str:
    url = f"{base_url}/{html.relative_to(ROOT).as_posix()}"
    if query:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"
    return url


def dump_dom(html: Path, base_url: str, query: str | None = None) -> str:
    url = page_url(html, base_url, query)
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


def extract_qa_report(dom: str) -> dict | None:
    match = QA_OUTPUT_RE.search(dom)
    if not match:
        return None
    raw = match.group(1).strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"could not parse figure-qa-output JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("figure-qa-output JSON must be an object")
    return value


def _item_id(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("role") or value)
    return str(value)


def summarize_layout_qa_item(item: object) -> str:
    if not isinstance(item, dict):
        return str(item)
    if "a" in item and "b" in item:
        return f"{_item_id(item['a'])} vs {_item_id(item['b'])}"
    if "text" in item and "zone" in item:
        return f"{_item_id(item['text'])} over {_item_id(item['zone'])}"
    if "id" in item:
        return _item_id(item)
    return str(item)


def audit_layout_qa_report(html: Path, report: dict | None) -> list[str]:
    if report is None:
        return []
    layout = report.get("layoutQa")
    if layout is None:
        return []
    if not isinstance(layout, dict):
        return [f"{html}: figure layout QA report must be an object"]

    failures = {
        "protectedTextCollisions": "protected text overlaps",
        "clippedProtectedText": "protected text is clipped",
        "protectedTextExclusionCollisions": "protected text intersects an exclusion zone",
        "protectedTextMetadataMissing": "protected text is missing stable semantic metadata",
        "boundedMarkEscapes": "bounded marks escape owner boxes",
    }
    errors = []
    for key, label in failures.items():
        items = layout.get(key) or []
        if not isinstance(items, list):
            errors.append(f"{html}: layout QA `{key}` must be a list")
            continue
        if items:
            examples = "; ".join(summarize_layout_qa_item(item) for item in items[:4])
            suffix = f": {examples}" if examples else ""
            errors.append(f"{html}: layout QA failure: {label}{suffix}")
    return errors


SIDE_ROW_BLOCK_STRIP_TYPES = {"sideRowBlockStrip", "rowBlockSideStrip", "rowBlockStrip"}


def is_side_strip_like(item: dict) -> bool:
    item_type = str(item.get("type") or "")
    item_id = str(item.get("id") or "").lower()
    return item_type in SIDE_ROW_BLOCK_STRIP_TYPES or (
        item_type == "segmentedColorbar" and ("strip" in item_id or item.get("linkedAxis") or item.get("linked_axis"))
    )


def segment_has_boundaries(segment: dict, orientation: str) -> bool:
    if orientation == "horizontal":
        return (
            ("fromX" in segment or "x1" in segment or "startX" in segment)
            and ("toX" in segment or "x2" in segment or "endX" in segment)
        ) or (("from" in segment or "start" in segment or "valueStart" in segment or "value_start" in segment) and ("to" in segment or "end" in segment or "valueEnd" in segment or "value_end" in segment))
    return (
        ("fromY" in segment or "y1" in segment or "startY" in segment)
        and ("toY" in segment or "y2" in segment or "endY" in segment)
    ) or (("from" in segment or "start" in segment or "valueStart" in segment or "value_start" in segment) and ("to" in segment or "end" in segment or "valueEnd" in segment or "value_end" in segment))


def float_value(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bbox_edge_value(bbox: dict, edge: str) -> float | None:
    x = float_value(bbox.get("x"))
    y = float_value(bbox.get("y"))
    width = float_value(bbox.get("width"))
    height = float_value(bbox.get("height"))
    if edge == "left":
        return x
    if edge == "top":
        return y
    if edge == "right" and x is not None and width is not None:
        return x + width
    if edge == "bottom" and y is not None and height is not None:
        return y + height
    return None


def resolve_alignment_target(panel: dict, plot: dict, layout_by_id: dict[str, dict], target: str) -> float | None:
    object_id, separator, edge = target.rpartition(".")
    if not separator or edge not in {"left", "right", "top", "bottom"}:
        return None
    panel_id = str(panel.get("id") or "")
    data_bbox_targets = {
        f"{panel_id}.plot.dataBbox",
        f"{panel_id}.plot.data_bbox",
        f"{panel_id}.dataBbox",
        f"{panel_id}.data_bbox",
        "plot.dataBbox",
        "plot.data_bbox",
        "dataBbox",
        "data_bbox",
    }
    if object_id in data_bbox_targets:
        return bbox_edge_value(plot.get("dataBbox") or plot.get("data_bbox") or {}, edge)
    item = layout_by_id.get(object_id)
    if isinstance(item, dict):
        return bbox_edge_value(item.get("bbox") or item.get("box") or {}, edge)
    return None


def validate_alignment_contract(
    errors: list[str],
    json_path: Path,
    panel: dict,
    plot: dict,
    layout_by_id: dict[str, dict],
    owner_id: str,
    source_bbox: dict,
    alignment: dict,
) -> None:
    alignment_id = alignment.get("id")
    source_edge = str(alignment.get("sourceEdge") or alignment.get("source_edge") or "").lower()
    target = alignment.get("target")
    if not alignment_id:
        errors.append(f"{json_path}: {owner_id} alignment is missing a stable id")
    if source_edge not in {"left", "right", "top", "bottom"}:
        errors.append(f"{json_path}: {owner_id} alignment `{alignment_id or 'alignment'}` has invalid sourceEdge")
        return
    if not isinstance(target, str):
        errors.append(f"{json_path}: {owner_id} alignment `{alignment_id or 'alignment'}` is missing target")
        return
    source_value = bbox_edge_value(source_bbox, source_edge)
    target_value = resolve_alignment_target(panel, plot, layout_by_id, target)
    if source_value is None or target_value is None:
        errors.append(f"{json_path}: {owner_id} alignment `{alignment_id or 'alignment'}` could not resolve source/target geometry")
        return
    delta = float_value(alignment.get("deltaPx", alignment.get("delta_px", 0))) or 0.0
    tolerance = float_value(alignment.get("tolerancePx", alignment.get("tolerance_px", 0.75))) or 0.75
    measured = source_value - target_value
    if abs(measured - delta) > tolerance:
        errors.append(f"{json_path}: {owner_id} alignment `{alignment_id or 'alignment'}` expected delta {delta:g}px but measured {measured:g}px")


def validate_tick_alignment_contract(
    errors: list[str],
    json_path: Path,
    panel: dict,
    plot: dict,
    layout_by_id: dict[str, dict],
    axis_key: str,
    tick: dict,
    alignment: dict,
) -> None:
    data_bbox = plot.get("dataBbox") or plot.get("data_bbox") or {}
    axis = plot.get(axis_key) or {}
    domain = axis.get("domain") or []
    if len(domain) != 2:
        return
    value = float_value(tick.get("value"))
    start = float_value(domain[0])
    end = float_value(domain[1])
    if value is None or start is None or end is None or start == end:
        return
    if axis_key == "x":
        box_start = bbox_edge_value(data_bbox, "left")
        box_end = bbox_edge_value(data_bbox, "right")
    else:
        box_start = bbox_edge_value(data_bbox, "top")
        box_end = bbox_edge_value(data_bbox, "bottom")
    if box_start is None or box_end is None:
        return
    tick_coord = box_start + ((value - start) / (end - start)) * (box_end - box_start)
    target = alignment.get("target")
    target_value = resolve_alignment_target(panel, plot, layout_by_id, target) if isinstance(target, str) else None
    if target_value is None:
        errors.append(f"{json_path}: {panel.get('id') or 'panel'} {axis_key} tick {tick.get('value')} alignment could not resolve target")
        return
    delta = float_value(alignment.get("deltaPx", alignment.get("delta_px", 0))) or 0.0
    tolerance = float_value(alignment.get("tolerancePx", alignment.get("tolerance_px", 0.75))) or 0.75
    measured = tick_coord - target_value
    if abs(measured - delta) > tolerance:
        errors.append(f"{json_path}: {panel.get('id') or 'panel'} {axis_key} tick {tick.get('value')} alignment expected delta {delta:g}px but measured {measured:g}px")


def audit_semantic_layout_contract(json_path: Path, spec: dict) -> list[str]:
    errors = []

    def validate_axis_offset(panel_id: str, plot_id: str, data_bbox: dict, axis: dict, axis_key: str) -> None:
        offset = axis.get("offsetFromDataBbox") or axis.get("offset_from_data_bbox")
        line = axis.get("line")
        if not isinstance(offset, dict) or not isinstance(line, dict) or not isinstance(data_bbox, dict):
            return
        edge = str(offset.get("edge") or "").lower()
        try:
            pixels = float(offset.get("pixels"))
        except (TypeError, ValueError):
            errors.append(f"{json_path}: {panel_id}.{plot_id} {axis_key} offsetFromDataBbox is missing numeric pixels")
            return
        if edge == "bottom":
            data_edge = float(data_bbox.get("y", 0)) + float(data_bbox.get("height", 0))
            axis_values = [float(line[key]) for key in ("y1", "y2") if key in line]
        elif edge == "top":
            data_edge = float(data_bbox.get("y", 0))
            axis_values = [float(line[key]) for key in ("y1", "y2") if key in line]
            pixels = -pixels
        elif edge == "left":
            data_edge = float(data_bbox.get("x", 0))
            axis_values = [float(line[key]) for key in ("x1", "x2") if key in line]
            pixels = -pixels
        elif edge == "right":
            data_edge = float(data_bbox.get("x", 0)) + float(data_bbox.get("width", 0))
            axis_values = [float(line[key]) for key in ("x1", "x2") if key in line]
        else:
            errors.append(f"{json_path}: {panel_id}.{plot_id} {axis_key} offsetFromDataBbox has unsupported edge `{edge}`")
            return
        if not axis_values:
            errors.append(f"{json_path}: {panel_id}.{plot_id} {axis_key} offsetFromDataBbox has no comparable line coordinate")
            return
        measured = sum(axis_values) / len(axis_values) - data_edge
        if abs(measured) <= 0.75:
            errors.append(f"{json_path}: {panel_id}.{plot_id} {axis_key} declares offsetFromDataBbox but line is still derived from dataBbox edge")
        if abs(measured - pixels) > 0.75:
            errors.append(f"{json_path}: {panel_id}.{plot_id} {axis_key} offsetFromDataBbox expected {pixels:g}px but line measures {measured:g}px")

    for panel in spec.get("panels") or []:
        panel_id = str(panel.get("id") or "panel")
        plot = panel.get("plot") or {}
        layout_by_id = {str(item.get("id")): item for item in panel.get("layoutObjects") or [] if isinstance(item, dict) and item.get("id")}
        if isinstance(plot, dict):
            axes = plot.get("axes") or {}
            x_axis = axes.get("xAxis") or axes.get("x_axis") or {}
            if isinstance(x_axis, dict) and isinstance(x_axis.get("originAlignment") or x_axis.get("origin_alignment"), dict):
                origin_alignment = x_axis.get("originAlignment") or x_axis.get("origin_alignment")
                tick_value = origin_alignment.get("tickValue", origin_alignment.get("tick_value"))
                matching_ticks = [tick for tick in (plot.get("x") or {}).get("ticks") or [] if isinstance(tick, dict) and tick.get("value") == tick_value]
                if not matching_ticks:
                    errors.append(f"{json_path}: {panel_id}.plot xAxis originAlignment references missing tickValue {tick_value}")
                else:
                    validate_tick_alignment_contract(errors, json_path, panel, plot, layout_by_id, "x", matching_ticks[0], origin_alignment)
            for axis_key in ("x", "y"):
                axis_spec = plot.get(axis_key) or {}
                if not isinstance(axis_spec, dict):
                    continue
                for tick in axis_spec.get("ticks") or []:
                    if isinstance(tick, dict) and isinstance(tick.get("alignment"), dict):
                        validate_tick_alignment_contract(errors, json_path, panel, plot, layout_by_id, axis_key, tick, tick["alignment"])
        for plot in panel.get("plotGroups") or panel.get("plot_groups") or []:
            if not isinstance(plot, dict):
                continue
            plot_id = str(plot.get("id") or "plot")
            if plot.get("type") == "heatmapPlot" and plot.get("dataBbox") and (plot.get("x") or {}).get("ticks"):
                axes = plot.get("axes") or {}
                x_axis = axes.get("xAxis") or axes.get("x_axis")
                if not isinstance(x_axis, dict) or not isinstance(x_axis.get("line"), dict):
                    errors.append(f"{json_path}: {panel_id}.{plot_id} heatmap plot must encode an explicit xAxis.line separate from dataBbox")
                else:
                    if not x_axis.get("id"):
                        errors.append(f"{json_path}: {panel_id}.{plot_id} explicit xAxis.line is missing a stable axis id")
                    if not (x_axis.get("tickLabelBand") or x_axis.get("tick_label_band")):
                        errors.append(f"{json_path}: {panel_id}.{plot_id} explicit xAxis.line is missing tickLabelBand")
                    validate_axis_offset(panel_id, plot_id, plot.get("dataBbox") or plot.get("data_bbox") or {}, x_axis, "xAxis")
        for item in panel.get("layoutObjects") or []:
            if not isinstance(item, dict) or not is_side_strip_like(item):
                continue
            item_id = str(item.get("id") or item.get("type") or "side-strip")
            item_type = str(item.get("type") or "")
            if item_type == "segmentedColorbar":
                errors.append(f"{json_path}: {panel_id}.{item_id} models an axis side row-block strip as generic segmentedColorbar; use sideRowBlockStrip with segments, separators, borders, linkedAxis, and exclusionZone")
            if "bbox" not in item and "box" not in item:
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip is missing bbox")
            if not (item.get("linkedAxis") or item.get("linked_axis")):
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip is missing linkedAxis")
            if not (item.get("exclusionZone") or item.get("exclusion_zone")):
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip is missing exclusionZone")
            if not item.get("sharedLayoutFrame") and not item.get("shared_layout_frame"):
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip is missing sharedLayoutFrame")
            alignments = item.get("alignments") or []
            if not isinstance(alignments, list) or not alignments:
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip is missing alignment constraints")
            else:
                for alignment in alignments:
                    if isinstance(alignment, dict):
                        validate_alignment_contract(errors, json_path, panel, panel.get("plot") or {}, layout_by_id, f"{panel_id}.{item_id}", item.get("bbox") or item.get("box") or {}, alignment)
                    else:
                        errors.append(f"{json_path}: {panel_id}.{item_id} alignment must be an object")
            segments = item.get("segments") or []
            if not isinstance(segments, list) or len(segments) < 2:
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip must encode at least two segment objects")
                continue
            orientation = str(item.get("orientation") or "vertical")
            for index, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    errors.append(f"{json_path}: {panel_id}.{item_id} segment {index} must be an object")
                    continue
                if not segment.get("id"):
                    errors.append(f"{json_path}: {panel_id}.{item_id} segment {index} is missing a stable id")
                if not (segment.get("fill") or segment.get("color")):
                    errors.append(f"{json_path}: {panel_id}.{item_id} segment {index} is missing fill/color")
                if not segment_has_boundaries(segment, orientation):
                    errors.append(f"{json_path}: {panel_id}.{item_id} segment {index} is missing explicit boundaries")
            separators = item.get("separators") or item.get("boundaries") or []
            if not isinstance(separators, list) or not separators:
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip must encode separator/boundary strokes")
            borders = item.get("borders") or []
            if not isinstance(borders, list) or not borders:
                errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip must encode edge/border strokes")
            components = item.get("components") or []
            expected_components = item.get("expectedComponentCount") or item.get("expected_component_count")
            if expected_components is not None:
                if not isinstance(components, list) or len(components) < int(expected_components):
                    errors.append(f"{json_path}: {panel_id}.{item_id} side row-block strip encodes {len(components) if isinstance(components, list) else 0}/{expected_components} visible components")
                for index, component in enumerate(components if isinstance(components, list) else []):
                    if not isinstance(component, dict):
                        errors.append(f"{json_path}: {panel_id}.{item_id} component {index} must be an object")
                        continue
                    if not component.get("id"):
                        errors.append(f"{json_path}: {panel_id}.{item_id} component {index} is missing a stable id")
                    if not (component.get("bbox") or component.get("box")):
                        errors.append(f"{json_path}: {panel_id}.{item_id} component {index} is missing bbox")
                    if not (component.get("fill") or component.get("color")):
                        errors.append(f"{json_path}: {panel_id}.{item_id} component {index} is missing fill/color")
    return errors


ATTR_RE = re.compile(r'([:\w-]+)\s*=\s*["\']([^"\']*)["\']')
LINE_TAG_RE = re.compile(r"<line\b[^>]*>", re.IGNORECASE)
GROUP_TAG_RE = re.compile(r"<g\b[^>]*>", re.IGNORECASE)
RECT_TAG_RE = re.compile(r"<rect\b[^>]*>", re.IGNORECASE)


def tag_attrs(tag: str) -> dict[str, str]:
    return {key: value for key, value in ATTR_RE.findall(tag)}


def axis_requires_render_validation(panel: dict) -> bool:
    layout_objects = panel.get("layoutObjects") or []
    if any(isinstance(item, dict) and str(item.get("type") or "") in SIDE_ROW_BLOCK_STRIP_TYPES for item in layout_objects):
        return True
    axes = ((panel.get("plot") or {}).get("axes") or {})
    for axis in (axes.get("xAxis") or axes.get("x_axis") or {}, axes.get("yAxis") or axes.get("y_axis") or {}):
        if isinstance(axis, dict) and (axis.get("sourceCalibrated") or axis.get("source_calibrated") or axis.get("explicit")):
            return True
    return False


def axis_is_explicit(axis: dict) -> bool:
    return bool(axis.get("sourceCalibrated") or axis.get("source_calibrated") or axis.get("explicit"))


def collect_panel_axis_specs(panel: dict) -> list[tuple[str, dict]]:
    specs = []
    plot = panel.get("plot") or {}
    axes = plot.get("axes") or {}
    for key in ("xAxis", "yAxis", "x_axis", "y_axis"):
        axis = axes.get(key)
        if isinstance(axis, dict) and isinstance(axis.get("line"), dict) and (axis_is_explicit(axis) or axis_requires_render_validation(panel)):
            axis_id = axis.get("id")
            specs.append((str(axis_id) if axis_id else f"{panel.get('id') or 'panel'}.{key}", axis))
    for plot_group in panel.get("plotGroups") or panel.get("plot_groups") or []:
        if not isinstance(plot_group, dict):
            continue
        axes = plot_group.get("axes") or {}
        force_x_axis = plot_group.get("type") == "heatmapPlot" and plot_group.get("dataBbox") and (plot_group.get("x") or {}).get("ticks")
        for key in ("xAxis", "yAxis", "x_axis", "y_axis"):
            axis = axes.get(key)
            is_x_axis = key in {"xAxis", "x_axis"}
            if isinstance(axis, dict) and isinstance(axis.get("line"), dict) and (axis_is_explicit(axis) or (force_x_axis and is_x_axis)):
                axis_id = axis.get("id")
                specs.append((str(axis_id) if axis_id else f"{panel.get('id') or 'panel'}.{plot_group.get('id') or 'plot'}.{key}", axis))
    return specs


def explicit_axis_expectations(spec: dict) -> list[tuple[str, dict]]:
    expected = []
    for panel in spec.get("panels") or []:
        if not isinstance(panel, dict):
            continue
        for axis_id, axis in collect_panel_axis_specs(panel):
            if not axis.get("id"):
                expected.append((axis_id, {"missing_id": True}))
                continue
            expected.append((str(axis_id), axis["line"]))
    return expected


def tick_alignment_expectations(spec: dict) -> list[tuple[str, object, dict]]:
    expected = []
    for panel in spec.get("panels") or []:
        if not isinstance(panel, dict):
            continue
        plot = panel.get("plot") or {}
        axes = plot.get("axes") or {}
        x_axis = axes.get("xAxis") or axes.get("x_axis") or {}
        x_axis_id = x_axis.get("id") if isinstance(x_axis, dict) else None
        if x_axis_id:
            origin_alignment = x_axis.get("originAlignment") or x_axis.get("origin_alignment")
            if isinstance(origin_alignment, dict) and origin_alignment.get("tickValue", origin_alignment.get("tick_value")) is not None:
                expected.append((str(x_axis_id), origin_alignment.get("tickValue", origin_alignment.get("tick_value")), origin_alignment))
            for tick in (plot.get("x") or {}).get("ticks") or []:
                if not isinstance(tick, dict):
                    continue
                if isinstance(tick.get("alignment"), dict):
                    expected.append((str(x_axis_id), tick.get("value"), tick["alignment"]))
    return expected


def number_attr(attrs: dict[str, str], key: str) -> float | None:
    try:
        return float(attrs[key])
    except (KeyError, ValueError):
        return None


def audit_explicit_axis_rendering(html: Path, dom: str, spec: dict) -> list[str]:
    errors = []
    line_attrs = [tag_attrs(tag) for tag in LINE_TAG_RE.findall(dom)]
    for axis_id, line in explicit_axis_expectations(spec):
        if line.get("missing_id"):
            errors.append(f"{html}: explicit offset axis {axis_id} is missing a stable axis id")
            continue
        matches = [attrs for attrs in line_attrs if attrs.get("data-axis") == axis_id]
        if not matches:
            errors.append(f"{html}: explicit offset axis `{axis_id}` was not rendered with matching data-axis metadata")
            continue
        wanted = {key: float(line[key]) for key in ("x1", "y1", "x2", "y2") if key in line}
        if not wanted:
            continue
        if not any(all(number_attr(attrs, key) is not None and abs(number_attr(attrs, key) - value) <= 0.75 for key, value in wanted.items()) for attrs in matches):
            errors.append(f"{html}: explicit offset axis `{axis_id}` rendered at coordinates that do not match its semantic line")
    for axis_id, value, alignment in tick_alignment_expectations(spec):
        target = alignment.get("target")
        alignment_id = alignment.get("id") or "alignment"
        matches = [
            attrs for attrs in line_attrs
            if attrs.get("data-role") == "axis-tick-mark"
            and attrs.get("data-axis") == axis_id
            and str(attrs.get("data-value")) == str(value)
        ]
        if not matches:
            errors.append(f"{html}: aligned tick `{axis_id}` value `{value}` was not rendered with axis-tick metadata")
            continue
        if target and not any(attrs.get("data-alignment-target") == target for attrs in matches):
            errors.append(f"{html}: aligned tick `{axis_id}` value `{value}` is missing rendered alignment target `{target}`")
    return errors


def audit_side_strip_rendering(html: Path, dom: str, spec: dict) -> list[str]:
    errors = []
    group_attrs = [tag_attrs(tag) for tag in GROUP_TAG_RE.findall(dom)]
    rect_attrs = [tag_attrs(tag) for tag in RECT_TAG_RE.findall(dom)]
    for panel in spec.get("panels") or []:
        for item in panel.get("layoutObjects") or []:
            if not isinstance(item, dict) or str(item.get("type") or "") not in SIDE_ROW_BLOCK_STRIP_TYPES:
                continue
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            segment_count = len(item.get("segments") or [])
            component_count = int(item.get("expectedComponentCount") or item.get("expected_component_count") or len(item.get("components") or []))
            separator_count = len(item.get("separators") or item.get("boundaries") or [])
            border_count = len(item.get("borders") or [])
            rendered_components = len(re.findall(rf'data-role=["\']side-row-block-component["\'][^>]*data-layout-id=["\']{re.escape(item_id)}["\']|data-layout-id=["\']{re.escape(item_id)}["\'][^>]*data-role=["\']side-row-block-component["\']', dom))
            rendered_segments = len(re.findall(rf'data-role=["\']side-row-block-segment["\'][^>]*data-layout-id=["\']{re.escape(item_id)}["\']|data-layout-id=["\']{re.escape(item_id)}["\'][^>]*data-role=["\']side-row-block-segment["\']', dom))
            rendered_separators = len(re.findall(rf'data-role=["\']side-row-block-separator["\'][^>]*data-layout-id=["\']{re.escape(item_id)}["\']|data-layout-id=["\']{re.escape(item_id)}["\'][^>]*data-role=["\']side-row-block-separator["\']', dom))
            rendered_borders = len(re.findall(rf'data-role=["\']side-row-block-border["\'][^>]*data-layout-id=["\']{re.escape(item_id)}["\']|data-layout-id=["\']{re.escape(item_id)}["\'][^>]*data-role=["\']side-row-block-border["\']', dom))
            if component_count and rendered_components < component_count:
                errors.append(f"{html}: side row-block strip `{item_id}` rendered {rendered_components}/{component_count} visible components")
            if not component_count and rendered_segments < segment_count:
                errors.append(f"{html}: side row-block strip `{item_id}` rendered {rendered_segments}/{segment_count} segments")
            if rendered_separators < separator_count:
                errors.append(f"{html}: side row-block strip `{item_id}` rendered {rendered_separators}/{separator_count} separators")
            if rendered_borders < border_count:
                errors.append(f"{html}: side row-block strip `{item_id}` rendered {rendered_borders}/{border_count} borders")
            for component in item.get("components") or []:
                if not isinstance(component, dict) or not component.get("id"):
                    continue
                component_id = str(component["id"])
                matches = [
                    attrs for attrs in rect_attrs
                    if attrs.get("data-role") == "side-row-block-component"
                    and attrs.get("data-layout-id") == item_id
                    and attrs.get("data-component-id") == component_id
                ]
                if not matches:
                    errors.append(f"{html}: side row-block strip `{item_id}` missing rendered component `{component_id}`")
                    continue
                expected_fill = str(component.get("fill") or component.get("color") or "").strip().lower()
                if expected_fill and not any(str(attrs.get("fill") or "").strip().lower() == expected_fill for attrs in matches):
                    errors.append(f"{html}: side row-block strip `{item_id}` component `{component_id}` rendered with wrong fill")
            alignment_ids = [str(alignment.get("id")) for alignment in item.get("alignments") or [] if isinstance(alignment, dict) and alignment.get("id")]
            if alignment_ids:
                matching_groups = [attrs for attrs in group_attrs if attrs.get("data-role") == "side-row-block-strip" and attrs.get("data-layout-id") == item_id]
                rendered_alignment_ids = set()
                for attrs in matching_groups:
                    rendered_alignment_ids.update(str(attrs.get("data-alignments") or "").split())
                missing = [alignment_id for alignment_id in alignment_ids if alignment_id not in rendered_alignment_ids]
                if missing:
                    errors.append(f"{html}: side row-block strip `{item_id}` missing rendered alignment metadata: {', '.join(missing[:4])}")
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
    errors.extend(audit_semantic_layout_contract(json_path, spec))
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
    errors.extend(audit_layout_qa_report(html, extract_qa_report(dom)))
    errors.extend(audit_rendered_surface(html, dom))
    errors.extend(audit_explicit_axis_rendering(html, dom, spec))
    errors.extend(audit_side_strip_rendering(html, dom, spec))
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
        dom = dump_dom(html, base_url, query="qaDom=1")
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
