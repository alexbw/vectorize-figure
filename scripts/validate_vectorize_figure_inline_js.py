#!/usr/bin/env python3
"""Validate inline JavaScript in vectorize-figure viewer HTML files."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
VIEWERS = [
    ROOT / "outputs" / "index.html",
    ROOT / "outputs" / "full-figure-batch-viewer.html",
    ROOT / "outputs" / "vectorize-figure-batch-gallery.html",
]


class ScriptExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_script = False
        self.current: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        script_type = attr_map.get("type", "").lower()
        if script_type and script_type not in {"application/javascript", "text/javascript", "module"}:
            return
        self.in_script = True
        self.current = []

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.in_script:
            self.scripts.append("".join(self.current))
            self.in_script = False
            self.current = []


def extract_scripts_from_text(text: str) -> list[str]:
    parser = ScriptExtractor()
    parser.feed(text)
    return [script for script in parser.scripts if script.strip()]


def extract_scripts(path: Path) -> list[str]:
    return extract_scripts_from_text(path.read_text(errors="replace"))


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("Inline JavaScript validation skipped: node not found")
        return 0

    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for viewer in VIEWERS:
            if not viewer.exists():
                errors.append(f"missing {viewer.relative_to(ROOT)}")
                continue
            scripts = extract_scripts(viewer)
            if not scripts:
                continue
            for index, script in enumerate(scripts, start=1):
                script_path = tmp / f"{viewer.stem}-{index}.js"
                script_path.write_text(script)
                result = subprocess.run(
                    [node, "--check", str(script_path)],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if result.returncode != 0:
                    errors.append(
                        f"{viewer.relative_to(ROOT)} script {index}: {result.stderr.strip() or result.stdout.strip()}"
                    )

    if errors:
        print("Inline JavaScript validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Inline JavaScript validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
