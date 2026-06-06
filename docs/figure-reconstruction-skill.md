# Scientific Figure Reconstruction Skill

Working goal: turn raster scientific figure subpanels into editable, data-driven HTML reconstructions that are close enough visually to the source PNG while preserving software-editable structure.

This is a draft approach to refine by testing against many subpanel types. Do not treat it as final doctrine; treat it as the shared playbook for experiments.

## Core Hypothesis

The durable artifact should be a semantic figure specification, not a particular renderer.

The specification is a semantic figure IR: source detections become evidence for
a graph of panels, coordinate systems, layout objects, data, marks,
annotations, and validation constraints. Bounding boxes are not the final
architecture; they are measurements that help infer relationships.

Generated HTML reconstructions must not reuse source figure PNGs as visual layers. Source PNGs can be used for inspection, QA comparison, and visual judging, but the candidate HTML itself should be built from generated DOM/SVG/canvas marks and editable data/spec recipes. Do not embed source PNGs with `<img>`, CSS backgrounds, or canvas `drawImage`.

The renderer can be SVG, DOM, canvas, or hybrid. The source of truth should be a JSON sidecar that describes the figure in editable terms:

- panel size and coordinate systems
- plot type and subpanel role
- axes, scales, domains, ticks, labels, and transforms
- data series or approximate data generation recipes
- visual marks such as points, lines, bars, heatmaps, violins, contours, rasters, arrows, brackets, and annotations
- style tokens such as colors, font sizes, stroke widths, opacity, marker size, and dash patterns
- provenance and confidence for inferred pieces

The same spec should support multiple renderers and quality-assurance overlays.

Relationship correctness precedes pixel tuning. If a visible element drifts,
first identify whether it is missing a parent object, transform, anchor, or
validation constraint before adjusting its absolute coordinates.

## Renderer Strategy

Use the best rendering primitive per layer.

| Layer | Default | When to Switch |
|---|---|---|
| Text, labels, titles, legends | SVG or DOM | DOM if direct HTML editing is the priority |
| Axes, ticks, brackets, simple annotations | SVG | DOM is acceptable for simple line/text figures |
| Line plots, paths, outlines, contours | SVG | Canvas only for very dense or image-like geometry |
| Scatter points, low/medium count | SVG | Canvas for thousands of points or performance-sensitive views |
| Dense scatter/raster/event plots | Canvas + SVG axes | Use SVG only for sampled/editable subsets |
| Heatmaps and matrix images | Canvas + SVG axes/colorbars | Raster image layer is acceptable if raw matrix is unavailable |
| Violin/KDE distributions | SVG path by default | Canvas if generated from a dense field |
| Background source PNG | QA-only image layer | Do not make it part of the final editable figure |

For most scientific plots, the likely best output is hybrid:

- SVG/DOM for labels, axes, legends, annotations, and editable marks
- Canvas for high-density dot fields, rasters, heatmaps, and pixel-native layers
- JSON sidecar as the editable source of truth

## Workflow

1. Select one cropped subpanel and inspect it at native resolution.
2. Parse critical visual elements from the raw PNG, ignoring inherited OCR unless explicitly requested.
3. Classify the panel type, such as violin, line plot, heatmap, raster, schematic, scatter, bar, matrix, or mixed panel.
4. Create a manual or semi-automatic visual metadata file with bounding boxes and semantic roles.
5. Convert the metadata into a figure spec JSON sidecar.
6. Render an HTML reconstruction from the spec.
7. Compare the rendered output to the source PNG at native dimensions.
8. Ask the human visual judge to score quality and identify failure modes.
9. Refine the spec schema, renderer strategy, and parsing heuristics.
10. Repeat across diverse panel types before formalizing the skill.

## Required Outputs Per Test Panel

Each test panel should produce:

- `*-visual-elements.json`: bbox-level parsed elements with roles and notes
- `*-visual-elements-overlay.png`: QA overlay with numbered boxes
- `*.json`: editable figure spec sidecar
- `*.html`: rendered reconstruction
- optional `*-dom.html`, `*-svg.html`, or `*-hybrid.html` variants when renderer comparison is useful
- optional screenshot from headless browser at source PNG dimensions

