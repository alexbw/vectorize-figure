# Reconstruction Contract

Use this contract when converting a raster scientific figure into configurable HTML and JSON.

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
    "axes": {"xAxisY": 258, "yAxisX": 64, "xTickLength": 6, "yTickLength": 6},
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
- Keep CSS local to the output file unless the user requests a bundled app.
- Avoid external dependencies unless the figure genuinely needs them.

## Validation

Run a local browser check when possible:

```bash
python3 -m http.server 8765
```

Then open the output at native dimensions, or capture a headless screenshot. Check for blank canvases, missing JSON loads, broken source paths, overlapped labels, and accidental source-raster reuse.
