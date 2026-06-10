#!/usr/bin/env python3
import argparse
import math
import re
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8766/outputs/full-figure-batch-viewer.html"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_CHROME_TIMEOUT = 60
FIGURE_IDS = [
    "reference-01-place-code-opto",
    "reference-02-decision-dynamics",
    "reference-03-learning-remapping",
    "reference-04-motor-manifold",
    "reference-05-grid-remapping",
    "reference-06-replay-stimulation",
    "reference-07-cross-region-small-multiples",
    "reference-08-neuropixels-central-heatmap",
]


def paeth(left: int, above: int, upper_left: int) -> int:
    p = left + above - upper_left
    pa = abs(p - left)
    pb = abs(p - above)
    pc = abs(p - upper_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return above
    return upper_left


def read_png(path: Path) -> tuple[int, int, bytes, int]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"{path} is not a PNG")

    pos = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
        elif chunk_type == b"IDAT":
            compressed.extend(payload)
        elif chunk_type == b"IEND":
            break

    if bit_depth != 8:
        raise ValueError(f"{path} uses unsupported PNG bit depth {bit_depth}")
    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_by_type:
        raise ValueError(f"{path} uses unsupported PNG color type {color_type}")

    channels = channels_by_type[color_type]
    row_bytes = width * channels
    raw = zlib.decompress(bytes(compressed))
    rows = bytearray(width * height * channels)
    prior = bytearray(row_bytes)
    src = 0
    dst = 0
    for _ in range(height):
        filter_type = raw[src]
        src += 1
        row = bytearray(raw[src : src + row_bytes])
        src += row_bytes
        for index in range(row_bytes):
            left = row[index - channels] if index >= channels else 0
            above = prior[index]
            upper_left = prior[index - channels] if index >= channels else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 255
            elif filter_type == 2:
                row[index] = (row[index] + above) & 255
            elif filter_type == 3:
                row[index] = (row[index] + ((left + above) // 2)) & 255
            elif filter_type == 4:
                row[index] = (row[index] + paeth(left, above, upper_left)) & 255
            elif filter_type != 0:
                raise ValueError(f"{path} uses unsupported PNG filter {filter_type}")
        rows[dst : dst + row_bytes] = row
        dst += row_bytes
        prior = row
    return width, height, bytes(rows), channels


def stage_crop(width: int, height: int) -> tuple[int, int, int, int]:
    rail = 56
    header = 44
    padding = 18
    available_width = width - rail - (padding * 2)
    available_height = height - header - (padding * 2)
    stage_width = min(available_width, available_height * 1.5)
    stage_height = stage_width * 1024 / 1536
    x = rail + padding + ((available_width - stage_width) / 2)
    y = header + padding + ((available_height - stage_height) / 2)
    return round(x), round(y), round(stage_width), round(stage_height)


def iter_stage_pixels(image: tuple[int, int, bytes, int]):
    width, height, pixels, channels = image
    crop_x, crop_y, crop_w, crop_h = stage_crop(width, height)
    for y in range(crop_y, min(height, crop_y + crop_h)):
        local_y = y - crop_y
        for x in range(crop_x, min(width, crop_x + crop_w)):
            local_x = x - crop_x
            if local_y < 60 and local_x > crop_w - 170:
                continue
            index = (y * width + x) * channels
            yield pixels[index : index + min(channels, 3)]


def stage_stats(image: tuple[int, int, bytes, int]) -> dict:
    count = 0
    total = 0.0
    total_sq = 0.0
    for pixel in iter_stage_pixels(image):
        if len(pixel) == 1:
            value = pixel[0]
        else:
            value = 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]
        count += 1
        total += value
        total_sq += value * value
    mean = total / count
    variance = max(0.0, (total_sq / count) - (mean * mean))
    return {"pixels": count, "mean": mean, "stddev": math.sqrt(variance)}


def stage_diff(a: tuple[int, int, bytes, int], b: tuple[int, int, bytes, int]) -> dict:
    a_pixels = list(iter_stage_pixels(a))
    b_pixels = list(iter_stage_pixels(b))
    if len(a_pixels) != len(b_pixels):
        raise ValueError("stage crop pixel counts differ")
    different = 0
    total_abs = 0
    for left, right in zip(a_pixels, b_pixels):
        delta = sum(abs(int(l) - int(r)) for l, r in zip(left, right))
        if delta:
            different += 1
            total_abs += delta
    return {
        "pixels": len(a_pixels),
        "different": different,
        "mean_abs_delta": total_abs / max(1, len(a_pixels)),
    }


def run_chrome(cmd: list[str], timeout: int = DEFAULT_CHROME_TIMEOUT, attempts: int = 2) -> subprocess.CompletedProcess:
    last_error = None
    for _ in range(attempts):
        try:
            return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            last_error = exc
    raise RuntimeError(f"Chrome failed after {attempts} attempt(s) of {timeout}s: {' '.join(cmd[-3:])}") from last_error


def capture(chrome: str, url: str, output: Path) -> None:
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--hide-scrollbars",
        "--no-first-run",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=3000",
        "--window-size=1536,1024",
        f"--screenshot={output}",
        url,
    ]
    run_chrome(cmd)


