# Text Placement QA

Generated figure reconstructions must not ship with poor protected-text
placement. The first enforceable aesthetics gate is intentionally narrow:
prevent label overlap, clipping, and text intrusion into reserved visual
regions.

## Protected Text

These text roles are protected by default:

- `panel-label`
- `panel-title`
- `tick-label`
- `x-axis-label`
- `y-axis-label`
- `axis-label`
- `colorbar-label`
- `colorbar-title`
- `legend-label`
- `phase-label`
- `region-label`
- `table-header`
- `table-cell`

Every generated protected text node should expose a stable `id` or
`data-text-id`, a semantic `role`, and either a semantic anchor (`anchorTo`,
axis/value metadata, tick-label band, legend row, colorbar, table cell) or a
source-calibrated position with provenance.

## Failure Rules

The browser-rendered reconstruction fails layout QA when:

- protected text boxes overlap each other after fonts load and text fitting
  runs
- protected text is clipped outside the canvas
- protected text intersects a declared plot, colorbar, legend, orientation key,
  helper strip, phase/region band, or table region

Tick label fixes must move label anchors or offsets only. Do not move the tick
mark or source-calibrated data geometry to make text fit.

## Renderer Contract

Generated HTML should publish layout QA when loaded with `?qaDom=1`:

```html
<script id="figure-qa-output" type="application/json">
{"layoutQa": {"protectedTextCollisions": []}}
</script>
```

The shared hybrid renderer already exposes `window.figureLayoutQa` and the
`#figure-qa-output` script. Custom renderers should match that shape.

## Source-Faithful Exceptions

If the source visibly overlaps protected text, record an explicit exception
instead of hiding the problem. Prefer resolving the exception in renderer QA so
the published failure arrays contain only actionable problems.

Example:

```json
{
  "validation": {
    "layoutQa": {
      "minTextGapPx": 1.5,
      "minZoneGapPx": 1,
      "allowOverlaps": [
        {"a": "panel-title", "b": "panel-label", "reason": "source-faithful"}
      ]
    }
  }
}
```

Use exceptions sparingly. A visible overlap in the generated output should be
treated as a bug unless the source clearly does the same thing.
