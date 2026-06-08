---
description: Reconstruct a raster scientific figure into configurable HTML and semantic JSON.
---

# Vectorize Figure

Use this command when the user provides or points to a PNG, JPEG, screenshot, or other raster image of a scientific figure and wants editable HTML plus JSON that implements the figure without reusing the source raster as the generated visual layer.

## Preflight

1. Load the `$vectorize-figure` skill before doing reconstruction work.
2. Identify the source raster path, attachment, or URL. If no image is available, ask for it.
3. Inspect the image at native resolution and record its dimensions.
4. Determine whether the input is a single panel or a multipanel figure.
5. Inventory every visible helper object before rendering: plot frames, axes, tick-label bands, colorbars and tick sides, side color strips, phase bands, legends, scale bars, orientation keys, table rows, annotation brackets, and protected exclusion zones around plot/key/colorbar/legend geometry.
6. Check the current workspace for existing output conventions, renderers, or figure assets.
7. If the working tree is dirty and edits will touch tracked files, note the affected paths before editing.

## Plan

Before creating files:

- state the output directory and filenames
- list the inferred panel inventory and renderer choices
- state which elements will be approximate because source data is unavailable
- confirm that the generated output will not display the source raster; source imagery is for external QA/viewer comparison only

## Commands

1. Create a semantic JSON specification first.
2. Record a semantic relationship inventory: coordinate systems, layout objects, derived marks/text, source-calibrated anchors, protected exclusion zones, owner boxes for bounded marks, and validation constraints.
3. Represent panels, plot boxes, axes, domains, ticks, labels, legends, marks, annotations, style tokens, provenance, and confidence notes.
4. Use SVG or DOM for editable structure such as axes, labels, paths, brackets, and legends.
5. Use canvas only for generated dense fields such as heatmaps, rasters, matrix textures, and large point sets.
6. Build HTML that renders from the JSON spec. Prefer an adjacent JSON file over hard-coded values. Expose the generated candidate through a stable generated-surface root, preferably `id="surface"` or `data-role="generated-candidate"`, and keep source-image QA in separate viewer tooling.
7. Never include the source raster inside the generated surface. Do not use `<img>`, SVG `<image>`, raster `href`/`xlink:href`, `data:image`, CSS `background-image`, or CSS `url(...)` as source or generated raster stand-ins inside the candidate.
8. Never call `drawImage(...)` anywhere in reconstruction HTML, including for offscreen/generated canvases. Use direct canvas primitives, `ImageData`, SVG, or DOM instead.
9. Encode protected text and helper geometry explicitly. Do not rely on renderer defaults for colorbar tick side, axis tick direction, plot boundaries, polar label offsets, table cell text fitting, or text collision avoidance.
10. Keep tick coordinates and tick label anchors separate. If label text needs an offset to avoid collision, the tick mark must remain at the source-calibrated coordinate and the label must record its offset/anchor explicitly.
11. Clip or clamp generated raster/event ticks to their owning plot or strip box. Store the owner box relationship in JSON and expose it in the rendered DOM.
12. For multi-panel composites, try the whole figure first only when the output can remain semantic and inspectable. If that attempt fails syntax, no-raster-reuse, rendered-pixel, or visual-readability checks, crop all source-supported subpanels and run `$vectorize-figure` on each crop before attempting an assembled composite.

## Verification

1. Open or screenshot the generated HTML at the source image dimensions.
2. Check that generated layers render and are not blank.
3. Compare the reconstruction to the source raster for layout, chart grammar, mark density, axis/tick alignment, label hierarchy, and annotation placement.
4. Confirm the JSON can be edited to change labels, domains, colors, and data recipes without rewriting the HTML.
5. Search the generated HTML and rendered generated surface for accidental source-raster reuse, `<img>`, SVG `<image>`, raster hrefs, `data:image`, CSS raster backgrounds, and any `drawImage(` call.
6. Run a rendered protected-text collision check. Any clipped or overlapping panel label, title, tick label, axis label, colorbar label, legend label, phase label, region label, table header, or table cell is a failure.
7. Run a protected-exclusion-zone check. Protected text must not intersect plot boxes, colorbars, orientation keys, legends, helper strips, or declared reserved regions unless the source visibly does so and provenance records the exception.
8. Validate one-to-one tick mark/label pairing, source-calibrated tick coordinates, and colorbar tick side against the source. Adjacent small-multiple edge tick labels must not collide, and collision fixes must not move tick marks off their source coordinates.
9. Validate bounded marks. Raster/event ticks, inward axis ticks, and strip marks must stay inside or be clipped to their owner box.
10. Confirm helper strips are source-supported. Do not add colored x/y axis bars, phase bands, or region strips unless the source visibly contains them.

## Summary

```text
## Result
- Action: reconstructed a raster scientific figure
- Status: success | partial | failed
- Details: output HTML, output JSON, renderer strategy, verification run, remaining uncertainty
```

## Next Steps

- Iterate the JSON spec if visual judging finds alignment or grammar misses.
- Split multipanel figures into cropped subpanels when one-pass reconstruction is too crowded or fails validation, then vectorize each crop independently.
- Add richer renderer support only when a specific mark type requires it.
