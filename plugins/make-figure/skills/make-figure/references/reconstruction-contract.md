# Reconstruction Contract

Use this contract when converting a raster scientific figure into configurable HTML and JSON.

Read `semantic-figure-ir.md` alongside this contract. The JSON may be
panel-specific, but it must preserve semantic relationships between data,
transforms, layout objects, marks, labels, and validation constraints.

## JSON Shape

Minimum top-level fields:

```json
{
  "schema": "scientific_figure_reconstruction.v1",
  "id": "figure-id",
  "source": {
    "path": "./source.png",
    "usage": "QA-only; not used by generated candidate.",
    "notes": "What was inferred visually."
  },
  "canvas": {
    "width": 800,
    "height": 600,
    "background": "#ffffff"
  },
  "typography": {
    "fontFamily": "Arial, Helvetica, sans-serif",
    "defaultSize": 12,
    "color": "#111111",
    "fontImports": [
      "https://fonts.googleapis.com/css2?family=Arimo:wght@400;700&display=swap"
    ],
    "fontFaces": [
      {"family": "FigureSans", "weight": 400, "src": "./fonts/FigureSans-Regular.woff2"},
      {"family": "FigureSans", "weight": 700, "src": "./fonts/FigureSans-Bold.woff2"}
    ],
    "fontCandidates": ["Arial", "Helvetica", "Arimo", "Source Sans 3", "Roboto", "Noto Sans"],
    "calibration": {
      "fontStretch": "normal",
      "letterSpacing": 0,
      "lineHeight": 1.08,
      "notes": "Use measured source text boxes to tune font family, stretch, size, and line height."
    }
  },
  "panels": [],
  "confidence": []
}
```

`fontImports` is for lightweight browser-based experimentation with external
CSS font providers such as Google Fonts. `fontFaces` is for reproducible local
or adjacent font files when a typeface has been selected. Do not introduce a
build system only to test fonts; use browser-native font loading and SVG text
measurement first.

## Panel Shape

Represent each subpanel explicitly. For a single cropped panel, use one item in `panels`.

```json
{
  "id": "panel-a",
  "label": {"text": "A", "x": 16, "y": 20, "fontSize": 24, "fontWeight": 700},
  "title": {"text": "Panel title", "x": 56, "y": 24, "fontSize": 16, "fontWeight": 700},
  "bbox": {"x": 0, "y": 0, "width": 400, "height": 300},
  "plot": {
    "dataBbox": {"x": 64, "y": 48, "width": 300, "height": 210},
    "axes": {
      "xAxis": {"id": "panel-a-x-axis", "line": {"x1": 64, "y1": 258, "x2": 364, "y2": 258}, "tickLength": 6},
      "yAxis": {"id": "panel-a-y-axis", "line": {"x1": 64, "y1": 48, "x2": 64, "y2": 258}, "tickLength": 6}
    },
    "x": {
      "scale": "linear",
      "domain": [0, 10],
      "ticks": [{"value": 0, "label": "0"}, {"value": 5, "label": "5"}, {"value": 10, "label": "10"}],
      "label": {"text": "Time (s)"}
    },
    "y": {
      "scale": "linear",
      "domain": [0, 1],
      "ticks": [{"value": 0, "label": "0"}, {"value": 0.5, "label": "0.5"}, {"value": 1, "label": "1"}],
      "label": {"text": "Response"}
    }
  },
  "marks": [],
  "annotations": [],
  "provenance": []
}
```

## Mark Types

Use semantic mark objects. Add fields as needed, but keep the meaning explicit.

- `lineSeries`: data points plus stroke, width, optional uncertainty band.
- `scatter`: points, marker shape, size, fill, stroke, opacity.
- `bar`: categorical or numeric bars with baseline, fill, stroke.
- `heatmap`: matrix, color scale, bounds, interpolation flag.
- `raster`: event times by row or a generation recipe with seed and density.
- `violin`: category, outline path or generated KDE recipe, median/quantile marks.
- `path`: editable SVG path data for contours, arrows, outlines, or schematic curves.
- `rect`, `circle`, `ellipse`, `text`, `bracket`, `arrow`: annotations and schematics.
- `imageRecipe`: generated texture or synthetic field; never point this at the source raster.

## Coordinate Systems

Define named transforms before rendering marks:

