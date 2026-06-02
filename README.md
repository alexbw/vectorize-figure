# Scientific Figure Reconstruction

Experimental workflow for converting raster scientific figure panels into editable, data-driven HTML reconstructions.

The core rule: generated candidates must not reuse the source PNG as a visual layer. Source images may appear only in clearly labeled QA/reference views.

## Contents

- `docs/figure-reconstruction-skill.md` - working skill/playbook and generalized lessons.
- `examples/no-image-1c/` - dedicated no-image reconstruction of one raster/time-series panel with a QA-only reference toggle.
- `examples/no-image-four/` - earlier four-panel no-image experiment.
- `assets/reference/` - reference PNGs used only for visual QA toggles.

## View Locally

From the repo root:

```bash
python3 -m http.server 8765
```

Then open:

- `http://localhost:8765/examples/no-image-1c/index.html`
- `http://localhost:8765/examples/no-image-four/index.html`

## Reconstruction Principles

- Use a semantic JSON spec as the source of truth.
- Render generated candidates from DOM, SVG, canvas, or hybrid marks.
- Use canvas for heatmaps, rasters, dense points, and pixel-native fields.
- Use SVG/DOM for axes, ticks, labels, legends, annotations, and editable structure.
- Infer chart grammar, not just text boxes: axes, domains, ticks, event anchors, category positions, and label alignment.
- Keep source PNGs out of generated candidates; use them only for QA comparison.

## Current Status

This is an early prototype. The strongest current example is `examples/no-image-1c`, which focuses on faithful axis/tick/event alignment and generated raster/line marks without drawing from the source image.
