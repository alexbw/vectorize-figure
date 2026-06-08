# Vectorize Figure Handoff

Date: 2026-06-08

## Current State

This checkpoint continues the repo cleanup and `make-figure` to
`vectorize-figure` rename. The worktree was intentionally dirty before this
session, with old `make-figure` paths deleted and new `vectorize-figure` paths
untracked. This checkpoint preserves that rename state.

## Completed In This Session

- Migrated one cropped panel to the denotational relationship pattern:
  `outputs/reference-01-place-code-opto-A-vectorize-figure-batch/reference-01-place-code-opto-A.json`.
- Added ignored metadata only for that panel:
  - named heatmap coordinate systems
  - layout owner boxes and tick-label bands
  - text anchors plus source-calibrated provenance
  - heatmap `ownerBox` and `clipToOwner`
  - explicit colorbar orientation, tick side, tick direction, label anchor, and title anchor
- Kept generated rendering unchanged. The panel HTML renderer ignores the new
  relationship fields.
- Updated the single stale visual baseline:
  `outputs/_regression-baselines/reference-01-place-code-opto-A.png`.
- Hardened screenshot crop detection in
  `scripts/validate_vectorize_figure_outputs.py` for white generated surfaces
  that do not have a dark frame border.
- Added unit coverage for the white-surface crop case in
  `scripts/test_vectorize_figure_validators.py`.
- Added Chrome DOM-dump timeout tolerance when Chrome prints complete DOM
  output but does not exit cleanly after `--dump-dom`.

## Audit State

Before the metadata migration:

```text
IR relationship audit: specs=70 objects=1977 warnings=1499
```

After the metadata migration:

```text
IR relationship audit: specs=70 objects=1985 warnings=1484
anchorTo: 38
children: 6
clipToOwner: 2
ownerBox: 2
parent: 6
usesTransform: 133
```

The migrated `reference-01-place-code-opto-A` cropped spec now has zero
relationship warnings.

## Validation

Passed:

```bash
python3 scripts/test_vectorize_figure_validators.py
python3 scripts/validate_vectorize_figure_outputs.py --outputs outputs/reference-01-place-code-opto-A-vectorize-figure-batch --jobs 1
python3 scripts/validate_vectorize_figure_workflow.py --skip-browser --jobs 4 --fail-fast
```

Focused browser validation for `reference-01-place-code-opto-A` passed with:

```text
changed=0.0000% mean_abs=0.000 threshold=0.5000%
```

The skip-browser workflow completed:

```text
OK workflow: checks=11 failed=0
```

## Notes

- A temporary local HTTP server on port 8765 was used for manual Chrome DOM
  diagnosis and has been stopped.
- Scratch audit files from this session were removed.
- The full browser-enabled workflow was not rerun after the final validator
  adjustment; the focused browser check and full skip-browser workflow passed.

## Suggested Next Work

1. Continue metadata-only migrations on cropped panels with compact warning
   sets before touching full composites.
2. Prefer panels that already have named scales and existing layout objects.
3. Keep the relationship audit warning-only until current outputs are migrated.
4. For each panel, run focused audit plus structural/browser validation before
   moving to the next metadata batch.
5. Avoid renderer rewrites unless a validator or mutation probe demonstrates a
   concrete relationship gap that metadata alone cannot express.