- `plot.dataBbox` maps data to pixels.
- For charts where the visual data rectangle is offset from axes, split
  `dataBbox` from `axisBbox` or explicit axis anchors such as `yAxisX` and
  `xAxisY`. Do not force source axis offsets into the data transform.
- `x.domain` and `y.domain` map quantitative axes.
- `categories` map categorical positions.
- `eventAnchor` maps event-aligned plots.
- `colorScale.domain` maps heatmaps and colorbars.

Avoid mixing hard-coded pixel marks with data-space marks unless the mark is truly an annotation. Ticks, event lines, and data marks should share the same transform.

### 3D Scientific Plots

Recognize 3D plots from visual cues such as three nonparallel labeled axes,
isometric or perspective box frames, oblique grid planes, tick labels attached
to multiple axis directions, and data paths or markers that overlap within a
projected volume. Do not require the user to identify a panel as 3D.

For static publication-style 3D plots made of axes, grid lines, trajectories,
markers, and labels, prefer semantic 3D data rendered into SVG through an
explicit projection function. Reserve WebGL or Three.js for genuinely complex
surfaces, dense point clouds, lighting, meshes, or interactive rotation.

Represent 3D scenes with explicit camera or projection metadata:

```json
{
  "scene": {
    "projection": {
      "type": "orthographicBasis",
      "corner": {"x": 58, "y": 327},
      "domainCorner": {"pc1": -2, "pc2": -2, "pc3": -2},
      "basis": {
        "pc1": {"x": 258, "y": 30},
        "pc2": {"x": 145, "y": 90},
        "pc3": {"x": 0, "y": -184}
      }
    },
    "domains": {"pc1": [-2, 2], "pc2": [-2, 2], "pc3": [-2, 2]},
    "trajectories": [{"points": [[-1.5, -1.6, -0.3], [0.7, -1.1, 1.8]]}]
  }
}
```

`fontImports` is for lightweight browser-based experimentation with external
CSS font providers such as Google Fonts. `fontFaces` is for reproducible local
or adjacent font files when a typeface has been selected. Do not introduce a
build system only to test fonts; use browser-native font loading and SVG text
measurement first.

Axes, grid planes, trajectories, markers, and annotations must use the same
3D-to-2D projection. Depth-sort generated marks when overlap matters: back grid
and box edges first, faint trial clouds, mean trajectories, timepoint markers,
then text labels. Labels should anchor to projected 3D points or axis objects
and then participate in the normal text-collision pass.

When using source-calibrated projected grid segments, avoid segments that
duplicate solid box edges or accidentally close into polygons. Grid lines should
read as independent faint plane guides unless the source explicitly shows a
closed projected face.

Prefer named 3D grid planes over a flat list of projected line segments. For
example, encode separate `floor`, `backWall`, and `sideWall` grid groups so each
axis pair has its own Cartesian grid. Inventory the source grid before tuning:
for every plane, count visible interior guides separately from boundary-aligned
guides that are merged with or hidden under box edges. Encode grid lines as
per-family values, such as independent `pc1`, `pc2`, and `pc3` guide families,
instead of one shared plane-level value list. Each family should state whether
domain-boundary values are included, and generated SVG lines should expose
stable plane/family attributes so count validation can catch drift. A 3D
state-space panel with PC1, PC2, and PC3 axes should not collapse into one wall
plus a triangular base.

If the source uses faint face shading, encode plane fills separately from grid
lines and generate the fill polygon from the same 3D projection. Do not bake the
shading into arbitrary background shapes. Tick labels in 3D plots are layout
text: allow source-calibrated text positions or offsets from projected ticks so
labels do not collide with each other, axis titles, or spines.

3D tick labels should be placed by semantic layout rules, not by one-shot
coordinates alone. Treat axis spines and tick marks as protected geometry with
padded hit zones. Treat faint grid lines and trajectory clouds as non-protected
unless the source clearly reserves label space around them. Tick labels may use
source-calibrated initial positions, but renderers should measure the final text
box and apply a constrained outward nudge if it intersects protected axis
geometry:

```json
{
  "axis": {
    "id": "pc1",
    "tickLabelPlacement": {
      "avoid": ["axis-spine"],
      "minGap": 5,
      "nudge": {"x": 8, "y": 7},
      "maxSteps": 6
    }
  }
}
```

3D axes with visible tick labels should also render visible tick marks unless
the source suppresses them. Store tick geometry as a projected tick anchor, a
short `markVector`, and a label offset or outward normal. The label should be
placed from the tick mark first; collision correction is a secondary adjustment,
not the primary placement mechanism.

