# Full Figure Viewer Handoff

Date: 2026-06-08

Repo: `/Users/alex/Code/vectorize-figure`

Current plugin version: `0.1.0+codex.20260608005037`

Installed Codex plugin cache:

`/Users/alex/.codex/plugins/cache/personal/vectorize-figure/0.1.0+codex.20260608005037`

Current viewer URL:

`http://127.0.0.1:8766/outputs/full-figure-batch-viewer.html`

There is an HTTP server already running on port `8766`, serving `/Users/alex/Code/vectorize-figure`.

Current full viewer cache version: `20260608-generated-surface-v4`

Current subpanel gallery cache version: `vectorize-batch-gallery-v4`

## User-Visible Bug

In the full-figure batch viewer, pressing `t` appears to toggle between `GEN` and `REF`, but the visual image looks identical. That should not happen: generated reconstructions can be close to the source reference, but they should not be pixel-identical.

Treat any recurrence as a viewer/display bug until proven otherwise. The current viewer code now forces generated mode inside the iframe, accepts both `#surface` and `[data-role="generated-candidate"]` as generated-surface roots, hides QA/reference siblings, and exposes outer `data-*` state so automated checks can prove what is visible.

## Relevant Files

- Viewer: `outputs/full-figure-batch-viewer.html`
- Generated full figures: `outputs/full-figure-batch/<figure-id>/<figure-id>.html`
- Generated JSON specs: `outputs/full-figure-batch/<figure-id>/<figure-id>.json`
- Full reference PNGs: `assets/full-reference/<figure-id>.png`
- Batch harness: `tmp/vectorize-figure-full-figures/run_batch.py`

Full figure IDs:

- `reference-01-place-code-opto`
- `reference-02-decision-dynamics`
- `reference-03-learning-remapping`
- `reference-04-motor-manifold`
- `reference-05-grid-remapping`
- `reference-06-replay-stimulation`
- `reference-07-cross-region-small-multiples`
- `reference-08-neuropixels-central-heatmap`

## What Was Already Verified

The reference PNG files and generated HTML files are distinct files with different hashes.

The generated full-figure HTML files currently contain one QA/reference `<img>` internally. Example structure:

```html
<div id="frame" class="frame">
  <div id="surface" class="surface"></div>
  <img id="reference" class="reference" alt="QA reference source image">
</div>
```

That internal reference image is intended only for QA inside the generated page. It must not be what the outer viewer presents as `GEN`.

Current validation additionally checks active generated outputs for stale pre-rename command naming, audits JSON specs for source-raster paths in generated mark data, and audits rendered generated surfaces for `<img>`/SVG `<image>` source-raster reuse. The generated-surface audit prefers `#surface` or `[data-role="generated-candidate"]` and also recognizes existing generated-only candidate containers such as `.candidate`, `#candidate`, and generated SVG/canvas roots so QA/reference siblings remain allowed outside the generated surface.

Latest hardened verifier state:

- `python3 scripts/validate_vectorize_figure_workflow.py --jobs 4` passes with browser checks.
- `python3 scripts/validate_vectorize_figure_workflow.py --all-variants --skip-browser --jobs 4` passes across 79 active plus historical/test output pages.
- `python3 scripts/validate_vectorize_figure_workflow.py --all-gallery --jobs 4` passes all workflow checks, including the 62-entry subpanel gallery browser pass.
- `python3 scripts/validate_vectorize_figure_plugin.py` now verifies that the installed Codex plugin cache for the current manifest version exists and matches `plugins/vectorize-figure/` byte-for-byte.
- `python3 scripts/validate_vectorize_figure_workflow.py --jobs 4` passes after the plugin validator was hardened to assert agent metadata and after the batch harnesses were hardened against embedded `data:image/...` reuse.
- `python3 scripts/test_vectorize_figure_validators.py` currently runs 23 focused tests, including direct tests that both full-figure and subpanel generation harnesses reject embedded image data URIs in JSON or HTML before treating existing outputs as valid, a standalone subpanel batch validator test for HTML `data:image` reuse, and inline-JS extractor tests that ignore JSON script tags.
- `python3 scripts/validate_vectorize_figure_workflow.py --skip-browser --jobs 4 --fail-fast` now includes `viewer inline javascript`; it extracts inline scripts from the full viewer and subpanel gallery HTML files and runs `node --check` when Node is available.
- `python3 scripts/validate_vectorize_figure_workflow.py --all-variants --skip-browser --jobs 4 --fail-fast` passes with `OK workflow: checks=10 failed=0` and validates 79 active plus historical/test output pages.
- The full viewer and subpanel gallery now select generated surfaces through a helper that rejects candidates inside QA/reference containers before forcing generated mode or reporting generated-surface display state.
- `python3 scripts/validate_vectorize_figure_workflow.py --jobs 4` passes after the generated-surface selector hardening with `OK workflow: checks=13 failed=0`.
- `python3 scripts/validate_vectorize_figure_workflow.py --all-gallery --jobs 4` passes after the generated-surface selector hardening with `OK workflow: checks=13 failed=0`; the all-gallery browser phase reports `OK subpanel gallery: total=62 failed=0`.
- `verify_viewer.py` now requires the outer body to report a visible outer generated iframe, hidden outer reference PNG, `data-gen-ready="1"`, a visible `data-generated-surface-display`, and `data-internal-reference-display` of `none` or `missing` before accepting GEN screenshots.
- `verify_gallery.py` applies the same outer-view and generated-surface assertions to representative or all subpanel gallery entries.
- `verify_no_raster_reuse.py`, `validate_vectorize_figure_outputs.py`, and `validate_batch.py` now reject embedded `data:image/...` values in generated image contexts, not only filename-based source-raster paths.
- Representative focused checks passed for full figure `reference-07-cross-region-small-multiples` and gallery panel `reference-08-neuropixels-central-heatmap-D`.

Latest Safari smoke check:

- Opened `reference-07-cross-region-small-multiples` in `mode=gen` through `pw`.
- Outer state: `data-mode="gen"`, generated iframe visible, reference image hidden.
- Generated iframe state: `#surface` display `block`, internal `#reference` display `none`, `#frame` class `frame`.
- Space-toggle to REF hid the iframe and showed the PNG; toggling back restored GEN and kept internal `#reference` hidden.
- Opened gallery panel `reference-08-neuropixels-central-heatmap-D` in generated mode through `pw`; this panel uses `#candidate` rather than `#surface`.
- Gallery generated state: generated-surface display `block`, generated iframe visible, outer reference hidden, internal QA reference hidden or missing.
- Gallery buttons toggled to REF and back to GEN correctly.

Latest Safari re-check on 2026-06-08:

- Full viewer URL: `http://127.0.0.1:8766/outputs/full-figure-batch-viewer.html?id=reference-07-cross-region-small-multiples&mode=gen&debug=1`.
- Full viewer GEN state: `data-mode="gen"`, `data-generated-frame-display="block"`, `data-outer-reference-display="none"`, `data-gen-ready="1"`, `data-generated-surface-display="block"`, `data-internal-reference-display="none"`.
- Space-toggle to REF reported generated iframe `none` and outer reference `block`; toggling back to GEN restored generated iframe `block`, outer reference `none`, generated surface `block`, and internal reference `none`.
- Gallery URL: `http://127.0.0.1:8766/outputs/vectorize-figure-batch-gallery.html?id=reference-08-neuropixels-central-heatmap-D&mode=generated&debug=1`.
- Gallery GEN state: `data-mode="generated"`, `data-panel="reference-08-neuropixels-central-heatmap-D"`, generated iframe `block`, outer reference `none`, `data-gen-ready="1"`, generated surface `block`, internal reference `missing`.

Latest v4 cache-buster validation:

- Full viewer `VIEWER_VERSION` is `20260608-generated-surface-v4`.
- Subpanel gallery `VIEWER_VERSION` is `vectorize-batch-gallery-v4`.
- `python3 tmp/vectorize-figure-full-figures/verify_viewer.py --keep` passes all 8 full figures after the v4 bump.
- `python3 tmp/vectorize-figure-all-subpanels/verify_gallery.py` passes the representative gallery set after the v4 bump.
- `python3 scripts/validate_vectorize_figure_workflow.py --skip-browser --jobs 4 --fail-fast` passes after the v4 bump with `OK workflow: checks=10 failed=0`.
- `python3 scripts/validate_vectorize_figure_workflow.py --all-gallery --jobs 4` passes after the v4 bump with `OK workflow: checks=13 failed=0`; the all-gallery browser phase reports `OK subpanel gallery: total=62 failed=0`.

