# Font Calibration

This directory contains the current text-matching calibration harness for
`vectorize-figure` reconstructions. It is intentionally lightweight: a static HTML
page runs the pixel scoring in the browser, and a small Node wrapper launches
headless Chrome and writes updated JSON plus a report.

The source raster is QA-only. It is used to score text masks and produce visual
overlays, not as a generated figure layer.

## Usage

Create a calibration spec with text objects that include `sourceBox`:

```sh
node scripts/font-calibration/run-calibration.mjs /tmp/font-qa/reference-01-place-code-opto-C-text.json tmp/font-qa/reference-01-place-code-opto-C
```

The runner writes:

- `<prefix>-calibrated.json`: original spec with calibrated `fontFamily`,
  `fontSize`, `fontWeight`, `lineHeight`, `targetWidth`, and `fit`.
- `<prefix>-calibration-report.json`: per-label candidate family, geometry,
  score, baseline score, and improvement.

For a test-friendly assertion that does not require pixel identity:

```sh
node scripts/font-calibration/assert-improvement.mjs tmp/font-qa/reference-01-place-code-opto-C-calibration-report.json 4
```

To apply a calibrated text spec to a real generated panel JSON:

```sh
node scripts/font-calibration/apply-text-calibration.mjs outputs/reference-01-place-code-opto-C-vectorize-figure/reference-01-place-code-opto-C.json tmp/font-qa/reference-01-place-code-opto-C-alltext-calibrated.json
```

For exploratory OCR targets over the current reference panel set:

```sh
node scripts/font-calibration/build-ocr-targets.mjs
```

The OCR output is noisy by design. Use it to find labels worth calibrating, then
visually inspect the resulting overlay. A useful integration test should assert
that representative labels improve versus baseline score, not that the final
render is pixel-identical to the source.