## Figure Spec Requirements

The spec should separate semantic data from rendering mechanics.

Minimum top-level fields:

- `source`: source image path, metadata source, notes
- `canvas`: width, height, background
- `typography`: font family and default text style
- `panels` or `panel`: panel label/title metadata
- `plot`: plot region, axes, scales, ticks, grid/reference lines
- `marks`: visual marks, grouped by semantic series
- `annotations`: p-values, brackets, labels, arrows, callouts
- `rendering`: preferred renderer and layer hints
- `confidence`: low-confidence or unresolved inferences

Axis fields should support dynamic changes:

- explicit domain override
- inferred domain from data
- nice tick generation
- tick label formatting
- scale mapping from data coordinates to pixels
- editable label and style metadata

Data fields should support imperfect reconstruction:

- exact values when available
- approximate values if inferred visually
- generation recipe when the raster only implies a distribution
- raw matrix for heatmaps when known
- embedded small arrays or external file references for larger data

## QA Criteria

Judge each reconstruction on:

- visual similarity at source dimensions
- correct plot type and semantic structure
- editability of axes and labels
- editability of data or data recipe
- ability to dynamically update ticks/domains when data changes
- stable IDs/classes for LLM or programmatic edits
- appropriate renderer choice for density and complexity
- clear record of assumptions and uncertain inferred values

A reconstruction can pass even if the data is approximate, as long as the layout, semantics, and editability are good enough for downstream modification.

## Generalized Rules Learned So Far

These are the operational rules of the skill. They should be applied across panels, not only to the examples that exposed them.

### No Source-Image Reuse

Generated HTML candidates must not use the source PNG as a visual layer. The source raster is allowed for:

- visual inspection
- reference panes in an explicit QA view
- screenshot comparison
- human judging

It is not allowed inside the generated candidate through `<img>`, CSS background images, canvas `drawImage`, or any equivalent source-image copy.

### Coordinate Systems

Every plot region should define named coordinate transforms before marks are rendered.

Required transform concepts:

- data domain
- pixel range
- plot bbox
- event anchor, if event-aligned
- category positions, if categorical
- tick generation or explicit tick list

Avoid mixing hard-coded pixel positions with scale-derived positions. Event lines, ticks, annotations, and data marks must share the same transform.

### Axis Rendering

Visible axes should emit both tick marks and tick labels unless the source clearly suppresses one of them.

This applies to:

- quantitative axes
- categorical axes
- repeated axes in small multiples
- secondary panels that share a domain with another subplot

If an axis appears in the source, the spec should represent it as editable structure, not as incidental text.

### Label Alignment

Text rendering needs explicit alignment modes rather than ad hoc top-left placement.

Support at minimum:

- left-aligned text
- centered single-line text
- centered multiline text with explicit width and line height
- vertical top-anchored axis label
- vertical center-anchored axis label tied to a plot bbox
- tick labels with anchor and offset rules

Visually grouped text may need separate semantic objects when alignment differs. For example, a condition label and its sample-size label should be separate if they center independently.

### Uncertainty And Error Bands

Do not invent rectangular confidence bars just to approximate a shaded region. If uncertainty is visible:

- represent it as a curve-following band when possible
- otherwise omit it and mark uncertainty as unresolved

False visual layers are worse than missing approximate layers because they misrepresent the chart grammar.

### Renderer Selection

Choose renderer by mark type and density:

- canvas for heatmaps, rasters, dense dots, and pixel-native fields
- SVG for paths, axes, contours, line plots, brackets, and editable vector marks
- DOM for text-heavy schematic panels and simple editable labels
- hybrid rendering for most scientific panels

The renderer is an implementation detail. The spec remains the source of truth.

### Recognition Versus Rendering

Detecting a tick label in OCR or metadata is not enough. The reconstruction must infer and render the axis structure:

- tick value
- tick mark geometry
- tick label geometry
- scale/domain relation
- whether the tick belongs to a shared or repeated axis