When a source-fitted frame or projection still does not reproduce the source's
tick text positions, keep the numeric tick `value` semantic but add separate
source-calibrated `markAnchor` and/or `labelAnchor` fields. Do not force tick
labels through one shared offset vector if the source clearly uses
axis-specific manual or backend-specific layout. Locked label anchors should be
recorded as measured source layout, not as inferred data geometry.

Treat each tick as a paired object. If the source has both tick labels and tick
marks, every encoded tick with a label must render a corresponding mark, and
every rendered mark should be associated with the same axis/value as the label.
Renderers should expose stable axis/value attributes for both nodes and validate
that labeled ticks have one-to-one mark/label pairs. A source-calibrated label
must not leave its mark behind on an older inferred projection anchor.

Use semantic collision groups and priorities rather than collision-detecting
all visible marks. Fixed structural geometry should remain fixed; layout text
can move within source-faithful limits.

### Data Boxes Versus Axis Boxes

Raster scientific figures often place axes, ticks, or spines a few pixels away
from the data region. Represent that explicitly instead of treating one
`bbox` as every layout contract:

```json
{
  "id": "heatmap-a",
  "type": "heatmap",
  "dataBbox": {"x": 70, "y": 91, "width": 170, "height": 354},
  "axes": {
    "xAxis": {
      "id": "heatmap-a-x-axis",
      "line": {"x1": 70, "y1": 451, "x2": 240, "y2": 451},
      "tickLength": 7
    },
    "yAxis": {
      "id": "heatmap-a-y-axis",
      "line": {"x1": 64, "y1": 91, "x2": 64, "y2": 445},
      "tickLength": 6
    },
    "dataBorder": ["top", "right", "bottom"]
  },
  "x": {"domain": [0, 210]},
  "y": {"domain": [1, 162]}
}
```

Use `dataBbox` for generated images, heatmaps, dense rasters, and marks. Use
axis line objects for spines and ticks. When the source shows a visible gap
between the data region and an axis spine, axis `line` endpoints must be offset
from the corresponding `dataBbox` edge; do not set them equal to the data edge
just because the transform uses that edge. When the source style leaves a gap
between x and y axes at the corner, encode that by giving `xAxis.line` and
`yAxis.line` independent endpoints that do not touch. This preserves editable
coordinate transforms while matching figures whose axes are visually offset
from the data.

### Relative Layout Anchors

Prefer relative anchors for labels attached to layout objects such as colorbars,
axes, scale bars, insets, and legends:

```json
{
  "xLabel": {
    "text": "X position (cm)",
    "anchorTo": "xAxis",
    "targetPoint": "bottom-center",
    "anchorPoint": "top-center",
    "dx": 0,
    "dy": 36,
    "baseline": "hanging"
  },
  "yLabel": {
    "text": "Y position (cm)",
    "anchorTo": "yAxis",
    "targetPoint": "middle-left",
    "anchorPoint": "center",
    "dx": -50,
    "dy": 0,
    "rotation": -90,
    "anchor": "middle"
  },
  "colorbar": {
    "bbox": {"x": 443, "y": 250, "width": 19, "height": 189},
    "label": {
      "text": "Firing rate\n(z-scored)",
      "anchorTo": "colorbar",
      "targetPoint": "top-left",
      "anchorPoint": "top-left",
      "dx": -10,
      "dy": -12,
      "lineHeight": 1.05
    }
  }
}
```

Renderers must resolve these anchors from named layout objects such as
`xAxis`, `yAxis`, `colorbar`, `tickLabelBox`, or `legend`. The implementation
must apply both `targetPoint` on the target layout object and `anchorPoint` on
the resolved text block. For multiline labels, estimate or measure a block
height from `height` or `lineCount * fontSize * lineHeight` before applying
`anchorPoint`. Use absolute `x` and `y` only when the label is truly
page-positioned.

## Text Alignment

Do not place text with only top-left coordinates when alignment matters. Use:

- `anchor`: `start`, `middle`, or `end`
- `baseline`: `top`, `middle`, `alphabetic`, or `bottom`
- `rotation`: degrees
- `width` and `lineHeight` for multiline labels
- `fontFamily`, `fontStretch`, `letterSpacing`, and `targetWidth` when visual
  text matching requires calibration against the raster.
- Prefer local `targetWidth` plus `fit: "scaleX"` for a specific label over
  changing global typography for the whole figure.

