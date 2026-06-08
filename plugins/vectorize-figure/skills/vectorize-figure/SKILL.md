---
name: vectorize-figure
description: Reconstruct raster images of scientific figures into editable, configurable HTML plus a semantic JSON specification. Use when the user invokes $vectorize-figure, asks to recreate a paper figure from a PNG/JPEG/screenshot, wants a no-source-image HTML reconstruction, or needs chart panels converted into editable axes, marks, annotations, legends, styles, and data recipes.
---

# Vectorize Figure

## Objective

Convert a raster scientific figure or cropped panel into two deliverables:

- `figure-id.json`: semantic, editable figure specification.
- `figure-id.html`: generated reconstruction rendered from the JSON spec.

The generated candidate must not reuse or display the source raster as a visual layer. Reconstruction deliverables must render generated HTML/SVG/DOM/canvas marks from JSON; source rasters belong only in external QA/viewer tooling, not inside the generated surface.

## Workflow

1. Inspect the source raster at native resolution. Determine whether the input is a single panel, multipanel figure, chart, schematic, heatmap, raster plot, microscopy image, or mixed figure.
2. Create or infer a panel inventory with pixel dimensions, plot boxes, axes, labels, legends, colorbars, annotations, and visible mark types.
3. Create a semantic relationship inventory: coordinate systems, layout objects, derived marks/text, source-calibrated anchors, validation constraints, protected exclusion zones, and every visible non-data helper object such as phase bands, colorbars, tick-label bands, side color strips, legends, scale bars, and orientation keys.
4. Choose renderers by layer: SVG/DOM for axes, labels, legends, paths, brackets, and annotations; canvas for heatmaps, rasters, dense dots, generated textures, and pixel-native fields.
5. Write the JSON spec first. Include dimensions, scales, domains, ticks, text, marks, renderer hints, style tokens, provenance, and confidence notes.
6. Build the HTML so every visible element is generated from the JSON. Keep stable IDs/classes/data attributes for programmatic edits.
7. Calibrate typography when text mismatch is visually material. Measure representative source text boxes, try likely sans-serif families through browser-rendered text, and store the winning local fields (`fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `targetWidth`, `fit`, `sourceBox`, and calibration notes) on the text objects.
8. Keep source-image QA outside the generated surface. Prefer separate QA/viewer tooling for source comparisons; if a project-specific viewer includes a source raster, it must be clearly labeled and must not be part of the reconstruction deliverable or generated-surface root.
9. Verify in a browser at source dimensions. Compare alignment, plot grammar, text hierarchy, mark density, axes, tick positions, and annotations. Measure protected text boxes in the rendered browser and fix any overlap before finishing. Tick collision fixes must not move tick marks away from source-calibrated coordinates. Iterate until the reconstruction is plausibly editable and visually close.
10. For multi-panel composites, try the whole figure first only when the output can remain semantic and inspectable. If that attempt fails syntax, no-raster-reuse, rendered-pixel, or visual-readability checks, crop all source-supported subpanels and run `$vectorize-figure` on each crop before attempting an assembled composite.

Read `references/semantic-figure-ir.md` and `references/reconstruction-contract.md` when implementing a nontrivial panel or when deciding schema fields.

Use `assets/hybrid-renderer-template.html` as a starting point for new outputs when no better project-local renderer exists.

Use `scripts/font-calibration/` when typography is the main source of visual drift. The calibration harness may use the source raster for scoring and overlay QA, but the generated candidate still must not render the source raster as a figure layer. Treat the report as evidence of improvement over the starting text render; final acceptance is a results-only visual overlay of original text and attempted text, not a zero-pixel-diff target.

## Output Contract

Place outputs next to the source image unless the user gives another destination. Use clear names such as:

- `my-panel.json`
- `my-panel.html`
- optional `my-panel-visual-elements.json`
- optional external `my-panel-qa.png` or browser screenshot

The HTML must load or embed the JSON spec and render from it. Prefer loading an adjacent `.json` file for configurability. It is acceptable to embed the initial spec in a `<script type="application/json">` fallback if the file also exists separately.

Expose the generated candidate through a stable generated-surface root, preferably `id="surface"` or `data-role="generated-candidate"`. Do not put `<img>`, SVG `<image>`, raster `href`/`xlink:href`, `data:image`, CSS raster backgrounds, or source-raster URLs inside that generated-surface root.

## Non-Negotiables

- Do not use the source PNG/JPEG/SVG as the generated visual layer.
- Do not call `drawImage(...)` anywhere in reconstruction HTML, including for offscreen/generated canvases.
- Do not use SVG `<image>`, raster `href`/`xlink:href`, `data:image`, CSS `background-image`, or CSS `url(...)` to display source or generated raster stand-ins inside the candidate.
- Do not flatten axes, ticks, labels, legends, or annotations into an image.
- Do not invent misleading marks, such as rectangular error boxes for curve-following uncertainty bands.
- Do not leave clipped or overlapping protected text. Table text, phase labels, tick labels, colorbar ticks, axis titles, legend labels, and panel titles must pass a rendered text-box collision check.
- Do not let protected text overlap any declared plot box, colorbar, orientation key, legend mark, or other protected exclusion zone unless the source visibly does so.
- Do not solve tick-label collisions by moving the tick mark away from its source-calibrated axis coordinate. Store the tick coordinate and the label anchor/offset separately.
- Do not let raster/event ticks or tick marks escape their owning plot, strip, or axis bounds unless the source visibly draws outward ticks.
- Do not invent helper structures that are not in the source, such as colored x-axis bands, region bars, legends, or subplots. If a visual element is ambiguous, record uncertainty in provenance and omit it unless it is clearly visible.
- Record uncertain inferences in `confidence` or `provenance` instead of pretending they are measured data.

## Renderer Rules

- Use SVG for axes, ticks, paths, contours, brackets, arrows, legends, and moderately sized editable marks.
- Use DOM for text-heavy schematics or labels where direct editing matters.
- Use canvas for heatmaps, matrix images, rasters, dense scatter fields, microscopy-like generated texture, and large point sets.
- Use hybrid rendering for most scientific figures: canvas for dense generated fields, SVG/DOM for structure.
- Render every visible axis spine, plot boundary, tick mark, tick label, colorbar tick, and colorbar label from a semantic object with stable axis/value or scale/value metadata.
- Store source-calibrated tick positions as semantic coordinates. If text needs collision avoidance, use label anchors, reserved gutters, or explicit label offsets while keeping the tick mark at the source coordinate.
- Keep data boxes, axis boxes, tick-label bands, and helper strips separate. Do not use one `bbox` for heatmap pixels, axes, ticks, labels, and colored strips when the source separates them.
- Colorbars must encode tick side (`left`, `right`, `top`, or `bottom`), tick mark direction, label anchor, and title anchor. Do not infer tick side from generic renderer defaults.
- Every plot/key/colorbar/legend object that occupies visual space must expose an exclusion box for layout QA. Protected text may be adjacent to these boxes, but must not intersect them without a source-visible reason recorded in provenance.
- Adjacent small multiples must reserve a gutter for neighboring tick labels. If a right-edge tick label from one plot collides with a left-edge tick label from the next plot, adjust plot spacing, tick label anchors, or use source-faithful label fitting before accepting the output.
- Polar angle labels must be anchored to the polar plot with a measured radial offset. They should be close enough to read as plot labels but separated from the circle/curve by a clear gap.
- Raster strips and boxed plots must draw all visible plot boundaries. Tick marks and generated event/raster marks must be clipped to, or mathematically clamped within, their encoded owner box unless the source visibly draws outward ticks.

## Quality Checklist

Before finishing, verify:

- Native canvas/page dimensions match the source crop.
- Plot boxes, tick labels, event anchors, and annotations share the same coordinate transforms.
- Tick marks remain at source-calibrated coordinates after any label collision fix. The rendered DOM should expose both `data-source-x`/`data-source-y` or semantic `data-axis`/`data-value` and any label-only offset.
- Visible axes have editable ticks and labels unless intentionally suppressed.
- Related objects remain linked in the rendered DOM, such as tick mark/label pairs, legends to series, colorbars to color scales, and grid lines to grid planes.
- Text has explicit alignment and does not overlap neighboring protected text or plot boundaries. Treat any clipped or overlapping protected label as a failed reconstruction, not an acceptable approximation.
- Protected text does not overlap declared exclusion zones such as plot boxes, colorbars, orientation keys, legends, or bounded helper strips.
- For every colorbar, confirm tick marks, tick labels, and title are on the same side as the source.
- For every helper strip or phase/region band, confirm the strip exists in the source, has the correct orientation, uses the correct colors, and does not overlap axis tick labels.
- For every boxed raster/strip plot, confirm event ticks and axis ticks are within the owner box or clipped by an owner clip path.
- Important text has been visually checked against source text overlays. When calibrated, representative labels improve versus the baseline score and the calibrated fields are recorded in JSON.
- The JSON can be edited to change labels, domains, colors, or data recipes without rewriting HTML.
- Any QA reference layer is visually and semantically separate from the generated candidate.
- Static validation finds no `drawImage(` calls in reconstruction HTML and no `<img>`, SVG `<image>`, raster hrefs, `data:image`, or source-raster URLs inside the rendered generated surface.