Prior validation showed:

- JSON files parse.
- Inline scripts pass `node --check`.
- HTML files do not use `drawImage`.
- HTML files do not use CSS `background-image` source reuse.
- The only source/reference image use in generated HTML should be QA-only.

Known previous generation problems:

- `reference-01-place-code-opto.html` had a JS syntax issue around unary minus and exponentiation; it was patched manually.
- `reference-07-cross-region-small-multiples` had malformed generated JS; it was regenerated through `$vectorize-figure`.

Because of those manual/regenerated changes, do not assume the batch is clean until it is revalidated from scratch.

## Current Viewer Wiring

In `outputs/full-figure-batch-viewer.html`, each figure has:

```js
ref: `../assets/full-reference/${id}.png`,
gen: `full-figure-batch/${id}/${id}.html`
```

The outer viewer contains:

```html
<iframe id="genView" class="view" title="Generated figure"></iframe>
<img id="refView" class="view hidden" alt="Reference figure">
```

Toggle logic:

```js
const showingGen = mode === 'gen';
genView.classList.toggle('hidden', !showingGen);
refView.classList.toggle('hidden', showingGen);
```

So if `t` looks identical, likely causes are:

1. The iframe is showing the generated page's internal QA/reference image instead of `#surface`.
2. The iframe did not render the vector surface and is falling back to or exposing the internal reference image.
3. Safari/browser cache is showing stale HTML despite the viewer cache buster.
4. The generated HTML itself is source-reusing in a way not caught by the simple text checks.
5. The user is seeing a stale viewer tab from the old server or previous file contents.

## Clean-Start Debug Plan

Start in the right repo:

```bash
cd /Users/alex/Code/vectorize-figure
```

Confirm the server:

```bash
lsof -i :8766
```

If needed, restart a clean server:

```bash
python3 -m http.server 8766
```

Open a cache-busted viewer URL:

```bash
open 'http://127.0.0.1:8766/outputs/full-figure-batch-viewer.html?debug=1'
```

Inspect the outer viewer state in Safari with `pw`:

```bash
pw nav 'http://127.0.0.1:8766/outputs/full-figure-batch-viewer.html?debug=1' --name codex
pw eval "({mode: document.getElementById('modeButton').textContent, genHidden: document.getElementById('genView').classList.contains('hidden'), refHidden: document.getElementById('refView').classList.contains('hidden'), genSrc: document.getElementById('genView').src, refSrc: document.getElementById('refView').src})" --name codex
```

Press/toggle and re-check:

```bash
pw eval "window.dispatchEvent(new KeyboardEvent('keydown', {key:'t'})); ({mode: document.getElementById('modeButton').textContent, genHidden: document.getElementById('genView').classList.contains('hidden'), refHidden: document.getElementById('refView').classList.contains('hidden')})" --name codex
```

Inspect inside the generated iframe:

```bash
pw eval "const d = document.getElementById('genView').contentDocument; const surface = d.querySelector('#surface, [data-role=\"generated-candidate\"], .surface, .candidate, svg[viewBox], canvas'); const reference = d.querySelector('#reference, [data-role=\"reference\"], .reference, .reference-wrap, img.reference, figure.reference'); ({frameClass: d.getElementById('frame')?.className, surfaceDisplay: surface ? getComputedStyle(surface).display : 'missing', referenceDisplay: reference ? getComputedStyle(reference).display : 'missing', referenceSrc: reference?.src, surfaceChildren: surface?.children.length})" --name codex
```

Expected generated-state iframe result:

- `frameClass` should not include `show-reference`.
- `surfaceDisplay` should not be `none`.
- `referenceDisplay` should be `none`.
- `surfaceChildren` should be greater than zero.