Separate semantically distinct labels even when they are visually grouped.

## Typeface Matching

Do not solve raster typography mismatch by applying one condensed or alternate
font globally unless most source labels clearly use that face. Use a calibrated
candidate workflow:

1. Select representative source labels: panel letter, title, tick labels, axis
   titles, legends, colorbar labels, table labels, and compact multiline text.
2. Try likely scientific-paper sans faces first: Arial/Helvetica fallbacks,
   Arimo, Liberation Sans, TeX Gyre Heros/Nimbus-like alternatives, Source Sans
   3, Roboto, and Noto Sans.
3. Compare browser-measured generated SVG text boxes with measured source text
   boxes. Choose a panel-level default only when most labels improve.
4. Use local fitting fields for outlier labels instead of distorting the whole
   panel.

Text objects may include:

```json
{
  "id": "x-axis-title",
  "text": "Time from light onset (s)",
  "x": 291,
  "y": 482,
  "fontFamily": "Arimo",
  "fontSize": 16,
  "lineHeight": 1.05,
  "letterSpacing": 0,
  "targetWidth": 224,
  "targetHeight": 18,
  "fit": "scaleX",
  "fitTolerancePx": 0.75,
  "minScale": 0.65,
  "maxScale": 1.35,
  "sourceBox": {"x": 181, "y": 467, "width": 224, "height": 18}
}
```

Supported fitting modes:

- `scaleX`: horizontally scales the rendered text around its anchor point to
  match `targetWidth`.
- `textLength`: uses SVG `textLength`/`lengthAdjust` for browser-managed
  width fitting.
- `fontSize`: adjusts font size to match `targetHeight`; use sparingly because
  it changes hierarchy.

Renderers should wait for `document.fonts.ready`, measure text with
`getBBox()` or `getComputedTextLength()`, and expose a QA report of generated
versus `sourceBox` dimensions when source boxes are provided. Optional font
metric libraries such as `opentype.js` can help inspect candidate fonts, but
browser-measured SVG output is the source of truth for rendered HTML
reconstructions. The shared template exposes `window.figureTextQa` whenever
`sourceBox` fields are present, and `?fontQa=1` also scores
`typography.fontCandidates` in `window.figureFontQa`.

For source-box-driven text calibration, use `scripts/font-calibration/` as the
shared harness. It renders candidate text in the browser, compares masks against
source crops, writes calibrated text fields back to the spec, and emits
`baselineScore`, `score`, and `improvement` per label. Use the scores to catch
regressions, but use results-only overlays for acceptance. The target is a
clear visual improvement over the baseline reconstruction, not pixel identity
with the source raster.

## Text Collision Rules

Text overlap is a reconstruction failure for protected layout text. Axis
titles, tick labels, colorbar titles, colorbar tick labels, legend labels,
table headers, table cell labels, panel labels, phase labels, and region labels
must reserve space from each other with measured or estimated text boxes. Do
not rely on a single fixed `x`/`y` offset when a label is visually attached to
another text row.

Protected text must be measured in the rendered browser before finishing. For
SVG text, use `getBBox()` after fonts are ready; for DOM text, use
`getBoundingClientRect()`. Treat a collision with another protected text box,
an axis spine, a plot boundary, or a clipping rectangle as a failed render.
Generated HTML should expose a collision report such as
`window.figureLayoutQa.protectedTextCollisions`, and any nonempty collision
list must be fixed before the output is considered complete.

For axes with tick labels, model the axis title as anchored to a
`tickLabelBand` rather than directly to the axis line whenever the source places
the title below or beside tick labels:

```json
{
  "xAxis": {
    "line": {"x1": 64, "y1": 258, "x2": 364, "y2": 258},
    "tickLabels": {
      "fontSize": 12,
      "dy": 18,
      "minGap": 2,
      "collision": {"strategy": "fit-or-stagger", "minScale": 0.72}
    },
    "label": {
      "text": "Time from stimulus onset (ms)",
      "anchorTo": "tickLabelBand",
      "targetPoint": "bottom-center",
      "anchorPoint": "top-center",
      "dy": 7
    }
  }
}
```

Renderers should measure SVG/DOM text boxes with the browser when possible. If
adjacent tick labels overlap, first apply source-faithful local calibration such
as `targetWidth`, `textLength`, `fontStretch`, or a smaller tick-label font.
Only stagger, rotate, abbreviate, or suppress tick labels when the source uses
that convention or when fitting would distort text beyond the declared
`minScale`.

