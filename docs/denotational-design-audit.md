# Denotational Design Audit

Date: 2026-06-08

## Scope

This audit is about the mathematical meaning of the project artifacts, not
about immediate visual tuning. The current outputs are good and should be
treated as protected baselines. Any future change that changes rendered output
needs a concrete reason, existing validation, and visual inspection against the
project criteria.

No generated output files were changed for this audit.

## Desired Denotation

The project should be able to state the meaning of a reconstructed figure before
talking about SVG, DOM, or canvas. A useful denotational model is:

```text
source evidence -> figure model -> rendered surface
```

Where:

```text
figure model =
  data
  + coordinate systems
  + layout objects
  + marks
  + guides
  + annotations
  + constraints
  + provenance
```

The renderer should be a function of that model:

```text
render : FigureModel -> GeneratedSurface
```

The important property is substitution. If data, domains, ticks, plot size, or
layout boxes change, dependent visual objects should move or recompute because
their meaning is defined that way, not because a second set of coordinates was
manually patched.

## Ownership And Dependencies

The model should distinguish layout ownership from semantic dependency.

Layout ownership should usually form a tree:

```text
Figure
  Canvas
    Panel
      Plot
        Axis
          Tick
            Tick mark
            Tick label
        Mark layer
        Annotation layer
      Legend
      Colorbar
```

Every rendered object should have exactly one primary layout owner. That owner
determines coordinate frame, clipping, lifecycle, and default layout behavior.
This prevents ambiguous questions such as which object moves, deletes, clips,
or resizes a child.

Dependencies should form a DAG, not a tree. A visible object can depend on
several semantic objects:

```text
data -> domain -> scale -> marks
data -> domain -> tick strategy -> ticks -> tick labels
plotBox -> scale range -> marks, ticks, gridlines
series encoding -> legend entry
color scale -> heatmap and colorbar
panel bbox -> plot boxes, legends, colorbars
```

This gives the project a clean rule:

```text
one primary layout owner, many explicit dependencies
```

For example, a legend entry is owned by a legend row but references a series
encoding. A shared colorbar is owned by a panel or figure layout object but
references a color scale used by several plots. A statistical bracket is owned
by a plot or annotation layer but can anchor to two bars or categories.

Page coordinates should normally stop at the panel boundary. Inside a panel,
objects should be defined in panel-local, plot-local, axis-local, or
layout-object-local terms. Absolute page `x`/`y` values may still exist as
source-calibrated resolved positions, but they should not be the only statement
of meaning for a protected object.

## Existing Design Strengths

The repository already states the right target. `README.md` says to use a
semantic JSON spec as source of truth, render from DOM/SVG/canvas, and infer
chart grammar rather than text boxes. The skill contract is stronger: it calls
for a semantic relationship inventory before rendering, with coordinate
systems, layout objects, anchors, constraints, and provenance.

The reference IR docs are especially aligned with denotational design:

- `sourceEvidence` is evidence, not the graph.
- `coordinateSystems` name transforms and scales.
- `layoutObjects` own axes, legends, colorbars, tick bands, and other spatial
  structure.
- `marks` derive from data or recipes.
- `annotations` anchor to data, marks, or layout objects.
- `constraints` define relationships that must survive rendering.

The outputs also already contain substantial semantic structure:

- all 70 active specs have `schema`, `id`, `source`, `canvas`, `typography`,
  and `panels`
- 39 active specs define `coordinateSystems`
- 40 active specs use at least one `usesTransform`
- 57 active specs include `validation`
- 62 active specs include object-level or top-level `provenance`
- dense marks are usually generated from recipes or arrays rather than source
  pixels
- existing validators strongly protect against source-raster reuse

This is a strong base. The main issue is not that the project is pixel soup.
The issue is that the mathematical meaning is still partly implicit and partly
duplicated across JSON fields and renderer conventions.

## Main Finding

The current system has a good intended IR and good rendered output, but many
active specs are still closer to "semantic JSON with source-calibrated pixels"
than to a clean typed scene graph.

