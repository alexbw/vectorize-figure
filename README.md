# Vectorize Figure

Experimental workflow for converting raster scientific figure panels into editable, data-driven HTML reconstructions.

The core rule: generated candidates must not reuse the source PNG as a visual layer. Source images may appear only in clearly labeled QA/reference views.

## Contents

- `commands/vectorize-figure.md` - command contract for `$vectorize-figure`.
- `AGENTS.md` - repo-local instructions that make this moved repo and `$vectorize-figure` authoritative for future sessions.
- `plugins/vectorize-figure/` - local Codex plugin bundle.
- `skills/vectorize-figure/` - local skill source mirrored into the plugin.
- `docs/figure-reconstruction-skill.md` - working skill/playbook and generalized lessons.
- `examples/no-image-1c/` - dedicated no-image reconstruction of one raster/time-series panel with a QA-only reference toggle.
- `examples/no-image-four/` - earlier four-panel no-image experiment.
- `assets/reference/` - reference PNGs used only for visual QA toggles.
- `assets/full-reference/` - full composite reference PNGs used only for QA toggles.
- `outputs/index.html` - inspection hub for generated figure viewers.
- `outputs/full-figure-batch-viewer.html` - full composite GEN/REF viewer.
- `outputs/vectorize-figure-batch-gallery.html` - cropped subpanel GEN/REF gallery.

## View Locally

From the repo root:

```bash
python3 -m http.server 8765
```

Then open:

- `http://localhost:8765/outputs/`
- `http://localhost:8765/examples/no-image-1c/index.html`
- `http://localhost:8765/examples/no-image-four/index.html`
- `http://localhost:8765/outputs/full-figure-batch-viewer.html`
- `http://localhost:8765/outputs/vectorize-figure-batch-gallery.html`

## Setup

Python validation uses Pillow:

```bash
python3 -m pip install -r requirements.txt
```

Browser-backed validation expects Chrome by default. Set `CHROME_BIN` or pass
the script-specific `--chrome` option when Chrome is installed somewhere else.

## Validation

Current regression checks:

```bash
python3 scripts/validate_vectorize_figure_workflow.py
python3 scripts/validate_vectorize_figure_workflow.py --jobs 4 --skip-browser
python3 scripts/validate_vectorize_figure_workflow.py --all-variants --jobs 4 --skip-browser
python3 scripts/validate_vectorize_figure_workflow.py --all-gallery
```

Individual checks:

```bash
python3 scripts/audit_figure_ir_relationships.py
python3 scripts/audit_ir_field_coverage.py --strict-high-risk
python3 scripts/validate_vectorize_figure_rename.py
python3 scripts/validate_vectorize_figure_plugin.py
python3 scripts/validate_vectorize_figure_plugin.py --require-installed-cache
python3 scripts/validate_vectorize_figure_inline_js.py
python3 scripts/validate_vectorize_figure_outputs.py --structural-only --jobs 4
python3 scripts/validate_vectorize_figure_outputs.py --all-variants --structural-only --jobs 4
python3 tmp/vectorize-figure-full-figures/verify_no_raster_reuse.py
python3 tmp/vectorize-figure-full-figures/verify_viewer.py --keep
python3 tmp/vectorize-figure-all-subpanels/validate_batch.py
python3 tmp/vectorize-figure-all-subpanels/verify_gallery.py --all
```

The workflow wrapper compiles the Python harness scripts, checks JavaScript helper syntax when Node is available, extracts and syntax-checks inline JavaScript from the viewer HTML files, runs validator unit tests, audits semantic IR field coverage against `schemas/ir-field-coverage.json` so no high-risk field is left as an inert JSON note, reports warning-only denotational relationship gaps, checks plugin/root command and skill surfaces plus the personal marketplace entry when present, guards against stale pre-rename command naming on active surfaces, validates all active output specs, and checks both JSON specs and rendered generated surfaces for source-raster image reuse. The optional `--require-installed-cache` plugin check verifies that the installed Codex plugin cache for the manifest version matches the repo bundle. The viewer checks compare generated and reference screenshots and assert that the iframe generated-surface root is visible while any internal QA/reference image is hidden, so an internal QA image cannot accidentally appear as the generated output.

## Plugin Updates

After editing `plugins/vectorize-figure/`, refresh Codex's local plugin cache:

```bash
python3 /Users/alex/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py plugins/vectorize-figure
codex plugin add vectorize-figure@personal
```

Open a new Codex thread after reinstalling so the updated `$vectorize-figure` skill is loaded.

## Reconstruction Principles

- Use a semantic JSON spec as the source of truth.
- Render generated candidates from DOM, SVG, canvas, or hybrid marks.
- Use canvas for heatmaps, rasters, dense points, and pixel-native fields.
- Use SVG/DOM for axes, ticks, labels, legends, annotations, and editable structure.
- Infer chart grammar, not just text boxes: axes, domains, ticks, event anchors, category positions, and label alignment.
- Keep source PNGs out of generated candidates; use them only for QA comparison.

## Current Status

This is an early prototype. The strongest current examples are the generated full-figure and cropped-panel reconstructions in `outputs/`, which focus on faithful axis/tick/event alignment and generated raster/line marks without drawing from the source image.
