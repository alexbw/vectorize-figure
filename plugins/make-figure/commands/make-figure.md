---
description: Reconstruct a raster scientific figure into configurable HTML and semantic JSON.
---

# Make Figure

Use this command when the user provides or points to a PNG, JPEG, screenshot, or other raster image of a scientific figure and wants editable HTML plus JSON that implements the figure without reusing the source raster as the generated visual layer.

## Preflight

1. Load the `$make-figure` skill before doing reconstruction work.
2. Identify the source raster path, attachment, or URL. If no image is available, ask for it.
3. Inspect the image at native resolution and record its dimensions.
4. Determine whether the input is a single panel or a multipanel figure.
5. Check the current workspace for existing output conventions, renderers, or figure assets.
6. If the working tree is dirty and edits will touch tracked files, note the affected paths before editing.

## Plan

Before creating files:

- state the output directory and filenames
- list the inferred panel inventory and renderer choices
- state which elements will be approximate because source data is unavailable
- confirm that the source raster will be QA-only

## Commands

1. Create a semantic JSON specification first.
2. Record a semantic relationship inventory: coordinate systems, layout objects, derived marks/text, source-calibrated anchors, and validation constraints.
3. Represent panels, plot boxes, axes, domains, ticks, labels, legends, marks, annotations, style tokens, provenance, and confidence notes.
4. Use SVG or DOM for editable structure such as axes, labels, paths, brackets, and legends.
5. Use canvas only for generated dense fields such as heatmaps, rasters, matrix textures, and large point sets.
6. Build HTML that renders from the JSON spec. Prefer an adjacent JSON file over hard-coded values.
7. Include a clearly labeled QA/reference view if the source image is included in the HTML.
8. Never use the source raster as a generated visual layer, CSS background, or canvas `drawImage` source.

## Verification

1. Open or screenshot the generated HTML at the source image dimensions.
2. Check that generated layers render and are not blank.
3. Compare the reconstruction to the source raster for layout, chart grammar, mark density, axis/tick alignment, label hierarchy, and annotation placement.
4. Confirm the JSON can be edited to change labels, domains, colors, and data recipes without rewriting the HTML.
5. Search the generated HTML for accidental source-raster reuse in non-QA layers.

## Summary

```text
## Result
- Action: reconstructed a raster scientific figure
- Status: success | partial | failed
- Details: output HTML, output JSON, renderer strategy, verification run, remaining uncertainty
```

## Next Steps

- Iterate the JSON spec if visual judging finds alignment or grammar misses.
- Split multipanel figures into cropped subpanels when one-pass reconstruction is too crowded.
- Add richer renderer support only when a specific mark type requires it.
