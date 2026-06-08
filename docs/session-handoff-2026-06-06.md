# Session Handoff - Figure Reconstruction

Date: 2026-06-06

## Current Objective

Continue iterative reconstruction of scientific figure panels with the `vectorize-figure`
workflow. The active panel is:

- Reference: `assets/reference/reference-02-decision-dynamics-B-reference.png`
- Generated spec: `outputs/reference-02-decision-dynamics-B-vectorize-figure/reference-02-decision-dynamics-B.json`
- Generated HTML: `outputs/reference-02-decision-dynamics-B-vectorize-figure/reference-02-decision-dynamics-B.html`
- Preview URL while the local server is running:
  `http://127.0.0.1:8765/outputs/reference-02-decision-dynamics-B-vectorize-figure/reference-02-decision-dynamics-B.html`

The user expects a preview link after every figure-generation iteration.

## User Priorities

The user is using these panels to improve a general reconstruction system, not
just to hand-tune one figure. Fixes should become reusable renderer/contract
behavior where possible.

Recurring priorities:

- No overlapping text, ticks, labels, legends, or axis/title elements.
- Position labels relative to their associated semantic objects, not absolute
  canvas guesses.
- Preserve source-specific layout details such as axis gaps, tick offsets,
  colorbar-title offsets, table stroke styles, and text-box spacing.
- Treat consistent visual blocks as consistency constraints. If one cell in a
  row has top/bottom strokes, all same-style cells should be checked against
  that style.
- For 3D plots, recognize the scene as 3D without being told and render from a
  coherent projection model.
- Do not use the source raster as the generated visual layer.

## Current Active Defect

The current generated panel B still has the wrong number and/or placement of 3D
grid lines compared with the reference. The details keep drifting because the
3D grid is still partially inferred by loose visual tuning instead of being
source-calibrated and encoded as measurable scene geometry.

Do not continue by adjusting random projected segments. First count and map the
reference grid lines.

## Panel B Context

Panel B is a 356 x 514 static 3D state-space trajectory plot:

- Title: `Neural state-space trajectories (population activity)`
- Legend: left choice, right choice, time points
- Axes: `PC 1 (25%)`, `PC 2 (12%)`, `PC 3 (8%)`
- Tick values: `-2`, `0`, `2` on all axes
- Scene style: isometric/projected 3D box with faint dashed Cartesian grids on
  multiple planes, black box edges, blue/red trajectories, black time-point
  markers, and direct labels for Stim, Go, Outcome.

Current implementation uses an SVG renderer with semantic 3D projection:

- Projection type in JSON: `trilinearProjectedCube`
- Renderer functions in the HTML:
  - `project`
  - `projectTrilinearCube`
  - `renderPlaneFill`
  - `renderGeneratedGridPlane`
  - `renderAxes`
  - `axisTickPoint`
  - `resolveTickAgainstGeometry`
  - `protectedAxisSegments`

Current grid JSON:

```json
"generatedPlanes": [
  {"id": "floor-pc1-pc2", "fixed": {"pc3": -2}, "u": "pc1", "v": "pc2", "values": [-2, 0, 2]},
  {"id": "back-wall-pc1-pc3", "fixed": {"pc2": -2}, "u": "pc1", "v": "pc3", "values": [-2, 0, 2]},
  {"id": "side-wall-pc2-pc3", "fixed": {"pc1": 2}, "u": "pc2", "v": "pc3", "values": [-2, 0, 2]}
]
```

This is the likely source of the mismatch. The renderer currently generates
line families from one shared `values` array per plane. That is too weak for
source parity because the source may show different visible grid-line families,
interior-only guides, boundary suppression, or a different number of guides per
axis direction.

## Recommended Next Plan

1. Inspect the reference at native resolution.
   - Use `view_image` for
     `assets/reference/reference-02-decision-dynamics-B-reference.png`.
   - Use a fresh browser screenshot of the generated HTML at the same apparent
     panel size.

