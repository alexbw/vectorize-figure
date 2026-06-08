#!/usr/bin/env python3
"""Validate repo-local vectorize-figure plugin surfaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "vectorize-figure"
PLUGIN_MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
PLUGIN_COMMAND = PLUGIN / "commands" / "vectorize-figure.md"
ROOT_COMMAND = ROOT / "commands" / "vectorize-figure.md"
PLUGIN_SKILL = PLUGIN / "skills" / "vectorize-figure"
ROOT_SKILL = ROOT / "skills" / "vectorize-figure"
PLUGIN_AGENT = PLUGIN_SKILL / "agents" / "openai.yaml"
ROOT_AGENT = ROOT_SKILL / "agents" / "openai.yaml"
MARKETPLACE = Path.home() / ".agents" / "plugins" / "marketplace.json"
CACHE_PARENT = Path.home() / ".codex" / "plugins" / "cache" / "personal" / "vectorize-figure"


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    _, raw, _ = text.split("---", 2)
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def text_files(root: Path) -> dict[Path, bytes]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            files[path.relative_to(root)] = path.read_bytes()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-installed-cache",
        action="store_true",
        help="fail if the matching installed Codex plugin cache is absent or differs",
    )
    args = parser.parse_args()
    errors: list[str] = []

    for path in (PLUGIN_MANIFEST, PLUGIN_COMMAND, ROOT_COMMAND, PLUGIN_SKILL / "SKILL.md", ROOT_SKILL / "SKILL.md", PLUGIN_AGENT, ROOT_AGENT):
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")

    if not errors:
        manifest = json.loads(PLUGIN_MANIFEST.read_text())
        version = str(manifest.get("version", ""))
        interface = manifest.get("interface", {})
        expected = {
            "name": "vectorize-figure",
            "skills": "./skills/",
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                errors.append(f"{PLUGIN_MANIFEST.relative_to(ROOT)}: {key} must be {value!r}")
        if interface.get("displayName") != "Vectorize Figure":
            errors.append(f"{PLUGIN_MANIFEST.relative_to(ROOT)}: interface.displayName must be 'Vectorize Figure'")
        if "$vectorize-figure" not in str(interface.get("defaultPrompt", "")):
            errors.append(f"{PLUGIN_MANIFEST.relative_to(ROOT)}: defaultPrompt must mention $vectorize-figure")
        if not version:
            errors.append(f"{PLUGIN_MANIFEST.relative_to(ROOT)}: version must be set")

        skill_frontmatter = frontmatter(PLUGIN_SKILL / "SKILL.md")
        root_skill_frontmatter = frontmatter(ROOT_SKILL / "SKILL.md")
        for label, values in (
            (PLUGIN_SKILL / "SKILL.md", skill_frontmatter),
            (ROOT_SKILL / "SKILL.md", root_skill_frontmatter),
        ):
            if values.get("name") != "vectorize-figure":
                errors.append(f"{label.relative_to(ROOT)}: frontmatter name must be vectorize-figure")
            if "$vectorize-figure" not in values.get("description", ""):
                errors.append(f"{label.relative_to(ROOT)}: description must mention $vectorize-figure")

        for agent in (PLUGIN_AGENT, ROOT_AGENT):
            agent_text = agent.read_text()
            if 'display_name: "Vectorize Figure"' not in agent_text:
                errors.append(f"{agent.relative_to(ROOT)}: display_name must be Vectorize Figure")
            if "$vectorize-figure" not in agent_text:
                errors.append(f"{agent.relative_to(ROOT)}: default prompt must mention $vectorize-figure")
            if "allow_implicit_invocation: true" not in agent_text:
                errors.append(f"{agent.relative_to(ROOT)}: implicit invocation must be enabled")

        if PLUGIN_COMMAND.read_bytes() != ROOT_COMMAND.read_bytes():
            errors.append("root command and plugin command differ")

        plugin_skill_files = text_files(PLUGIN_SKILL)
        root_skill_files = text_files(ROOT_SKILL)
        if plugin_skill_files.keys() != root_skill_files.keys():
            missing_root = sorted(plugin_skill_files.keys() - root_skill_files.keys())
            missing_plugin = sorted(root_skill_files.keys() - plugin_skill_files.keys())
            errors.append(f"skill mirror file set differs missing_root={missing_root} missing_plugin={missing_plugin}")
        else:
            for rel in sorted(plugin_skill_files):
                if plugin_skill_files[rel] != root_skill_files[rel]:
                    errors.append(f"skill mirror differs at {rel}")

        if MARKETPLACE.exists():
            marketplace = json.loads(MARKETPLACE.read_text())
            entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == "vectorize-figure"]
            if len(entries) != 1:
                errors.append(f"{MARKETPLACE}: expected exactly one vectorize-figure marketplace entry")
            else:
                entry = entries[0]
                source = entry.get("source", {})
                policy = entry.get("policy", {})
                if source.get("source") != "local":
                    errors.append(f"{MARKETPLACE}: vectorize-figure source.source must be local")
                if source.get("path") != "./Code/vectorize-figure/plugins/vectorize-figure":
                    errors.append(f"{MARKETPLACE}: vectorize-figure source.path points to {source.get('path')!r}")
                if policy.get("installation") != "AVAILABLE":
                    errors.append(f"{MARKETPLACE}: vectorize-figure policy.installation must be AVAILABLE")
                if policy.get("authentication") != "ON_INSTALL":
                    errors.append(f"{MARKETPLACE}: vectorize-figure policy.authentication must be ON_INSTALL")
                if entry.get("category") != "Productivity":
                    errors.append(f"{MARKETPLACE}: vectorize-figure category must be Productivity")

        if version:
            cache = CACHE_PARENT / version
            if not cache.exists():
                if args.require_installed_cache:
                    errors.append(f"{cache}: installed plugin cache for manifest version is missing")
            else:
                plugin_files = text_files(PLUGIN)
                cache_files = text_files(cache)
                if plugin_files.keys() != cache_files.keys():
                    missing_cache = sorted(plugin_files.keys() - cache_files.keys())
                    extra_cache = sorted(cache_files.keys() - plugin_files.keys())
                    errors.append(f"installed plugin cache file set differs missing_cache={missing_cache} extra_cache={extra_cache}")
                else:
                    for rel in sorted(plugin_files):
                        if plugin_files[rel] != cache_files[rel]:
                            errors.append(f"installed plugin cache differs at {rel}")

    if errors:
        print("Plugin validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Plugin validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