That is acceptable for visual reconstruction. It becomes limiting for data
mutation, resizing, interaction, and automatic layout because some visible
objects do not yet have explicit dependency paths back to data, scales, layout
objects, or anchors.

## Field Classification

Current fields fall into four denotational classes.

### Primitive Model Fields

These are legitimate inputs to the figure model:

- source crop dimensions
- canvas size
- panel bounding boxes
- measured plot/data boxes
- approximate data arrays
- data generation recipes
- color palettes
- typography defaults
- source-calibrated text boxes
- provenance and confidence notes

Pixel values are not inherently bad here. A measured plot box from the raster is
a valid primitive layout measurement.

### Derived Model Fields

These should be computed from primitives where possible:

- axis spines derived from plot or axis boxes
- tick mark positions derived from axis scale and tick value
- gridline positions derived from scales
- colorbar tick positions derived from color scale
- mark paths derived from data and coordinate systems
- label bands derived from axis/tick geometry and text metrics
- legend entries derived from series encodings

Many outputs already do this for marks and tick marks.

### Renderer Hints

These influence how the model is drawn but should not carry hidden meaning:

- `renderer: "svg"` or `"canvas"`
- layer ordering
- stroke widths
- opacity
- font family and local fitting mode
- interpolation mode

### Source Evidence

These are facts used to infer the model:

- OCR text boxes
- source line segment measurements
- color samples
- visual notes about approximate reconstruction

The reference IR says these should not become detached render instructions.
This distinction is currently underused.

## Quantitative Observations

An active-output scan found:

```text
active specs: 70

top-level fields:
  coordinateSystems: 39 specs
  layoutObjects: 10 specs
  validation: 57 specs
  provenance: 9 top-level specs

relationship fields:
  usesTransform: 138 objects in 40 files
  anchorTo: 27 objects in 13 files
  parent: 0 objects
  derivesFrom: 0 objects
  sourceEvidence: 4 objects in 1 file
  ownerBox: 0 objects
  exclusionZone: 2 objects in 2 files

selected shape patterns:
  text objects with absolute x/y and no anchorTo: 565 objects in 66 files
  axis line objects with explicit x1/y1/x2/y2: 63 objects in 31 files
  colorbar-like tick objects missing side/direction/orientation: 19 objects
  semantic marks without usesTransform: 37 objects in 15 files
```

These numbers should not be read as failures. They show where the intended IR
has not yet been made explicit enough for robust mutation and resizing.

## Risk Areas

### 1. Axis Geometry Duplicates Plot Geometry

Several specs define both `dataBbox` and axis line endpoints. That is sometimes
needed when the source has visible axis offsets, but it can also duplicate the
same fact.

Good denotation:

```text
xAxis = bottom edge of axisBox, with tick marks from x scale
```

Weaker denotation:

```text
xAxis = {x1, y1, x2, y2}, while ticks are computed elsewhere
```

Risk: resizing a plot box changes marks and ticks, but an explicit axis line
can remain frozen unless the renderer knows how to recompute it.

Recommendation: keep explicit axis line measurements, but classify them:

- `derivedFrom: "plot.dataBbox.bottom"` for normal axes
- `sourceCalibrated: true` plus `anchorTo` for visibly offset axes
- separate `axisBox` or `axisAnchor` where the source has a meaningful gap

Do not remove existing endpoints until a renderer proves it can preserve visual
output.

### 2. Text Is Often Page-Positioned Rather Than Anchored

>> ABW note: this is a problem. Text shoudl always be anchored, only the entire panel itself is page positioned.

Most protected text objects still use absolute `x`/`y`. This is visually useful
and often source-faithful, but it does not always say what the text means.

Examples:

- axis labels should anchor to axes or tick-label bands
- colorbar labels should anchor to colorbars
- annotations should anchor to data points, events, marks, or layout objects
- legend labels should anchor to legend rows, which reference series

Risk: changing domain, data extent, font size, or plot box size does not define
where the label should go.