2. Make a grid inventory before editing.
   - For each visible plane, list the visible line families:
     - floor plane: PC1 x PC2
     - back wall: PC1 x PC3
     - side wall: PC2 x PC3
   - Count source-visible interior lines and boundary-adjacent lines separately.
   - Record whether a line is a box edge, a grid line, a tick guide, or a plane
     fill boundary. These must not be conflated.

3. Strengthen the JSON schema for 3D grids.
   - Replace the single shared `values` field with per-family fields, for
     example:

```json
{
  "id": "floor-pc1-pc2",
  "fixed": {"pc3": -2},
  "families": [
    {"axis": "pc1", "values": [-2, 0, 2], "includeBoundary": false},
    {"axis": "pc2", "values": [-2, 0, 2], "includeBoundary": false}
  ]
}
```

   - If the source shows only interior dashed lines, encode that explicitly.
   - If a plane needs source-calibrated projected endpoints, add optional
     `clipStart`/`clipEnd` or projected endpoint overrides per family, but keep
     the semantic 3D anchor.

4. Update `renderGeneratedGridPlane`.
   - Render each family independently.
   - Respect `includeBoundary`.
   - Never let a grid line double as a box edge.
   - Keep plane fills generated from the projected plane polygon, behind all
     grid lines.

5. Add a lightweight validation pass.
   - Count generated grid-line elements by `data-plane` and `data-family`.
   - Compare counts against the JSON inventory.
   - This will not prove visual parity, but it prevents accidental count drift.

6. Only after the count is correct, tune projection and style.
   - Dash pattern, opacity, and stroke width should be adjusted after the
     geometry count matches.
   - Tick labels and tick marks should be checked again after grid changes,
     because nearby collision geometry changes.

## Important Existing Contract Changes

The reconstruction contract was already updated in both locations:

- `skills/vectorize-figure/references/reconstruction-contract.md`
- `plugins/vectorize-figure/skills/vectorize-figure/references/reconstruction-contract.md`

Relevant contract guidance already added:

- Detect 3D scientific plots from visual cues.
- Prefer semantic 3D data rendered through explicit projection for static 3D
  publication plots.
- Use named 3D grid planes instead of arbitrary projected segment lists.
- Generate plane fills from the same projection.
- Treat axis spines and tick marks as protected geometry.
- Place 3D tick labels from projected tick anchors plus offsets, then use
  collision correction as a secondary step.
- Render visible tick marks when the source has visible tick labels/ticks.

If the 3D grid schema changes, update both contract copies again.

## Prior Work This Session

Already addressed in panel B:

- Moved from a loose 2D drawing to a semantic projected-cube model.
- Removed the accidental triangular base artifact.
- Added a coherent 3D frame with floor, back-wall, and side-wall concepts.
- Added light gray floor-plane shading.
- Added visible tick marks.
- Anchored tick labels to projected tick points before collision nudging.
- Added semantic collision helpers for axis spines/tick labels.

Still not good enough:

- Grid-line count and placement do not match the reference.
- Some tick-label placement may need another pass after grid correction.
- Font mismatch remains a known cross-panel issue.

## Useful Commands

Start or verify local preview server from repo root:

```bash
python3 -m http.server 8765
```

Open current preview:

```text
http://127.0.0.1:8765/outputs/reference-02-decision-dynamics-B-vectorize-figure/reference-02-decision-dynamics-B.html
```

Validate JSON:

```bash
python3 -m json.tool outputs/reference-02-decision-dynamics-B-vectorize-figure/reference-02-decision-dynamics-B.json
```

Check that generated HTML does not reuse the source raster as a rendered layer:

```bash
rg -n "drawImage|background-image|source.path|reference.src" outputs/reference-02-decision-dynamics-B-vectorize-figure
```

## GitHub Issues

Existing issues created during this session:

- Font fidelity issue:
  `https://github.com/alexbw/vectorize-figure/issues/1`
- Collision-aware placement issue:
  `https://github.com/alexbw/vectorize-figure/issues/2`

## Working Tree Note

The working tree contains untracked reference images and generated outputs. Do
not clean, reset, or revert them. The last explicit checkpoint commit was:

```text
edd0539 Checkpoint vectorize-figure reconstructions
```
