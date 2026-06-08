#!/usr/bin/env python3
"""Focused tests for vectorize-figure validator helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_vectorize_figure_outputs.py"
INLINE_JS_VALIDATOR = ROOT / "scripts" / "validate_vectorize_figure_inline_js.py"
BATCH_VALIDATOR = ROOT / "tmp" / "vectorize-figure-all-subpanels" / "validate_batch.py"
SUBPANEL_RUN_BATCH = ROOT / "tmp" / "vectorize-figure-all-subpanels" / "run_batch.py"
FULL_RUN_BATCH = ROOT / "tmp" / "vectorize-figure-full-figures" / "run_batch.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_vectorize_figure_outputs", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_validator()


def load_batch_validator():
    spec = importlib.util.spec_from_file_location("validate_batch", BATCH_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BATCH_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


batch_validator = load_batch_validator()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inline_js_validator = load_module("validate_vectorize_figure_inline_js", INLINE_JS_VALIDATOR)
subpanel_run_batch = load_module("subpanel_run_batch", SUBPANEL_RUN_BATCH)
full_run_batch = load_module("full_run_batch", FULL_RUN_BATCH)


class ScreenshotCropTests(unittest.TestCase):
    def test_finds_white_surface_without_dark_border(self) -> None:
        image = Image.new("RGB", (800, 732), (238, 238, 238))
        left = 144
        top = 141
        width = 512
        height = 512
        for y in range(top, top + height):
            for x in range(left, left + width):
                image.putpixel((x, y), (255, 255, 255))

        self.assertEqual(
            validator.find_frame_crop(image, width, height),
            (left, top, left + width, top + height),
        )


class InlineJavaScriptExtractorTests(unittest.TestCase):
    def test_extracts_plain_and_module_scripts(self) -> None:
        html = """
        <script>const plain = 1;</script>
        <script type="module">const moduleValue = 2;</script>
        """
        scripts = inline_js_validator.extract_scripts_from_text(html)
        self.assertEqual([script.strip() for script in scripts], ["const plain = 1;", "const moduleValue = 2;"])

    def test_ignores_json_scripts(self) -> None:
        html = """
        <script type="application/json">{"not": "javascript"}</script>
        <script type="text/javascript">const checked = true;</script>
        """
        scripts = inline_js_validator.extract_scripts_from_text(html)
        self.assertEqual([script.strip() for script in scripts], ["const checked = true;"])


class GeneratedSurfaceAuditTests(unittest.TestCase):
    def audit(self, dom: str) -> list[str]:
        return validator.audit_rendered_surface(Path("candidate.html"), dom)

    def test_surface_excludes_reference_sibling(self) -> None:
        dom = """
        <body>
          <div id="frame">
            <div id="surface"><svg><path d="M0 0L1 1"></path></svg></div>
            <img id="reference" src="../../../assets/full-reference/reference-01-place-code-opto.png">
          </div>
        </body>
        """
        self.assertEqual(self.audit(dom), [])

    def test_candidate_wrapper_excludes_qa_sibling(self) -> None:
        dom = """
        <body>
          <div id="candidate" class="candidate"><canvas></canvas><svg></svg></div>
          <aside class="qa-reference">
            <img src="../../assets/reference/reference-01-place-code-opto-A-reference.png">
          </aside>
        </body>
        """
        self.assertEqual(self.audit(dom), [])

    def test_data_role_generated_candidate_excludes_reference_sibling(self) -> None:
        dom = """
        <body>
          <section data-role="generated-candidate"><svg><path d="M0 0L1 1"></path></svg></section>
          <img id="reference" src="../../../assets/full-reference/reference-01-place-code-opto.png">
        </body>
        """
        self.assertEqual(self.audit(dom), [])

    def test_generated_surface_rejects_img(self) -> None:
        dom = """
        <body>
          <figure class="candidate">
            <img src="../../assets/reference/reference-01-place-code-opto-A-reference.png">
          </figure>
        </body>
        """
        errors = self.audit(dom)
        self.assertTrue(any("image elements" in error for error in errors), errors)
        self.assertTrue(any("source raster" in error for error in errors), errors)

    def test_generated_surface_rejects_svg_image(self) -> None:
        dom = """
        <body>
          <svg id="figure">
            <image href="../../assets/reference/reference-01-place-code-opto-A-reference.png"></image>
          </svg>
        </body>
        """
        errors = self.audit(dom)
        self.assertTrue(any("image elements" in error for error in errors), errors)
        self.assertTrue(any("source raster" in error for error in errors), errors)

    def test_generated_surface_rejects_embedded_image_data_uri(self) -> None:
        dom = """
        <body>
          <svg id="figure">
            <image href="data:image/png;base64,AAAA"></image>
          </svg>
        </body>
        """
        errors = self.audit(dom)
        self.assertTrue(any("image elements" in error for error in errors), errors)
        self.assertTrue(any("embedded image data URI" in error for error in errors), errors)

    def test_generated_surface_rejects_url_encoded_source_raster(self) -> None:
        dom = """
        <body>
          <svg id="figure">
            <image href="../../assets/reference/reference-01-place-code-opto-A-reference%2epng"></image>
          </svg>
        </body>
        """
        errors = self.audit(dom)
        self.assertTrue(any("image elements" in error for error in errors), errors)
        self.assertTrue(any("source raster" in error for error in errors), errors)

    def test_missing_generated_surface_fails(self) -> None:
        errors = self.audit("<body><aside class='qa-reference'><img src='reference-01.png'></aside></body>")
        self.assertTrue(any("missing a generated surface" in error for error in errors), errors)


class JsonSourceRasterAuditTests(unittest.TestCase):
    def scan(self, spec: dict) -> list[str]:
        return validator.scan_json_for_source_images(Path("candidate.json"), spec, "reference-01-place-code-opto-A")

    def test_source_path_is_allowed(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "source": {"path": "../../assets/reference/reference-01-place-code-opto-A-reference.png"},
        }
        self.assertEqual(self.scan(spec), [])

    def test_generated_image_mark_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "marks": [
                        {
                            "type": "image",
                            "src": "../../assets/reference/reference-01-place-code-opto-A-reference.png",
                        }
                    ]
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("generated JSON references source raster or embedded image" in error for error in errors), errors)

    def test_generated_image_mark_data_uri_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "marks": [
                        {
                            "type": "image",
                            "src": "data:image/png;base64,AAAA",
                        }
                    ]
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("generated JSON references source raster or embedded image" in error for error in errors), errors)

    def test_generated_image_mark_url_encoded_source_raster_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "marks": [
                        {
                            "type": "image",
                            "src": "../../assets/reference/reference-01-place-code-opto-A-reference%2epng",
                        }
                    ]
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("generated JSON references source raster or embedded image" in error for error in errors), errors)

    def test_other_reference_asset_image_mark_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "marks": [
                        {
                            "type": "image",
                            "src": "../../assets/reference/reference-02-decision-dynamics-A-reference.png",
                        }
                    ]
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("generated JSON references source raster or embedded image" in error for error in errors), errors)

    def test_non_image_mark_src_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "marks": [
                        {
                            "type": "line",
                            "src": "../../assets/reference/reference-01-place-code-opto-A-reference.png",
                        }
                    ]
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("generated JSON references source raster or embedded image" in error for error in errors), errors)

    def test_provenance_reference_path_is_allowed(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "provenance": {
                "referencePath": "../../assets/reference/reference-01-place-code-opto-A-reference.png",
            },
        }
        self.assertEqual(self.scan(spec), [])


class StandaloneBatchJsonAuditTests(unittest.TestCase):
    def scan(self, spec: dict) -> list[str]:
        return batch_validator.scan_json_for_source_images(
            Path("candidate.json"),
            spec,
            "reference-01-place-code-opto-A",
        )

    def test_source_path_is_allowed(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "source": {"path": "../../assets/reference/reference-01-place-code-opto-A-reference.png"},
        }
        self.assertEqual(self.scan(spec), [])

    def test_generated_image_mark_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "marks": [
                {
                    "type": "image",
                    "src": "../../assets/reference/reference-01-place-code-opto-A-reference.png",
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("marks.0.src" in error for error in errors), errors)

    def test_generated_image_mark_data_uri_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "marks": [
                {
                    "type": "image",
                    "src": "data:image/png;base64,AAAA",
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("marks.0.src" in error for error in errors), errors)

    def test_generated_image_mark_url_encoded_source_raster_is_rejected(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "marks": [
                {
                    "type": "image",
                    "src": "../../assets/reference/reference-01-place-code-opto-A-reference%2epng",
                }
            ],
        }
        errors = self.scan(spec)
        self.assertTrue(any("marks.0.src" in error for error in errors), errors)


class RunBatchValidationTests(unittest.TestCase):
    def make_output(self, temp_root: Path, item_id: str, spec: dict, html_text: str = "<html><body></body></html>") -> Path:
        outdir = temp_root / f"{item_id}-vectorize-figure-batch"
        outdir.mkdir()
        (outdir / "source.png").write_bytes(b"png")
        (outdir / f"{item_id}.json").write_text(json.dumps(spec))
        (outdir / f"{item_id}.html").write_text(html_text)
        return outdir

    def test_subpanel_run_batch_rejects_json_data_uri(self) -> None:
        panel_id = "reference-01-place-code-opto-A"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            outdir = self.make_output(
                Path(temp),
                panel_id,
                {
                    "id": panel_id,
                    "source": {"path": "./source.png"},
                    "marks": [{"type": "image", "src": "data:image/png;base64,AAAA"}],
                },
            )
            result = subpanel_run_batch.validate(panel_id, outdir)
        self.assertTrue(result["raster_reuse_hits"], result)

    def test_subpanel_run_batch_rejects_html_data_uri(self) -> None:
        panel_id = "reference-01-place-code-opto-A"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            outdir = self.make_output(
                Path(temp),
                panel_id,
                {"id": panel_id, "source": {"path": "./source.png"}, "marks": []},
                '<html><body><img src="data:image/png;base64,AAAA"></body></html>',
            )
            result = subpanel_run_batch.validate(panel_id, outdir)
        self.assertTrue(result["raster_reuse_hits"], result)

    def test_subpanel_run_batch_rejects_url_encoded_source_raster(self) -> None:
        panel_id = "reference-01-place-code-opto-A"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            outdir = self.make_output(
                Path(temp),
                panel_id,
                {
                    "id": panel_id,
                    "source": {"path": "./source.png"},
                    "marks": [{"type": "image", "src": "../../assets/reference/reference-01-place-code-opto-A-reference%2epng"}],
                },
            )
            result = subpanel_run_batch.validate(panel_id, outdir)
        self.assertTrue(result["raster_reuse_hits"], result)

    def test_full_run_batch_rejects_json_data_uri(self) -> None:
        figure_id = "reference-01-place-code-opto"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            outdir = self.make_output(
                Path(temp),
                figure_id,
                {
                    "id": figure_id,
                    "source": {"path": "./source.png"},
                    "marks": [{"type": "image", "src": "data:image/png;base64,AAAA"}],
                },
            )
            result = full_run_batch.validate(figure_id, outdir)
        self.assertTrue(result["raster_reuse_hits"], result)

    def test_full_run_batch_rejects_html_data_uri(self) -> None:
        figure_id = "reference-01-place-code-opto"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            outdir = self.make_output(
                Path(temp),
                figure_id,
                {"id": figure_id, "source": {"path": "./source.png"}, "marks": []},
                '<html><body><image href="data:image/png;base64,AAAA"></image></body></html>',
            )
            result = full_run_batch.validate(figure_id, outdir)
        self.assertTrue(result["raster_reuse_hits"], result)

    def test_full_run_batch_rejects_url_encoded_source_raster(self) -> None:
        figure_id = "reference-01-place-code-opto"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            outdir = self.make_output(
                Path(temp),
                figure_id,
                {
                    "id": figure_id,
                    "source": {"path": "./source.png"},
                    "marks": [{"type": "image", "src": "../../assets/full-reference/reference-01-place-code-opto%2epng"}],
                },
            )
            result = full_run_batch.validate(figure_id, outdir)
        self.assertTrue(result["raster_reuse_hits"], result)

    def test_standalone_batch_validator_rejects_html_data_uri(self) -> None:
        panel_id = "reference-01-place-code-opto-A"
        original_out_root = batch_validator.OUT_ROOT
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            temp_root = Path(temp)
            self.make_output(
                temp_root,
                panel_id,
                {"id": panel_id, "source": {"path": "./source.png"}, "marks": []},
                '<html><body><img src="data:image/png;base64,AAAA"></body></html>',
            )
            try:
                batch_validator.OUT_ROOT = temp_root
                result = batch_validator.validate_one(panel_id)
            finally:
                batch_validator.OUT_ROOT = original_out_root
        self.assertTrue(result["html_forbidden_hits"], result)


if __name__ == "__main__":
    unittest.main()
