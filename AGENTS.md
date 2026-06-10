# Repository Instructions

This repository contains the vectorize-figure agent skill and its validation
harness.

- Canonical skill: `skills/vectorize-figure/SKILL.md`
- Skill references: `skills/vectorize-figure/references/`
- Viewer hub: `outputs/index.html`
- Primary viewers: `outputs/full-figure-batch-viewer.html` and `outputs/vectorize-figure-batch-gallery.html`

For figure reconstruction work, generated candidates must not reuse the source
raster as a visual layer. Source images are allowed only in clearly labeled
QA/reference views outside the generated-surface root.

For multi-panel figures, try a whole-composite reconstruction only when it can
remain semantic and inspectable. If that fails syntax, no-raster-reuse,
rendered-pixel, or visual-readability checks, crop all source-supported
subpanels and run the vectorize-figure workflow on each crop before assembling
a composite.

Reference images under `assets/` are test fixtures with source-calibrated
pixel coordinates baked into the output specs. Never resize or recompress them.

Run these validation commands before handing off substantial changes:

```bash
python3 scripts/validate_vectorize_figure_workflow.py --jobs 4
python3 scripts/validate_vectorize_figure_workflow.py --all-variants --skip-browser --jobs 4
python3 scripts/validate_vectorize_figure_workflow.py --all-gallery --jobs 4
```

Browser-backed checks need Chrome; set `CHROME_BIN` if it is not on the default
path, or use `--skip-browser` for structural-only runs.
