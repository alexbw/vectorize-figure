# Semantic Figure IR

Use this document with `reconstruction-contract.md`. The reconstruction output
is a semantic figure intermediate representation, not a collection of detected
bounding boxes.

## Core Model

A scientific figure reconstruction is a typed scene graph:

```text
source evidence
  -> semantic figure objects
  -> named coordinate systems and transforms
  -> derived layout objects
  -> renderable marks and text
  -> validation constraints
```

Bounding boxes, OCR text, detected line segments, and color samples are source
evidence. They help infer the graph, but they are not the graph itself.

Semantic IR fields must have coverage. A non-provenance field should affect
rendering, survive into DOM/debug metadata, be validated against geometry or
relationships, or be explicitly marked as deprecated/ignored with a reason in
`schemas/ir-field-coverage.json`. Provenance-only notes belong under
`source`, `provenance`, `notes`, `confidence`, or `sourceEvidence`.

## Common Object Fields

Any semantic object may use these fields:

```json
{
  "id": "panel-a-x-tick-0",
  "type": "axisTick",
  "parent": "panel-a-x-axis",
  "children": ["panel-a-x-tick-0-mark", "panel-a-x-tick-0-label"],
  "usesTransform": "panel-a.xy",
  "anchorTo": "panel-a-x-axis",
  "derivesFrom": "panel-a.x.ticks[0]",
  "sourceEvidence": ["bbox-17", "line-04"],
  "provenance": {"confidence": "medium", "note": "Tick position measured from source."}
}
```

Prefer stable ids and explicit relationships over free-floating pixel objects.
When an object needs source-calibrated coordinates, keep those coordinates on
the semantic object as measured anchors instead of detaching the rendered mark
or text.

## Top-Level IR Concepts

- `sourceEvidence`: source bboxes, OCR snippets, measured line segments, color
  samples, and notes. These are evidence records, not render instructions.
- `coordinateSystems`: named transforms such as Cartesian data scales,
  categorical scales, event anchors, color scales, image/matrix ranges, and
  projected 3D scenes.
- `layoutObjects`: axes, tick-label bands, legends, colorbars, tables, insets,
  panel titles, scale bars, and other objects that reserve space or anchor text.
- `data`: exact data, approximate data, or generation recipes.
- `marks`: visual encodings derived from data or layout objects.
- `annotations`: labels, arrows, brackets, callouts, and event labels anchored
  to data points, marks, or layout objects.
- `constraints`: relationship and layout invariants that must survive rendering.
- `rendering`: renderer hints, layer order, and style tokens.
- `validation`: renderer- or harness-readable checks and expected counts.
- `provenance`: object-level confidence and unresolved inferences.

Panel-specific schemas may organize these concepts differently, but they should
preserve the same relationships.

## Required Relationship Invariants

Renderers and validation scripts should enforce these when the source shows the
corresponding objects:

- Labeled ticks render one tick mark and one tick label with matching
  `axis`/`value` metadata. The tick mark stores the source-calibrated axis
  coordinate separately from any label-only offset used for readability.
- Axis titles anchor to an axis, tick-label band, or measured source anchor;
  they are not independent guessed text.
- Event-aligned ticks, event lines, brackets, and annotations share a named
  event anchor or explicit measured visual anchor.
- Grid lines belong to named grid planes and families; grid lines must not be
  confused with solid box edges.
- Legends reference real series, marker classes, or mark groups.
- Colorbars reference a color scale and own their ticks and title. The IR must preserve tick side, tick mark direction, title anchor, and label anchor instead of leaving those to renderer defaults.
- Table cell text, row rules, separators, and highlights remain separate
  objects when their visual styles differ.
- Protected text nodes reserve layout space and must not overlap each other:
  panel labels, titles, axis titles, tick labels, colorbar labels, legend
  labels, table headers, table cells, phase labels, and region labels.
- Protected text nodes must also avoid declared exclusion zones for plot boxes,
  colorbars, orientation keys, legends, helper strips, and reserved regions
  unless a source-faithful exception is recorded in provenance.
- Adjacent small multiples own separate tick-label bands. A tick label at the
  right edge of one plot must not collide with the left-edge tick label of the
  next plot; use explicit gutters, label fitting, or source-calibrated anchors.
- Plot frames own all visible boundary strokes. Raster-strip panels must encode
  left/right/top/bottom rules separately when the source shows them, and tick
  marks must state whether they point inward or outward.
- Raster/event ticks and generated strip marks must identify an owner box and
  either clip to that box or validate that every endpoint stays inside it.
- Colored side row-block strips and phase/region bands are semantic layout
  objects with orientation, segment boundaries, colors, separators, borders,
  labels, linked axes, and exclusion zones. A heatmap-adjacent row-block strip
  is not a generic colorbar and must not be collapsed into a two-color
  rectangle when the source shows separator or edge components. Do not add an
  x-axis or y-axis colored strip unless the source visibly contains it.
- Data boxes, side strips, strip separators/borders, axis lines, tick marks,
  tick-label bands, and axis titles are separate layout objects. Offset axes
  must use explicit axis line geometry; renderers must not blindly derive axis
  spines from the heatmap `dataBbox` when the source shows a gap or side strip.
  If a gap is intentionally modeled, add `offsetFromDataBbox` with the source
  edge and pixel distance; an offset declaration whose line still equals the
  data box edge is invalid.
- Heatmap plot arrays that use `plotGroups` still need explicit axis objects.
  A bottom x-axis line must be encoded as `axes.xAxis.line` with a stable id
  and tick-label band; it must not be implied by a plot rectangle or the
  heatmap `dataBbox` bottom edge.
- Side row-block strips may include `components[]` in addition to semantic
  `segments[]` when visible parts need countable rendering, such as a dark
  edge, teal/cyan block, light separator, and gold block. Validators should
  compare rendered component nodes with `expectedComponentCount`.
- If a side strip, helper strip, axis origin tick, or plot frame visually
  shares an edge or origin, encode that as `sharedLayoutFrame`, `alignments`,
  or axis `originAlignment`. Treat the relationship as important unless the
  source gives evidence it is accidental. Renderers must preserve those
  relationships in DOM metadata and validators must check the declared deltas.
- Every protected text node has a stable `id`, role, and semantic `anchorTo`
  target such as an axis, tick-label band, side strip, legend row, colorbar,
  plot box, or table cell. Protected text includes panel labels, titles, tick
  labels, axis labels, colorbar labels, legend labels, phase/region labels, and
  table text.
- Collision repair may move only label anchors, label offsets, or reserved
  layout bands. It must not move tick marks, data marks, heatmap boxes, or
  source-calibrated geometry.
- Polar angle labels anchor to a polar plot and store an `angle`,
  `radialOffsetPx`, `anchor`, and optional source-calibrated label point. They
  are not free-floating page text.
- Annotations anchor to data coordinates, generated marks, or layout objects
  unless they are explicitly page-positioned.
- Generated visuals never reuse the source raster as a generated layer.

## Relationship Inventory Step

Before writing the final JSON for a nontrivial panel, produce a short inventory:

- plot type and renderer strategy
- coordinate systems and named anchors
- layout objects and their children
- data-driven marks and their series/group ownership
- annotations and what each one anchors to
- source-calibrated overrides and why the transform alone is insufficient
- validation constraints that should be checked in the rendered DOM
- any new semantic IR field and whether it is rendered, preserved, validated,
  provenance-only, deprecated, or intentionally ignored

Do this before visual tuning. If a generated object looks wrong, first ask which
relationship or transform is missing before changing pixels.
