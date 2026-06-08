# Text Positioning Mismatch Plan

Date: 2026-06-06

## Visual Report

Annotated current overlays are saved in `tmp/font-qa/mismatch-report/`.

- Contact sheet: `tmp/font-qa/mismatch-report/annotated-mismatch-contact.png`
- Panel A: `tmp/font-qa/mismatch-report/annotated-A-overlay.png`
- Panel B: `tmp/font-qa/mismatch-report/annotated-B-overlay.png`
- Panel C: `tmp/font-qa/mismatch-report/annotated-C-overlay.png`
- Panel F: `tmp/font-qa/mismatch-report/annotated-F-overlay.png`
- Decision A: `tmp/font-qa/mismatch-report/annotated-decision-A-overlay.png`
- Decision B: `tmp/font-qa/mismatch-report/annotated-decision-B-overlay.png`

## Mismatch Inventory

| ID | Panel | Remaining discrepancy | What broke down | Specific fix |
| --- | --- | --- | --- | --- |
| A-01 | A | Header and heatmap titles are slightly baseline-shifted relative to the reference. | The fitter scored text boxes as standalone glyph masks, but the renderer mixes `middle` anchors, multi-line titles, and baseline y values. | Keep source-calibrated x positions, nudge title baselines only where the overlay shows source text consistently above/below generated text. |
| A-02 | A | Rotated y-axis title still has a small horizontal offset. | Rotated text bbox fitting treats the unrotated baseline as the score anchor; source crop makes the left edge ambiguous. | Keep manual rotated override, refine `overlayX` against the overlay rather than OCR box center. |
| A-03 | A | Colorbar title is close but still exposes a top/baseline mismatch. | Multi-line colorbar title used a baseline y from the pixel fitter instead of a top/hanging anchor. | Store explicit top-aligned manual override and note that this node is not an automated OCR fit. |
| A-04 | A | X tick/axis label band has minor vertical drift. | Axis labels are renderer-derived from axis geometry while OCR target boxes were measured from raster text pixels. | Prefer a shared manual y-band for control/opto x labels and ticks if drift remains after title fixes. |
| B-01 | B | Title and legend row have small baseline/width drift. | Mixed legend line/text layout was calibrated as text-only, ignoring the marker line anchor. | Leave mark geometry unchanged; adjust only legend text baseline if it visibly separates from source. |
| B-02 | B | Y tick/title band has a small left/right mismatch. | Rotated axis title and tick labels were calibrated independently, so the band does not behave as one source column. | Use a consistent y-axis text column for tick labels and the y title. |
| B-03 | B | X-axis title baseline is slightly low. | The renderer uses the plot axis baseline plus a fixed offset; source text baseline is closer to the tick band. | Nudge `x-label.overlayY` upward and document the manual axis-title override. |
| C-01 | C | Raster group labels are close but not perfectly aligned. | Multi-line group labels were scored by text box while source has uneven line spacing and color-specific antialiasing. | Keep calibrated family/size; refine the four group label y anchors as a block. |
| C-02 | C | Raster x ticks/title remain slightly horizontally and vertically offset. | The raster axis geometry and OCR text boxes disagree by a few pixels; text was fit to OCR boxes independently from ticks. | Move raster x tick labels and title as a band to keep them source-aligned while preserving tick pairing. |
| C-03 | C | Line y-axis title/tick band has small horizontal drift. | Rotated y-title was manually recovered after the automated rotated fitter failed. | Refine the manual y-title x anchor and keep y ticks in the source column. |
| C-04 | C | Line legend labels are slightly low/right. | Legend text was manually enlarged after OCR underfit, but the line marker anchor was not part of the text fit. | Nudge legend label anchors to match the source legend row. |
| F-01 | F | Rotated y-axis title is still too far left. | Source y-title is clipped by the panel edge; the first manual override optimized for avoiding tick overlap, not source alignment. | Move the rotated title right while keeping it outside the map/tick labels. |
| F-02 | F | X-axis titles sit below the source baseline. | Fixed renderer x-label offset is lower than the source label band for both maps. | Move both map x labels up as a shared band. |
| F-03 | F | Legend labels sit below the source legend text. | Legend labels were fitted as text boxes but rendered from a legend line baseline. | Move legend label baselines up together and keep marker lines unchanged. |
| F-04 | F | Colorbar title has residual top-anchor drift. | Multi-line colorbar title originally used baseline y; first manual pass fixed size but left a small x/y offset. | Refine `colorbar-label.overlayX/Y` with a manual top-anchor note. |
| F-05 | F | Colorbar tick labels are good enough but remain a source of possible baseline drift. | Log-scale colorbar ticks use renderer positions, while source labels include local antialiasing and slight tick-mark offsets. | Keep renderer tick positions unless a specific tick visibly separates; do not overfit individual tick labels. |
| DA-01 | Decision A | Epoch titles are slightly high/low relative to source. | Decision A renderer has semantic text positions but no `textCalibration` map; all titles share one hard-coded font/line-height. | Adjust epoch title y anchors as a group and keep screen geometry unchanged. |
| DA-02 | Decision A | Timeline tick/title band has baseline drift. | Collision-aware tick placement computes the axis title from rendered tick bboxes; this is robust semantically but not source-exact. | Use a smaller tick-title gap and/or fixed label anchor after collision resolution. |
| DA-03 | Decision A | Table/process row text has small y drift. | Table row text uses semantic row centers and shared font sizing, not OCR-aligned source boxes. | Nudge phase table label dy and process row y anchors as row groups. |
| DB-01 | Decision B | Panel title is slightly offset. | Decision B title is semantic text only; no per-node calibration fields are applied. | Adjust title y/x anchors conservatively if it remains visually material. |
| DB-02 | Decision B | Legend labels are slightly offset from source. | Legend text is placed from marker geometry rather than source text boxes. | Leave markers unchanged; nudge legend text only if needed after axis-title fixes. |
| DB-03 | Decision B | PC3 axis title remains offset. | 3D projected semantic anchor is not the source label anchor; manual pass was close but not exact. | Update PC3 axis-title x/y manually and document the projection mismatch. |
| DB-04 | Decision B | PC1 axis title remains offset. | Same projected-anchor mismatch as PC3; source label is artist-positioned rather than projected. | Update PC1 axis-title x/y manually and document the projection mismatch. |

