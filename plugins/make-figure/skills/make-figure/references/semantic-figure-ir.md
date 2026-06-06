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
  `axis`/`value` metadata.
- Axis titles anchor to an axis, tick-label band, or measured source anchor;
  they are not independent guessed text.
- Event-aligned ticks, event lines, brackets, and annotations share a named
  event anchor or explicit measured visual anchor.
- Grid lines belong to named grid planes and families; grid lines must not be
  confused with solid box edges.
- Legends reference real series, marker classes, or mark groups.
- Colorbars reference a color scale and own their ticks and title.
- Table cell text, row rules, separators, and highlights remain separate
  objects when their visual styles differ.
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

Do this before visual tuning. If a generated object looks wrong, first ask which
relationship or transform is missing before changing pixels.