For schematic timelines, event axes, or task diagrams, do not assume that tick
positions are linearly spaced just because labels contain numeric values. If the
source visually compresses or expands intervals, preserve semantics with
`value`/`label` but encode source-derived visual anchors such as `x`, `y`, or
`anchorTo` for ticks, guides, brackets, and phase boundaries. Renderers should
prefer explicit visual anchors over numeric transforms for these schematic
objects, while retaining the numeric values for editability and provenance.

Table-like rows should separate shared row rules from individual cell
boundaries. If the source shows strong horizontal rules but weak or absent
vertical strokes, encode a row/band object with top and bottom rules plus
optional separators and highlighted cells. Do not force every cell into an
identical full-stroke rectangle.

For compact schematic phase tables or task timelines, model the visual rows
explicitly:

```json
{
  "phaseTable": {
    "bbox": {"x": 15, "y": 312, "width": 395, "height": 180},
    "columns": [
      {"id": "stim", "label": "Stim", "x": 94, "width": 74, "accent": "#3769b1"}
    ],
    "rows": [
      {"id": "header", "height": 36, "minTextGap": 4},
      {"id": "process", "height": 54, "minTextGap": 5},
      {"id": "behavior", "height": 58, "minTextGap": 5}
    ],
    "rules": {"top": true, "bottom": false, "columnGap": 3, "strokeWidth": 1}
  }
}
```

Renderers must measure multiline text inside every phase/table cell. If text
does not fit, first reduce the local font size within the declared hierarchy,
then wrap or increase row height if the source has room. Never accept clipped
or overlapping cell text.

### Tick Bands In Small Multiples

For arrays of heatmaps or small multiples, each plot has its own data box and
its own tick-label band. Adjacent tick labels are protected text even if they
belong to different plots. Labels such as `100` at the right edge of one plot
and `0` at the left edge of the next plot must not collide.

Encode enough layout to prevent this:

```json
{
  "smallMultiple": {
    "plotGap": 12,
    "xTickLabelBand": {"height": 20, "minNeighborGap": 3},
    "xTicks": [
      {"value": 0, "label": "0", "edgePolicy": "inside"},
      {"value": 100, "label": "100", "edgePolicy": "inside"}
    ]
  }
}
```

When edge tick labels collide, prefer a source-faithful inward anchor (`start`
for left edge, `end` for right edge), local text fitting, or a larger plot gap.
Do not simply nudge one label until it overlaps a different object. Do not move
the tick mark away from its source-calibrated coordinate to make room for text.

### Tick Coordinate Invariants

Every visible tick has two related but separate objects:

- the tick mark coordinate, derived from the source axis scale
- the tick label box, which may have an anchor or offset for legibility

Renderers must expose both relationships in the DOM:

```html
<line data-role="axis-tick-mark" data-axis="x" data-value="100" data-source-x="129">
<text data-role="tick-label" data-axis="x" data-value="100" data-label-offset-x="0">
```

Moving a label to avoid collision is allowed only if the tick mark remains at
the calibrated coordinate. Moving both the mark and the label together to make
room is a geometry error.

### Protected Exclusion Zones

Text collision checks must include more than text-vs-text intersections. Any
layout object that occupies protected visual space must declare an exclusion
box or path:

```json
{
  "id": "pc-orientation-key",
  "type": "orientationKey",
  "bbox": {"x": 394, "y": 275, "width": 70, "height": 56},
  "exclusionZone": {"paddingPx": 2}
}
```

Protected text must not intersect plot boxes, colorbars, orientation keys,
legend marks, helper strips, or explicitly reserved regions unless the source
visibly overlaps those elements. If an exception is source-faithful, record it
in provenance and tag the text or exclusion zone with the exception id.

### Colorbars

Colorbars are not generic rectangles with default ticks. Encode all of:

- `orientation`: vertical or horizontal
- `tickSide`: left, right, top, or bottom
- `tickDirection`: inward or outward relative to the bar
- `tickLength`
- `labelAnchor` and `titleAnchor`
- the color scale used by the corresponding data mark

Example:

```json
{
  "colorbar": {
    "id": "activity-colorbar",
    "orientation": "vertical",
    "bbox": {"x": 304, "y": 247, "width": 8, "height": 108},
    "tickSide": "right",
    "tickDirection": "outward",
    "ticks": [{"value": 0, "label": "0"}, {"value": 2, "label": "2"}]
  }
}
```

