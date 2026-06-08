#!/usr/bin/env python3
"""Validate that active surfaces use vectorize-figure naming."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def old_name() -> str:
    return "make" + "-figure"


def old_snake() -> str:
    return "make" + "_figure"


STALE_PATTERNS = [
    re.compile(re.escape("$" + old_name())),
    re.compile(re.escape(old_name())),
    re.compile(re.escape("Make" + " Figure")),
    re.compile(re.escape("validate_" + old_snake())),
    re.compile(re.escape(old_snake())),
    re.compile(re.escape("scientific" + "-figure-reconstruction")),
]

TEXT_ROOTS = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "figure-reconstruction-skill.md",
    ROOT / "docs" / "session-handoff-2026-06-06.md",
    ROOT / "docs" / "text-positioning-mismatch-plan.md",
    ROOT / "commands",
    ROOT / "plugins" / "vectorize-figure",
    ROOT / "skills" / "vectorize-figure",
    ROOT / "scripts",
    ROOT / "tmp",
    ROOT / "outputs",
]

TEXT_SUFFIXES = {".html", ".json", ".js", ".md", ".py", ".txt", ".yaml", ".yml", ".jsonl"}

SKIP_PARTS = {
    ".git",
    "__pycache__",
    "_regression-baselines",
    "gallery-checks",
    "logs",
    "node_modules",
    "plugin-validator-venv",
    "viewer-checks",
}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for root in TEXT_ROOTS:
        if not root.exists() or should_skip(root):
            continue
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES and not should_skip(path):
                files.append(path)
    return sorted(set(files))


def main() -> int:
    errors: list[str] = []
    for path in iter_text_files():
        text = path.read_text(errors="ignore")
        rel = path.relative_to(ROOT)
        for pattern in STALE_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{rel}:{line}: stale name `{match.group(0)}`")

    stale_filenames = []
    for path in ROOT.rglob("*"):
        if should_skip(path):
            continue
        if old_name() in path.name or old_snake() in path.name:
            stale_filenames.append(path.relative_to(ROOT))
    for rel in sorted(stale_filenames):
        errors.append(f"{rel}: stale name in file path")

    if errors:
        print("Rename validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Rename validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