Recommendation: preserve the current `x`/`y` as source-calibrated resolved
positions, then add relationship fields without changing render output:

```json
{
  "id": "x-axis-label",
  "text": "Time (s)",
  "x": 178,
  "y": 432,
  "anchorTo": "xAxis.tickLabelBand",
  "targetPoint": "bottom-center",
  "anchorPoint": "top-center",
  "sourceCalibrated": true
}
```

Renderers can continue using `x`/`y` until a safe anchor resolver exists.

### 3. Coordinate Systems Are Present But Not Always Canonical

Some specs have top-level `coordinateSystems`; others define domains and boxes
inside plots. Both can work, but the meaning is less composable when every
renderer has to rediscover local conventions.

Risk: future interactivity or mutation code needs plot-specific special cases.

Recommendation: normalize without rewriting visuals:

- every plot-like object gets a stable transform id
- every mark references a transform or a layout owner
- plot-local domains may remain, but should be mirrored or addressable as a
  named transform
- renderer DOM should expose `data-transform-id` where practical

### 4. Colorbars Are Under-Specified

The contract says colorbars should encode orientation, tick side, tick
direction, label anchor, title anchor, and color scale. The scan found many
colorbar-like objects with ticks but without side/direction/orientation fields.

Risk: renderer defaults become part of the mathematical meaning. A different
renderer can place ticks on the wrong side while still satisfying the JSON.

Recommendation: add non-rendering metadata first:

```json
{
  "orientation": "vertical",
  "tickSide": "right",
  "tickDirection": "outward",
  "labelAnchor": "start",
  "titleAnchor": "top-left"
}
```

Only change rendering after visual comparison.

### 5. Bounded Dense Marks Lack Owner-Box Semantics

Raster ticks, heatmap cells, dense dots, and generated strip marks are often
visually bounded by a plot or strip. Renderers frequently clip in code, but the
spec rarely says `ownerBox` or `clipToOwner`.

Risk: mutation of density, jitter, row spacing, or dimensions can let marks
escape their intended plot area.

Recommendation: add explicit ownership to dense marks:

```json
{
  "id": "event-raster",
  "type": "raster",
  "ownerBox": "panel-c.rasterBox",
  "clipToOwner": true
}
```

Then validate rendered endpoints or clip paths.

### 6. Full-Composite Renderers Are More Procedural

The full-figure HTML outputs are compact and high-quality, but some renderer
logic directly embeds formulas, fixed offsets, and per-panel drawing branches.
That is good for producing the current gallery; it is weaker as a reusable
denotation.

Risk: full composites are harder to mutate than cropped panels because the
meaning lives partly in JavaScript branches.

Recommendation: do not rewrite them wholesale. Instead, treat full-composite
renderers as acceptance targets while evolving cropped-panel renderers and IR
first. Migrate one full composite only after the smaller patterns are stable.

## Proposed Mathematical Core

A cleaner model can be introduced as a v2-compatible discipline without
breaking v1 output.

### Source Evidence

```text
Evidence = bbox | textBox | lineSegment | colorSample | sourceNote
```

Evidence may support a model object, but it is not rendered directly unless the
object says it is a source-calibrated anchor.

### Coordinate Systems

```text
CoordinateSystem =
  PagePixels
  | CartesianScale(xDomain, yDomain, dataBox)
  | CategoryScale(categories, range)
  | EventAnchor(value, transform)
  | ColorScale(domain, palette)
  | Projection3D(camera, domains)
```

### Layout Objects

```text
LayoutObject =
  Panel
  | PlotBox
  | Axis
  | TickLabelBand
  | Legend
  | Colorbar
  | Table
  | ScaleBar
  | Inset
  | ExclusionZone
```

Layout objects own visual space and define anchors.

### Marks

```text
Mark = DataBinding + VisualEncoding + Transform
```

A mark should be impossible to render without knowing its transform or layout
owner.

### Guides

```text
Guide = Axis | Tick | GridLine | ColorbarTick | LegendEntry
```

Guides are derived from scales and layout objects. They are not independent
page decorations.