When a panel has category labels under an axis, explicitly decide whether visible tick marks should exist. Do not treat category text as a substitute for axis geometry.

## Test Set Plan

Use diverse cropped subpanels, not just visually similar plots.

Initial candidates:

- violin/distribution plot: `reference-05-grid-remapping-D`
- heatmap or matrix panel
- line plot with error bands
- dense scatter or raster panel
- small multiples panel
- schematic/diagram panel
- mixed panel with colorbar and annotations

For each panel, record:

- source panel path
- panel type
- renderer used
- what worked
- what failed
- schema changes needed
- whether SVG, DOM, canvas, or hybrid seemed best

## Test: Violin/Distribution Panel

Panel: `reference-05-grid-remapping-D`

Created files:

- `annotations/manual-visual-elements/reference-05-grid-remapping-D-visual-elements.json`
- `annotations/manual-visual-elements/reference-05-grid-remapping-D-visual-elements-overlay.png`
- `html-reconstructions/reference-05-grid-remapping-D.json`
- `html-reconstructions/reference-05-grid-remapping-D.html`
- `html-reconstructions/reference-05-grid-remapping-D-dom.html`

Lessons so far:

- JSON spec as source of truth is the right direction.
- SVG is naturally strong for scientific plot marks, axes, and annotations.
- DOM-only rendering can work for simple plots but is awkward for complex shapes.
- Canvas should be reserved for dense point fields, rasters, heatmaps, and other pixel-native layers.
- Human visual review is essential because the data may be approximate while the semantic layout still needs to feel right.

## Test: Paired Heatmap Panel

Panel: `reference-05-grid-remapping-C`

Created files:

- `annotations/manual-visual-elements/reference-05-grid-remapping-C-visual-elements.json`
- `annotations/manual-visual-elements/reference-05-grid-remapping-C-visual-elements-overlay.png`
- `html-reconstructions/reference-05-grid-remapping-C.json`
- `html-reconstructions/reference-05-grid-remapping-C-hybrid.html`

Renderer used:

- hybrid DOM + canvas
- canvas for the two autocorrelogram heatmaps and the colorbar gradient
- DOM for panel text, condition labels, axes, ticks, tick labels, and axis labels

Lessons:

- Canvas is a good fit for heatmap pixels and color gradients, especially when exact source matrix values are unknown.
- The editable spec should store a heatmap recipe or matrix separately from canvas drawing mechanics.
- DOM axes can work for simple static axes, but label anchoring becomes fiddly; SVG remains cleaner for many axis/tick systems.
- Hybrid rendering seems like the best general direction: canvas for pixel-native/dense layers, SVG or DOM for editable structure.
- Cropped subpanels may include non-semantic neighboring fragments. Mark these as source-context artifacts, not plot semantics.

## Open Questions

- How detailed should the initial bbox parse be before moving to spec generation?
- Should every renderer use the same spec, or should renderers have small renderer-specific hints?
- What is the threshold for switching scatter points from SVG to canvas?
- How should heatmap matrices be represented when the original values are unknown?
- Should the skill produce editable approximate data or preserve visual fidelity first?
- How should confidence and unresolved ambiguities be surfaced to the user?

## Near-Term Refinement Loop

1. Pick the next panel type.
2. Produce fresh visual metadata and overlay.
3. Generate a spec and renderer.
4. Have the user judge visual quality.
5. Update this document with the new lesson.
6. Only after several panel types pass, convert the stable workflow into a formal reusable Codex skill.

## Batch Feedback Loop

Panel-by-panel work is too slow for strategy selection. Use a batch gallery whenever we need broad feedback.

Important correction: the first batch gallery reused source PNGs as mark layers. That is invalid for reconstruction quality. Batch galleries may show source PNGs only as separate QA/reference panes, never as part of the generated candidate.

Deprecated batch tooling:

- `scripts/generate_strategy_gallery.py`
- `html-reconstructions/batch/strategy-gallery.json`
- `html-reconstructions/batch/index.html`
- `html-reconstructions/batch/strategy-contact-sheet.png`

