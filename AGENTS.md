# Repository Instructions

This repository is the authoritative home for the Vectorize Figure workflow:

- Repo root: `/Users/alex/Code/vectorize-figure`
- Command: `$vectorize-figure`
- Plugin source: `plugins/vectorize-figure`
- Skill source: `skills/vectorize-figure`
- Primary viewer hub: `outputs/index.html`
- Primary viewers: `outputs/full-figure-batch-viewer.html` and `outputs/vectorize-figure-batch-gallery.html`

Do not use pre-rename command, plugin, skill, or output paths for new work in this repo. If a session exposes stale skill metadata, prefer the files in this repository and the installed `vectorize-figure@personal` plugin.

For scientific figure reconstruction work, generated candidates must not reuse the source raster as a visual layer. Source images are allowed only in clearly labeled QA/reference views outside the generated-surface root.

For multi-panel figures, try a whole-composite reconstruction only when it can remain semantic and inspectable. If that fails syntax, no-raster-reuse, rendered-pixel, or visual-readability checks, crop all source-supported subpanels and run `$vectorize-figure` on each crop before assembling a composite.

Use these validation commands before handing off substantial changes:

```bash
python3 scripts/validate_vectorize_figure_workflow.py --jobs 4
python3 scripts/validate_vectorize_figure_workflow.py --all-variants --skip-browser --jobs 4
python3 scripts/validate_vectorize_figure_workflow.py --all-gallery --jobs 4
```

When Safari-specific browser behavior matters, use the local `pw` CLI with a named session:

```bash
pw nav URL --name codex
pw snap --name codex
pw close --name codex
```

Avoid `pw eval JS` with untrusted input because it executes JavaScript in the user's real Safari session.