Before finishing, compare the generated tick side to the source. A colorbar
whose ticks or labels are on the wrong side fails validation even if the bar
colors are correct.

### Axis Truncation And Orientation Keys

Some source panels intentionally truncate an axis to leave room for an
orientation key, inset, legend, or annotation. Represent this as semantic axis
geometry, not as a missing tick:

```json
{
  "xAxis": {
    "visibleSegments": [
      {"from": -6, "to": 3.2}
    ],
    "ticks": [
      {"value": -6, "label": "-6", "showMark": true, "showLabel": true},
      {"value": 0, "label": "0", "showMark": true, "showLabel": true},
      {"value": 6, "label": "6", "showMark": true, "showLabel": true}
    ],
    "occluders": ["pc-orientation-key"]
  }
}
```

Do not delete tick labels merely because a visible axis segment is truncated.
If a source tick label is visible but its mark lies outside the shortened
segment, encode a source-calibrated tick mark or label anchor.

### Polar Labels

Polar angle labels are anchored labels, not arbitrary page text. Store the
angle, offset, anchor, and minimum gap:

```json
{
  "angleLabels": [
    {"value": 0, "label": "0°", "radialOffsetPx": 7, "minGapPx": 3, "anchor": "start"}
  ]
}
```

The label should be close enough to read as part of the polar plot but clearly
separated from the circle, curve, and preferred-direction marker. Excessive
offsets that detach the label from the plot are also failures.

### Raster Plot Boundaries And Ticks

Raster plots and strip panels must inventory visible boundary strokes. If the
source shows a left spine, encode and render it. If ticks are drawn inside the
plot bounds, store `tickDirection: "in"` and keep ticks inside the data or axis
box. Do not allow bottom ticks to extend below the boundary unless the source
does that.

Raster/event ticks, inward axis ticks, boxed-strip marks, and similar generated
line marks must have an owner box. A mark must either be clipped by a clip path
whose rectangle matches the owner box, or all of its endpoints must lie inside
that owner box:

```json
{
  "id": "ca1-event-42",
  "type": "rasterTick",
  "ownerBox": "ca1.box",
  "clipToOwner": true
}
```

Renderer QA should emit a mismatch if an un-clipped bounded mark extends
outside the owner box. This is especially important for sparse raster strips
where tick height, jitter, or row spacing can otherwise push strokes beyond
clearly drawn boundaries.

### Colored Side Strips And Region Bands

Colored strips adjacent to heatmaps are semantic axis/layout objects. Inventory
their orientation, segments, boundaries, colors, and relationship to the
corresponding axis before rendering. Do not add a strip to an axis that does
not visibly have one in the source. In particular, do not invent colored x-axis
bars to explain y-axis sorting strips or event/region colors. When text labels
and colored strips share an axis area, reserve separate bands so labels never
overlap the strip.

## Provenance And Confidence

Record uncertainty at the object level:

```json
{
  "target": "panel-a.marks.control-line",
  "confidence": "medium",
  "note": "Curve shape inferred visually; source data unavailable."
}
```

Prefer approximate data or a generation recipe over fake exact values. If a source image only implies a distribution, store recipe parameters and the random seed used by the renderer.

## HTML Requirements

- Render all generated visuals from the JSON spec.
- Keep the source raster out of generated layers.
- Put QA/reference source image behind a clearly labeled toggle or separate view.
- Provide stable selectors: `data-panel-id`, `data-mark-id`, `data-role`.
- Provide relationship selectors where applicable, such as `data-axis`,
  `data-value`, `data-plane`, `data-family`, `data-series-id`, and
  `data-anchor-to`.
- Emit `data-*-validation="ok"` or `data-*-validation="mismatch"` for renderer
  checks that can be evaluated in the browser, such as grid counts, protected
  text collisions, and tick mark/label pairing.
- Keep CSS local to the output file unless the user requests a bundled app.
- Avoid external dependencies unless the figure genuinely needs them.

## Validation

Run a local browser check when possible:

```bash
python3 -m http.server 8765
```

Then open the output at native dimensions, or capture a headless screenshot. Check for blank canvases, missing JSON loads, broken source paths, overlapped labels, and accidental source-raster reuse.

For existing generated outputs, use `scripts/validate_make_figure_outputs.py`
to capture baselines and check structural relationship invariants before and
after schema or renderer changes.