def dump_dom(chrome: str, url: str) -> str:
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--no-first-run",
        "--virtual-time-budget=1000",
        "--dump-dom",
        url,
    ]
    result = run_chrome(cmd)
    return result.stdout


def body_dataset(chrome: str, url: str) -> dict[str, str]:
    dom = dump_dom(chrome, url)
    body_match = re.search(r"<body\b[^>]*>", dom)
    body = body_match.group(0) if body_match else ""
    return dict(re.findall(r'\bdata-([a-z0-9_-]+)="([^"]*)"', body))


def dom_state(chrome: str, url: str) -> tuple[str | None, str | None]:
    data = body_dataset(chrome, url)
    return data.get("figure"), data.get("mode")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify full-figure viewer GEN/REF rendering.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--chrome", default=DEFAULT_CHROME)
    parser.add_argument("--keep", action="store_true", help="Keep screenshots under tmp/vectorize-figure-full-figures/viewer-checks.")
    parser.add_argument("figures", nargs="*", help="1-based figure numbers or figure ids. Defaults to all figures.")
    args = parser.parse_args()

    if not Path(args.chrome).exists():
        print(f"Chrome not found: {args.chrome}", file=sys.stderr)
        return 2

    requested = args.figures or [str(index + 1) for index in range(len(FIGURE_IDS))]
    figure_numbers = []
    for item in requested:
        if item.isdigit():
            number = int(item)
        else:
            if item not in FIGURE_IDS:
                print(f"Unknown figure: {item}", file=sys.stderr)
                return 2
            number = FIGURE_IDS.index(item) + 1
        if number < 1 or number > len(FIGURE_IDS):
            print(f"Figure number out of range: {item}", file=sys.stderr)
            return 2
        figure_numbers.append(number)

    server_proc = ensure_server(args.base_url)
    outdir = REPO / "tmp" / "vectorize-figure-full-figures" / "viewer-checks"
    temp_context = tempfile.TemporaryDirectory() if not args.keep else None
    root = outdir if args.keep else Path(temp_context.name)
    root.mkdir(parents=True, exist_ok=True)

    failures = 0
    try:
        for number in figure_numbers:
            figure_id = FIGURE_IDS[number - 1]
            gen_path = root / f"{number:02d}-gen.png"
            ref_path = root / f"{number:02d}-ref.png"
            gen_url = f"{args.base_url}?figure={number}&mode=gen"
            ref_url = f"{args.base_url}?figure={number}&mode=ref"
            try:
                gen_data = body_dataset(args.chrome, gen_url)
                ref_data = body_dataset(args.chrome, ref_url)
                gen_state = (gen_data.get("figure"), gen_data.get("mode"))
                ref_state = (ref_data.get("figure"), ref_data.get("mode"))
                capture(args.chrome, gen_url, gen_path)
                capture(args.chrome, ref_url, ref_path)

                gen = read_png(gen_path)
                ref = read_png(ref_path)
                gen_stats = stage_stats(gen)
                ref_stats = stage_stats(ref)
                diff = stage_diff(gen, ref)
                state_ok = gen_state == (figure_id, "gen") and ref_state == (figure_id, "ref")
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
                    f"{status} {number:02d} {figure_id}: "
                    f"state={gen_state}/{ref_state} "
                    f"outer={gen_data.get('generated-frame-display')}/{gen_data.get('outer-reference-display')} "
                    f"surface={gen_data.get('gen-ready')}/{gen_data.get('generated-surface-display')} "
                    f"internal_ref={gen_data.get('internal-reference-display')} "
                    f"gen_std={gen_stats['stddev']:.2f} ref_std={ref_stats['stddev']:.2f} "
                    f"diff_pixels={diff['different']}/{diff['pixels']} mean_abs_delta={diff['mean_abs_delta']:.3f}",
                    flush=True,
                )
            except Exception as exc:
                ok = False
                print(f"FAIL {number:02d} {figure_id}: {exc}", file=sys.stderr, flush=True)
            if not ok:
                failures += 1
    finally:
        if temp_context:
            temp_context.cleanup()
        stop_server(server_proc)
    if failures:
        print(f"FAIL full viewer: total={len(figure_numbers)} failed={failures}", file=sys.stderr)
    else:
        print(f"OK full viewer: total={len(figure_numbers)} failed=0")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
