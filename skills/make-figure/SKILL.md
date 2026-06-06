---
name: make-figure
description: Reconstruct raster images of scientific figures into editable, configurable HTML plus a semantic JSON specification. Use when the user invokes $make-figure, asks to recreate a paper figure from a PNG/JPEG/screenshot, wants a no-source-image HTML reconstruction, or needs chart panels converted into editable axes, marks, annotations, legends, styles, and data recipes.
---

# Make Figure

## Objective

Convert a raster scientific figure or cropped panel into two deliverables:

- `figure-id.json`: semantic, editable figure specification.
- `figure-id.html`: generated reconstruction rendered from the JSON spec.

The generated candidate must not reuse the source raster as a visual layer. The source image may appear only in clearly labeled QA/reference views.

## Workflow

1. Inspect the source raster at native resolution. Determine whether the input is a single panel, multipanel figure, chart, schematic, heatmap, raster plot, microscopy image, or mixed figure.
2. Create or infer a panel inventory with pixel dimensions, plot boxes, axes, labels, legends, colorbars, annotations, and visible mark types.
3. Create a semantic relationship inventory: coordinate systems, layout objects, derived marks/text, source-calibrated anchors, and validation constraints.
4. Choose renderers by layer: SVG/DOM for axes, labels, legends, paths, brackets, and annotations; canvas for heatmaps, rasters, dense dots, generated textures, and pixel-native fields.
5. Write the JSON spec first. Include dimensions, scales, domains, ticks, text, marks, renderer hints, style tokens, provenance, and confidence notes.
6. Build the HTML so every visible element is generated from the JSON. Keep stable IDs/classes/data attributes for programmatic edits.
7. Include an optional QA toggle that shows the source image separately from the generated candidate. Label it clearly as reference-only.
8. Verify in a browser at source dimensions. Compare alignment, plot grammar, text hierarchy, mark density, axes, tick positions, and annotations. Iterate until the reconstruction is plausibly editable and visually close.

Read `references/semantic-figure-ir.md` and `references/reconstruction-contract.md` when implementing a nontrivial panel or when deciding schema fields.

Use `assets/hybrid-renderer-template.html` as a starting point for new outputs when no better project-local renderer exists.

## Output Contract

Place outputs next to the source image unless the user gives another destination. Use clear names such as:

- `my-panel.json`
- `my-panel.html`
- optional `my-panel-visual-elements.json`
- optional `my-panel-qa.png` or browser screenshot

The HTML must load or embed the JSON spec and render from it. Prefer loading an adjacent `.json` file for configurability. It is acceptable to embed the initial spec in a `<script type="application/json">` fallback if the file also exists separately.

## Non-Negotiables

- Do not use the source PNG/JPEG/SVG as the generated visual layer.
- Do not call `drawImage(sourceRaster)` or set the source raster as a CSS background in the generated candidate.
- Do not flatten axes, ticks, labels, legends, or annotations into an image.
- Do not invent misleading marks, such as rectangular error boxes for curve-following uncertainty bands.
- Record uncertain inferences in `confidence` or `provenance` instead of pretending they are measured data.

## Renderer Rules

- Use SVG for axes, ticks, paths, contours, brackets, arrows, legends, and moderately sized editable marks.
- Use DOM for text-heavy schematics or labels where direct editing matters.
- Use canvas for heatmaps, matrix images, rasters, dense scatter fields, microscopy-like generated texture, and large point sets.
- Use hybrid rendering for most scientific figures: canvas for dense generated fields, SVG/DOM for structure.

## Quality Checklist

Before finishing, verify:

- Native canvas/page dimensions match the source crop.
- Plot boxes, tick labels, event anchors, and annotations share the same coordinate transforms.
- Visible axes have editable ticks and labels unless intentionally suppressed.
- Related objects remain linked in the rendered DOM, such as tick mark/label pairs, legends to series, colorbars to color scales, and grid lines to grid planes.
- Text has explicit alignment and does not overlap neighboring labels.
- The JSON can be edited to change labels, domains, colors, or data recipes without rewriting HTML.
- Any QA reference layer is visually and semantically separate from the generated candidate.