The current batch covers all 62 cropped subpanels, but its generated previews are invalid as reconstructions because they used source raster content as a mark layer. Keep it only as a record of the failed approach.

Strategy assignment counts:

- `hybrid_canvas_dom`: 24 panels
- `svg_vectors_dom_text`: 19 panels
- `hybrid_canvas_svg_dom`: 16 panels
- `dom_svg_schematic`: 2 panels
- `hybrid_unknown`: 1 panel

Future batch galleries should separate each panel into:

- source PNG for visual ground truth in a clearly labeled reference pane
- generated candidate built only from DOM/SVG/canvas marks, data recipes, and layout specs
- optional QA overlay showing parsed bboxes or diff metrics
- automatically assigned renderer strategy label

Use this gallery to collect high-volume feedback:

- Which plot types need SVG instead of canvas?
- Which panels need canvas because density or heatmap content dominates?
- Which text overlays are too noisy to trust?
- Which source crops contain neighboring context fragments that should be excluded?
- Which strategies produce acceptable first drafts versus misleading ones?

After feedback, update the strategy classifier and regenerate the gallery rather than refining one panel at a time.

## Test: No-Image Four-Panel Pass

Panels:

- `reference-01-place-code-opto-A`
- `reference-01-place-code-opto-C`
- `reference-01-place-code-opto-E`
- `reference-02-decision-dynamics-A`

Created files:

- `html-reconstructions/no-image-four/no-image-four.json`
- `html-reconstructions/no-image-four/index.html`

Strategies:

- 1A: generated canvas heatmaps + DOM axes/text/colorbar
- 1C: generated canvas raster and line plot + DOM axes/text
- 1E: DOM vector lines/points/errorbar + DOM axes/text
- 2A: DOM/CSS schematic elements, timeline, and process table

Validation:

- no `<img>` elements
- no canvas `drawImage`
- no source PNG path references in the no-image HTML/spec
- source PNGs were used only for visual inspection during authoring

Event-aligned raster/time-series correction pass:

- Issue: condition-side labels were authored as single multiline blocks, so sample-size labels and condition labels could not be centered independently.
  Fix: split condition descriptors, sample-size labels, and row labels into separate positioned text objects with explicit width and `text-align: center`.
- Issue: an event-aligned `0` tick was computed from axis geometry while the event line used a hard-coded x position.
  Fix: make event markers and all event-aligned x ticks share the same scale function or explicit event anchor.
- Issue: bottom line plot had an x-axis line but no tick marks or tick labels.
  Fix: x ticks are required for every visible quantitative axis, even when the same domain appears in a neighboring subplot.
- Issue: a wide grey confidence band was drawn as a rectangular bar, which looked like a false data layer.
  Fix: uncertainty bands should follow the data curve or be omitted until the renderer can generate a curve-following band.
- Issue: rotated y-axis text was manually transformed and drifted out of alignment.
  Fix: use a reusable vertical-label helper or SVG text transform with a tested anchor model; do not hand-place rotated multiline labels.

Generalized rule:

For multi-axis/event-aligned panels, every axis, tick, event line, and annotation should be derived from named coordinate transforms in the spec. Avoid mixed hard-coded pixels and scale-derived positions. Text blocks that appear visually grouped in the source may still need separate semantic objects if their alignment differs.

Second correction pass:

- Side labels needed centered multiline text helpers, not just individually placed text blocks. Use explicit `centerX`, `width`, and `lineHeight` for condition labels and sample-size labels.
- Categorical x axes still need tick marks, even if the categories are labeled. Category labels alone do not communicate the axis geometry.
- Vertical axis labels should be centered against the plot bbox using a helper such as `verticalCenteredLabel(x, plot.y + plot.height / 2)`, not positioned by top-left guesswork.

Generalized rule:

Axis renderers must emit both tick marks and tick labels for categorical and quantitative axes unless the source clearly suppresses marks. Label renderers need explicit alignment modes: left text, centered single-line, centered multiline, vertical top-anchored, and vertical center-anchored.
