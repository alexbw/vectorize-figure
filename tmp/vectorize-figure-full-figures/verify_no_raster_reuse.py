#!/usr/bin/env python3
import argparse
from html.parser import HTMLParser
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO / "outputs" / "full-figure-batch"
DEFAULT_BASE_URL = "http://127.0.0.1:8766"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_CHROME_TIMEOUT = 60
SOURCE_RASTER_RE = re.compile(r"reference-0[1-8].*\.(?:png|jpg|jpeg|webp)", re.IGNORECASE)


def check_server(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/outputs/full-figure-batch-viewer.html", timeout=3) as response:
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


def run_chrome(cmd: list[str], timeout: int = DEFAULT_CHROME_TIMEOUT, attempts: int = 2) -> subprocess.CompletedProcess:
    last_error = None
    for _ in range(attempts):
        try:
            return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            last_error = exc
    raise RuntimeError(f"Chrome failed after {attempts} attempt(s) of {timeout}s: {' '.join(cmd[-3:])}") from last_error


def dump_dom(chrome: str, url: str) -> str:
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--no-first-run",
        "--virtual-time-budget=3000",
        "--dump-dom",
        url,
    ]
    result = run_chrome(cmd)
    return result.stdout


def figure_outputs() -> list[tuple[str, Path, Path]]:
    pairs = []
    for html in sorted(OUT_ROOT.glob("*/*.html")):
        spec = html.with_suffix(".json")
        if spec.exists():
            pairs.append((html.stem, html, spec))
    return pairs


def line_hits(text: str, patterns: list[re.Pattern], allowed: list[str]) -> list[str]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not any(pattern.search(line) for pattern in patterns):
            continue
        if any(token in line for token in allowed):
            continue
        hits.append(f"{lineno}:{line.strip()}")
    return hits


def scan_json_for_source_images(spec_path: Path, figure_id: str) -> list[str]:
    spec = json.loads(spec_path.read_text())
    hits = []

    def looks_like_source_raster(value: str) -> bool:
        lower = urllib.parse.unquote(value).lower()
        if lower.startswith("data:image/"):
            return True
        if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return False
        return figure_id in lower or "assets/full-reference/" in lower or SOURCE_RASTER_RE.search(lower) is not None

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
                        hits.append(f"{'.'.join(child_path)}:{child}")
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + (str(index),))

    visit(spec)
    return hits


def check_source_path(spec_path: Path) -> list[str]:
    spec = json.loads(spec_path.read_text())
    source = spec.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if not isinstance(source_path, str):
        return ["missing source.path"]
    if re.match(r"https?://", source_path):
        return []
    if not (spec_path.parent / source_path).resolve().exists():
        return [f"source.path does not exist relative to spec: {source_path}"]
    return []


def extract_body_dataset(dom: str) -> dict[str, str]:
    match = re.search(r"<body\b([^>]*)>", dom)
    attrs = match.group(1) if match else ""
    return dict(re.findall(r'(data-[\w-]+)="([^"]*)"', attrs))


class SurfaceParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    GENERATED_IDS = {"surface", "candidate", "figure", "svg-layer", "heatmap-layer", "overlay-svg", "residual-canvas"}

    def __init__(self) -> None:
        super().__init__()
        self.surface_depths: list[int] = []
        self.has_surface = False
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
            self.has_surface = True
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
        text = " ".join(attr_map.get(key, "") for key in ("id", "class", "aria-label", "data-role")).lower()
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


def audit_rendered_surface(chrome: str, base_url: str, figure_id: str, html: Path) -> list[str]:
    rel = html.relative_to(REPO).as_posix()
    url = f"{base_url}/{urllib.parse.quote(rel)}?mode=gen&audit=1"
    dom = dump_dom(chrome, url)
    dataset = extract_body_dataset(dom)
    parser = SurfaceParser()
    parser.feed(dom)
    errors = []

    if not parser.has_surface:
        errors.append("missing generated surface in rendered DOM")
    if parser.image_tags:
        errors.append(f"rendered generated surface contains image elements: {', '.join(parser.image_tags)}")
    if parser.source_refs:
        errors.append(f"rendered generated surface references source raster: {', '.join(parser.source_refs)}")
    if parser.embedded_image_refs:
        errors.append(f"rendered generated surface contains embedded image data URIs: {', '.join(parser.embedded_image_refs)}")
    if dataset.get("data-mode") == "ref":
        errors.append("rendered page is in reference mode")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify full-figure outputs do not use source rasters as generated layers.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--chrome", default=DEFAULT_CHROME)
    args = parser.parse_args()

    if not Path(args.chrome).exists():
        print(f"Chrome not found: {args.chrome}", file=sys.stderr)
        return 2
    server_proc = ensure_server(args.base_url)

    html_patterns = [
        re.compile(r"drawImage\s*\("),
        re.compile(r"background-image\s*:"),
        re.compile(r"background\s*:\s*url"),
        re.compile(r"<image\b", re.I),
        re.compile(r"<img\b", re.I),
        re.compile(r"assets/full-reference"),
        re.compile(r"reference-0[1-8].*\.(?:png|jpg|jpeg|webp)", re.I),
    ]
    allowed_html = [
        '<img id="reference"',
        "reference.src",
        "QA reference",
        "QA-only",
        "Source image is QA-only",
        "source.path",
    ]

    failures = 0
    try:
        for figure_id, html, spec in figure_outputs():
            html_hits = line_hits(urllib.parse.unquote(html.read_text(errors="replace")), html_patterns, allowed_html)
            json_hits = check_source_path(spec) + scan_json_for_source_images(spec, figure_id)
            dom_hits = audit_rendered_surface(args.chrome, args.base_url, figure_id, html)
            ok = not html_hits and not json_hits and not dom_hits
            print(f"{'ok' if ok else 'FAIL'} {figure_id}", flush=True)
            for label, hits in (("html", html_hits), ("json", json_hits), ("dom", dom_hits)):
                for hit in hits:
                    print(f"  {label}: {hit}", flush=True)
            if not ok:
                failures += 1
    finally:
        stop_server(server_proc)

    if failures:
        print(f"FAIL full no-raster: total={len(figure_outputs())} failed={failures}", file=sys.stderr)
    else:
        print(f"OK full no-raster: total={len(figure_outputs())} failed=0")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