### Annotations

```text
Annotation = Text/Line/Bracket/Arrow + Anchor
Anchor = DataPoint | ScaleValue | Event | Mark | LayoutObject | PagePosition
```

`PagePosition` should be explicit, not the accidental default.

### Constraints

```text
Constraint =
  tick mark and label share axis/value
  | protected text avoids exclusion zones
  | dense marks stay inside owner box
  | legend entry references real series
  | colorbar references real color scale
  | source raster is not a generated layer
```

## Compatibility Strategy

Do not replace the current output pipeline in one step. Add meaning alongside
existing fields, and only later teach renderers to prefer that meaning.

Recommended migration order:

1. Add relationship metadata that renderers ignore.
2. Add validators for relationship metadata.
3. Add non-output-changing DOM attributes from already-known relationships.
4. Add mutation probes that render to temporary artifacts only.
5. Refactor one small renderer pattern to resolve anchors from layout objects.
6. Compare screenshots and visually inspect before accepting.
7. Repeat for axes, labels, colorbars, dense marks, and full composites.

## Validation Additions

These checks can be added without changing output.

### Spec-Level Checks

- every mark has `usesTransform`, `anchorTo`, or `ownerBox`
- every colorbar has orientation, tick side, tick direction, and color scale
- every annotation has `anchorTo`, `xValue`, `yValue`, `bbox`, or explicit
  `positioning: "page"`
- every axis label has `anchorTo` or `positioning: "page"`
- every tick with a label preserves `value`
- every source-calibrated override has provenance or source evidence

Initially these should warn, not fail, because current outputs predate the
stricter model.

### Rendered-DOM Checks

- tick mark and tick label expose matching `data-axis` and `data-value`
- rendered marks expose `data-mark-id` and either `data-transform-id`,
  `data-series`, or `data-owner-box`
- colorbar ticks expose color scale id and tick side
- dense mark groups expose clipping/owner metadata
- protected text exposes enough metadata for collision reporting

### Mutation Probes

Run these on temporary copies, not the primary output files:

- change a data maximum and check whether domain/ticks/marks update coherently
- widen a plot box and check whether axes, ticks, gridlines, marks, and labels
  remain attached
- change canvas size and check whether panel-local layout remains stable
- change color scale domain and check heatmap/colorbar consistency
- add/remove a category and check categorical axis/marks/labels
- move an event anchor and check event line, event label, and related marks

Mutation probes should not compare to the source raster. Their acceptance
criterion is relationship coherence. Source-fidelity regression remains a
separate acceptance gate for changes to canonical output.

## Visual Safety Gate

Any future PR that changes generated output should include:

1. existing workflow validation
2. before/after screenshots at native dimensions
3. visual inspection against source for layout, chart grammar, mark density,
   axis/tick alignment, label hierarchy, annotations, and no raster reuse
4. a short explanation of why any visual difference is worth the semantic gain

If the change only adds metadata or validators and does not alter rendering,
visual inspection is not needed beyond confirming no output files changed.

## Recommended Next Work

Start with warnings and reports, not renderer rewrites.

1. Add a script such as `scripts/audit_figure_ir_relationships.py`.
2. Have it produce a JSON or Markdown report for active outputs.
3. Classify objects as `primitive`, `derived`, `anchored`, `rendererHint`,
   `sourceEvidence`, or `unclassified`.
4. Add warning-only checks for the validation additions above.
5. Pick one strong cropped panel and add ignored relationship metadata until it
   has a clean graph without changing pixels.
6. Only then refactor that panel renderer to resolve one relation, such as axis
   labels from axis/tick-label bands.

The first implementation target should probably be a cropped panel, not a full
composite. Cropped panels are easier to inspect visually, and the project
already has strong gallery validation for them.

## Bottom Line

The project is already on the right design path. The main denotational gap is
that current JSON often records enough information to reproduce a figure, but
not always enough information to state why every visible object belongs where
it is.

The next layer of maturity is to make that "why" explicit while preserving the
current good output.