## Execution Order

1. Apply low-risk JSON-only anchor fixes for the clearest remaining mismatches: F x labels/legend/y-title, Decision-B PC1/PC3 labels, and B x-axis label.
2. Apply smaller cleanup nudges to C raster/legend label bands where the current overlay shows consistent directional drift.
3. Recapture all six overlays in `actual-panel-viewer` overlay mode.
4. Rebuild a final overlay contact sheet.
5. Validate JSON parsing and run `git diff --check`.

## Execution Notes

Applied in this pass:

- Refined Panel A y-axis title and colorbar title manual anchors in `outputs/reference-01-place-code-opto-A-vectorize-figure/reference-01-place-code-opto-A.json`.
- Moved Panel B x-axis title baseline up in `outputs/reference-01-place-code-opto-B-vectorize-figure/reference-01-place-code-opto-B.json`.
- Nudged Panel C line legend labels up/left in `outputs/reference-01-place-code-opto-C-vectorize-figure/reference-01-place-code-opto-C.json`.
- Moved Panel F y-axis title right, x-axis titles up, legend labels up, and colorbar title left in `outputs/reference-01-place-code-opto-F-vectorize-figure/reference-01-place-code-opto-F.json`.
- Moved Decision A epoch titles down and timeline axis title down in `outputs/reference-02-decision-dynamics-A-vectorize-figure/reference-02-decision-dynamics-A.json`.
- Refined Decision B PC1 and PC3 axis-title manual anchors in `outputs/reference-02-decision-dynamics-B-vectorize-figure/reference-02-decision-dynamics-B.json`.

Post-fix overlays:

- Contact sheet: `tmp/font-qa/actual-viewer-shots/postfix-overlay-contact.png`
- Panel A: `tmp/font-qa/actual-viewer-shots/postfix-A-overlay.png`
- Panel B: `tmp/font-qa/actual-viewer-shots/postfix-B-overlay.png`
- Panel C: `tmp/font-qa/actual-viewer-shots/postfix-C-overlay.png`
- Panel F: `tmp/font-qa/actual-viewer-shots/postfix-F-overlay.png`
- Decision A: `tmp/font-qa/actual-viewer-shots/postfix-decision-A-overlay.png`
- Decision B: `tmp/font-qa/actual-viewer-shots/postfix-decision-B-overlay.png`

Validation:

- Parsed all six edited JSON specs successfully.
- `git diff --check` passed for the edited specs, this plan, and the actual panel viewer.
