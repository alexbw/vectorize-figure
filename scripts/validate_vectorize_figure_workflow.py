#!/usr/bin/env python3
"""Run the vectorize-figure workflow regression checks."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


PYTHON_FILES = [
    "scripts/test_vectorize_figure_validators.py",
    "scripts/audit_ir_field_coverage.py",
    "scripts/audit_figure_ir_relationships.py",
    "scripts/validate_vectorize_figure_plugin.py",
    "scripts/validate_vectorize_figure_rename.py",
    "scripts/validate_vectorize_figure_inline_js.py",
    "scripts/validate_vectorize_figure_outputs.py",
    "tmp/vectorize-figure-full-figures/verify_no_raster_reuse.py",
    "tmp/vectorize-figure-full-figures/verify_viewer.py",
    "tmp/vectorize-figure-all-subpanels/validate_batch.py",
    "tmp/vectorize-figure-all-subpanels/verify_gallery.py",
    "tmp/vectorize-figure-full-figures/run_batch.py",
    "tmp/vectorize-figure-all-subpanels/run_batch.py",
]

JS_FILES = [
    "tmp/apply_feedback_fixes.js",
    "tmp/regenerate_feedback_panels_v2.js",
    "tmp/font-qa/run-evidence.mjs",
]


def run(label: str, command: list[str]) -> int:
    print(f"\n== {label}", flush=True)
    print(" ".join(command), flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT)
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        print(f"FAILED {label}: exit {result.returncode} after {elapsed:.1f}s", file=sys.stderr, flush=True)
    else:
        print(f"OK {label}: {elapsed:.1f}s", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-browser", action="store_true", help="skip Chrome screenshot/DOM checks")
    parser.add_argument("--all-variants", action="store_true", help="include historical/test output variants in structural checks")
    parser.add_argument("--all-gallery", action="store_true", help="verify all 62 subpanel gallery entries")
    parser.add_argument("--fail-fast", action="store_true", help="stop after the first failed check")
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("VALIDATE_JOBS", "1")), help="parallel structural validation workers")
    args = parser.parse_args()

    node = shutil.which("node")
    js_checks = []
    if node:
        js_checks = [(f"javascript syntax {Path(path).name}", [node, "--check", path]) for path in JS_FILES]

    checks = [
        ("python compile", [sys.executable, "-m", "py_compile", *PYTHON_FILES]),
        *js_checks,
        ("viewer inline javascript", [sys.executable, "scripts/validate_vectorize_figure_inline_js.py"]),
        ("validator unit tests", [sys.executable, "scripts/test_vectorize_figure_validators.py"]),
        ("ir field coverage", [sys.executable, "scripts/audit_ir_field_coverage.py", "--strict-high-risk"]),
        ("relationship audit", [sys.executable, "scripts/audit_figure_ir_relationships.py"]),
        ("plugin surfaces", [sys.executable, "scripts/validate_vectorize_figure_plugin.py"]),
        ("rename guard", [sys.executable, "scripts/validate_vectorize_figure_rename.py"]),
        (
            "structural outputs",
            [
                sys.executable,
                "scripts/validate_vectorize_figure_outputs.py",
                "--structural-only",
                "--jobs",
                str(max(1, args.jobs)),
                *(["--all-variants"] if args.all_variants else []),
            ],
        ),
        ("subpanel batch", [sys.executable, "tmp/vectorize-figure-all-subpanels/validate_batch.py"]),
    ]
    if not args.skip_browser:
        checks.extend([
            ("full no-raster", [sys.executable, "tmp/vectorize-figure-full-figures/verify_no_raster_reuse.py"]),
            ("full viewer", [sys.executable, "tmp/vectorize-figure-full-figures/verify_viewer.py", "--keep"]),
            (
                "subpanel gallery",
                [
                    sys.executable,
                    "tmp/vectorize-figure-all-subpanels/verify_gallery.py",
                    *(["--all"] if args.all_gallery else []),
                ],
            ),
        ])

    failures = 0
    for label, command in checks:
        failed = 1 if run(label, command) else 0
        failures += failed
        if failed and args.fail_fast:
            print(f"\nFAIL workflow: checks={len(checks)} failed={failures}", file=sys.stderr, flush=True)
            return 1
    if failures:
        print(f"\nFAIL workflow: checks={len(checks)} failed={failures}", file=sys.stderr, flush=True)
    else:
        print(f"\nOK workflow: checks={len(checks)} failed=0", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