If `referenceDisplay` is `block`, the outer viewer is showing the internal source reference as the generated image. Fix the generated page template and/or viewer iframe initialization so `#frame.show-reference` is removed and `#reference` is forcibly hidden in viewer mode.

## Add a Pixel-Level Regression Check

The fix should not rely on eyeballing. The current repeatable checks are:

```bash
python3 scripts/validate_vectorize_figure_workflow.py
python3 scripts/validate_vectorize_figure_workflow.py --jobs 4 --skip-browser
python3 scripts/validate_vectorize_figure_workflow.py --all-variants --jobs 4 --skip-browser
python3 scripts/validate_vectorize_figure_workflow.py --all-gallery
python3 scripts/validate_vectorize_figure_rename.py
python3 tmp/vectorize-figure-full-figures/verify_viewer.py --keep
python3 tmp/vectorize-figure-full-figures/verify_no_raster_reuse.py
python3 tmp/vectorize-figure-all-subpanels/verify_gallery.py
python3 scripts/validate_vectorize_figure_outputs.py --structural-only --jobs 4
python3 tmp/vectorize-figure-all-subpanels/validate_batch.py
```

`verify_viewer.py` captures the full-figure outer viewer in `GEN` and `REF` mode, compares pixels, and confirms the iframe generated surface is visible while the iframe QA/reference element is hidden. `verify_gallery.py` does the same for representative subpanel gallery panels.

Minimum acceptance:

- `GEN` screenshot and `REF` screenshot must not be pixel-identical.
- `GEN` screenshot must be nonblank.
- `REF` screenshot must be nonblank.
- The selected figure ID must match the requested rail item.
- The outer DOM must report visible generated iframe display, hidden outer reference display, `data-gen-ready="1"`, visible generated-surface display, and hidden or missing internal reference display.

Useful approach for extending coverage:

1. Patch the viewer to accept URL params:
   - `?figure=1`
   - `?id=reference-01-place-code-opto`
   - `?mode=gen`
   - `?mode=ref`
2. Patch the viewer to update the URL when selection or mode changes.
3. Use headless Chrome or `pw screenshot` to capture:
   - `viewer.html?figure=1&mode=gen`
   - `viewer.html?figure=1&mode=ref`
4. Compare bytes or pixels.

Headless Chrome command shape:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless \
  --disable-gpu \
  --hide-scrollbars \
  --window-size=1536,1024 \
  --screenshot=/tmp/full-viewer-01-gen.png \
  'http://127.0.0.1:8766/outputs/full-figure-batch-viewer.html?figure=1&mode=gen'
```

Repeat for `mode=ref`, then compare:

```bash
shasum /tmp/full-viewer-01-gen.png /tmp/full-viewer-01-ref.png
```

If hashes match, inspect DOM and iframe state before changing output generation.

## Likely Code Fixes

Viewer fixes to make first:

1. Add URL-param support for selected figure and mode.
2. On iframe load, forcibly put the generated page into generated mode:
   - remove `show-reference` from the iframe's `#frame`
   - hide iframe `#reference`
   - show iframe `#surface` or `[data-role="generated-candidate"]`
3. Make the iframe cache buster deterministic enough for testing:
   - use selected figure ID plus a viewer version, not only `Date.now()`
4. Add a visible debug attribute or data field during development:
   - `document.body.dataset.mode`
   - `document.body.dataset.figure`
5. Verify the outer `GEN` and `REF` modes via pixel screenshots.

Vectorize-figure fixes only if needed:

- If the generated page cannot render without its internal QA image, fix `$vectorize-figure` page generation/template.
- Do not patch individual full-figure HTML files as the real solution.
- Any fix that affects generated output should be made in the vectorize-figure skill/command/template and then the affected figures should be regenerated.

## Success Criteria

The task is complete only when:

- The viewer visibly toggles between generated reconstruction and source reference.
- Pixel screenshots for `GEN` and `REF` differ for at least several figures.
- The generated iframe is confirmed to show `#surface`, not the generated page's internal `#reference`.
- All 8 full figures can be selected independently from the rail.
- Fresh `$vectorize-figure` output does not require ad hoc edits to avoid this bug.
- The viewer is reopened at a cache-busted URL for user inspection.
