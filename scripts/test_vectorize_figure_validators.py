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
IR_FIELD_COVERAGE_AUDIT = ROOT / "scripts" / "audit_ir_field_coverage.py"
BATCH_VALIDATOR = ROOT / "scripts" / "subpanels" / "validate_batch.py"
SUBPANEL_RUN_BATCH = ROOT / "scripts" / "subpanels" / "run_batch.py"
FULL_RUN_BATCH = ROOT / "scripts" / "full-figures" / "run_batch.py"

# Scratch space for temporary fixtures; tmp/ is gitignored and may not exist.
(ROOT / "tmp").mkdir(exist_ok=True)


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
ir_field_coverage_audit = load_module("audit_ir_field_coverage", IR_FIELD_COVERAGE_AUDIT)
subpanel_run_batch = load_module("subpanel_run_batch", SUBPANEL_RUN_BATCH)
full_run_batch = load_module("full_run_batch", FULL_RUN_BATCH)


class IrFieldCoverageAuditTests(unittest.TestCase):
    def base_manifest(self) -> dict:
        return {
            "version": 1,
            "defaults": {
                "allowedProvenancePaths": ["provenance", "sourceEvidence", "confidence", "notes"],
                "highRiskPrefixes": ["panels[].plot"],
                "renderedLeafFields": ["id", "plot", "type"],
            },
            "fields": {
                "panels[].plot.axes.xAxis.line": {
                    "status": ["rendered", "preserved", "validated"],
                    "rendererEvidence": ["line[data-axis]"],
                    "validators": ["audit_explicit_axis_rendering"],
                }
            },
        }

    def audit_fixture(self, spec: dict, manifest: dict | None = None, strict: bool = True) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fixture.json"
            path.write_text(json.dumps(spec))
            return ir_field_coverage_audit.audit_specs([path], manifest or self.base_manifest(), strict_high_risk=strict)

    def test_unknown_high_risk_field_fails_in_strict_mode(self) -> None:
        spec = {"panels": [{"plot": {"id": "plot-a", "axes": {"xAxis": {"schemaOnlySemantic": True}}}}]}
        report = self.audit_fixture(spec)
        self.assertTrue(report["strictFailures"])
        self.assertTrue(any(item.path.endswith("schemaOnlySemantic") for item in report["strictFailures"]))

    def test_unknown_provenance_field_is_allowed(self) -> None:
        spec = {"panels": [{"plot": {"id": "plot-a", "provenance": {"schemaOnlySemantic": True}}}]}
        report = self.audit_fixture(spec)
        self.assertEqual(report["strictFailures"], [])

    def test_manifest_entry_with_invalid_status_fails(self) -> None:
        manifest = self.base_manifest()
        manifest["fields"]["panels[].plot.dataBbox"] = {"status": ["schema-only"]}
        errors = ir_field_coverage_audit.validate_manifest(manifest)
        self.assertTrue(any("invalid status" in error for error in errors), errors)

    def test_manifest_entry_with_unknown_validator_fails(self) -> None:
        manifest = self.base_manifest()
        manifest["fields"]["panels[].plot.dataBbox"] = {
            "status": ["validated"],
            "validators": ["not_a_validator"],
        }
        errors = ir_field_coverage_audit.validate_manifest(manifest)
        self.assertTrue(any("unknown validator" in error for error in errors), errors)

    def test_preserved_manifest_entry_requires_renderer_evidence(self) -> None:
        manifest = self.base_manifest()
        manifest["fields"]["panels[].plot.axes.xAxis.originAlignment"] = {
            "status": ["preserved"],
        }
        errors = ir_field_coverage_audit.validate_manifest(manifest)
        self.assertTrue(any("rendererEvidence" in error for error in errors), errors)


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


class LayoutQaReportTests(unittest.TestCase):
    def report_dom(self, report: dict) -> str:
        return f"""
        <html>
          <body>
            <div id="surface"><svg></svg></div>
            <script id="figure-qa-output" type="application/json">{json.dumps(report)}</script>
          </body>
        </html>
        """

    def audit(self, report: dict) -> list[str]:
        return validator.audit_layout_qa_report(Path("candidate.html"), report)

    def test_extracts_qa_report(self) -> None:
        report = {"layoutQa": {"protectedTextCollisions": []}}
        self.assertEqual(validator.extract_qa_report(self.report_dom(report)), report)

    def test_clean_layout_qa_passes(self) -> None:
        report = {
            "layoutQa": {
                "protectedTextCollisions": [],
                "clippedProtectedText": [],
                "protectedTextExclusionCollisions": [],
                "boundedMarkEscapes": [],
            }
        }
        self.assertEqual(self.audit(report), [])

    def test_protected_text_collision_fails(self) -> None:
        report = {
            "layoutQa": {
                "protectedTextCollisions": [
                    {"a": {"id": "x-tick-100"}, "b": {"id": "x-axis-label"}}
                ]
            }
        }
        errors = self.audit(report)
        self.assertTrue(any("protected text overlaps" in error for error in errors), errors)
        self.assertTrue(any("x-tick-100 vs x-axis-label" in error for error in errors), errors)

    def test_clipped_protected_text_fails(self) -> None:
        report = {"layoutQa": {"clippedProtectedText": [{"id": "panel-title"}]}}
        errors = self.audit(report)
        self.assertTrue(any("protected text is clipped" in error for error in errors), errors)

    def test_text_over_exclusion_zone_fails(self) -> None:
        report = {
            "layoutQa": {
                "protectedTextExclusionCollisions": [
                    {"text": {"id": "legend-label"}, "zone": {"id": "panel-a.plot"}}
                ]
            }
        }
        errors = self.audit(report)
        self.assertTrue(any("protected text intersects an exclusion zone" in error for error in errors), errors)
        self.assertTrue(any("legend-label over panel-a.plot" in error for error in errors), errors)

    def test_allowed_source_faithful_exception_passes_after_renderer_filtering(self) -> None:
        report = {
            "layoutQa": {
                "protectedTextCollisions": [],
                "allowedOverlaps": [
                    {"a": "source-overlap-a", "b": "source-overlap-b", "reason": "source-faithful"}
                ],
            }
        }
        self.assertEqual(self.audit(report), [])


class SideStripAndAxisContractTests(unittest.TestCase):
    def side_strip_spec(self, strip: dict | None = None) -> dict:
        return {
            "id": "fixture",
            "source": {"path": "./source.png"},
            "canvas": {"width": 200, "height": 160},
            "panels": [
                {
                    "id": "panel-c",
                    "plot": {
                        "dataBbox": {"x": 80, "y": 20, "width": 100, "height": 120},
                        "axes": {
                            "yAxis": {
                                "id": "panel-c-y-axis",
                                "sourceCalibrated": True,
                                "line": {"x1": 62, "y1": 20, "x2": 62, "y2": 140},
                            }
                        },
                        "x": {"domain": [0, 1], "ticks": []},
                        "y": {"domain": [0, 1], "ticks": []},
                    },
                    "layoutObjects": [strip or {
                        "id": "panel-c-row-block-strip",
                        "type": "sideRowBlockStrip",
                        "orientation": "vertical",
                        "bbox": {"x": 66, "y": 20, "width": 12, "height": 120},
                        "linkedAxis": "panel-c-y-axis",
                        "sharedLayoutFrame": "panel-c.plot.dataBbox",
                        "alignments": [
                            {"id": "strip-top-to-data-top", "sourceEdge": "top", "target": "panel-c.plot.dataBbox.top", "deltaPx": 0},
                            {"id": "strip-bottom-to-data-bottom", "sourceEdge": "bottom", "target": "panel-c.plot.dataBbox.bottom", "deltaPx": 0},
                            {"id": "strip-right-to-data-left", "sourceEdge": "right", "target": "panel-c.plot.dataBbox.left", "deltaPx": -2},
                        ],
                        "exclusionZone": {"paddingPx": 1},
                        "segments": [
                            {"id": "upper", "fromY": 20, "toY": 90, "fill": "#009688"},
                            {"id": "lower", "fromY": 90, "toY": 140, "fill": "#d6a300"},
                        ],
                        "separators": [{"id": "transition", "atY": 90, "stroke": "#ffffff", "strokeWidth": 1}],
                        "borders": [{"side": "right", "width": 2, "fill": "#111111"}],
                    }],
                }
            ],
        }

    def test_two_color_only_side_strip_fails_semantic_contract(self) -> None:
        strip = {
            "id": "panel-c-color-strip",
            "type": "segmentedColorbar",
            "orientation": "vertical",
            "bbox": {"x": 66, "y": 20, "width": 12, "height": 120},
            "linkedAxis": "panel-c-y-axis",
            "segments": [
                {"id": "upper", "fromY": 20, "toY": 90, "fill": "#009688"},
                {"id": "lower", "fromY": 90, "toY": 140, "fill": "#d6a300"},
            ],
        }
        errors = validator.audit_semantic_layout_contract(Path("candidate.json"), self.side_strip_spec(strip))
        self.assertTrue(any("generic segmentedColorbar" in error for error in errors), errors)
        self.assertTrue(any("separator" in error for error in errors), errors)
        self.assertTrue(any("border" in error for error in errors), errors)

    def test_declared_side_strip_component_count_must_render(self) -> None:
        spec = self.side_strip_spec({
            "id": "panel-c-row-block-strip",
            "type": "sideRowBlockStrip",
            "orientation": "vertical",
            "bbox": {"x": 66, "y": 20, "width": 12, "height": 120},
            "linkedAxis": "panel-c-y-axis",
            "sharedLayoutFrame": "panel-c.plot.dataBbox",
            "alignments": [
                {"id": "strip-top-to-data-top", "sourceEdge": "top", "target": "panel-c.plot.dataBbox.top", "deltaPx": 0},
                {"id": "strip-bottom-to-data-bottom", "sourceEdge": "bottom", "target": "panel-c.plot.dataBbox.bottom", "deltaPx": 0},
                {"id": "strip-right-to-data-left", "sourceEdge": "right", "target": "panel-c.plot.dataBbox.left", "deltaPx": -2},
            ],
            "exclusionZone": {"paddingPx": 1},
            "expectedComponentCount": 4,
            "components": [
                {"id": "dark-edge", "bbox": {"x": 66, "y": 20, "width": 2, "height": 120}, "fill": "#111111"},
                {"id": "upper", "bbox": {"x": 68, "y": 20, "width": 10, "height": 70}, "fill": "#009688"},
                {"id": "transition", "bbox": {"x": 68, "y": 90, "width": 10, "height": 2}, "fill": "#ffffff"},
                {"id": "lower", "bbox": {"x": 68, "y": 92, "width": 10, "height": 48}, "fill": "#d6a300"},
            ],
            "segments": [
                {"id": "upper", "fromY": 20, "toY": 90, "fill": "#009688"},
                {"id": "lower", "fromY": 92, "toY": 140, "fill": "#d6a300"},
            ],
            "separators": [{"id": "transition", "atY": 90, "stroke": "#ffffff", "strokeWidth": 1}],
            "borders": [{"side": "left", "width": 2, "fill": "#111111"}],
        })
        dom = """
        <html><body><div id="surface"><svg>
          <rect data-role="side-row-block-segment" data-layout-id="panel-c-row-block-strip"></rect>
          <rect data-role="side-row-block-segment" data-layout-id="panel-c-row-block-strip"></rect>
        </svg></div></body></html>
        """
        errors = validator.audit_side_strip_rendering(Path("candidate.html"), dom, spec)
        self.assertTrue(any("visible components" in error for error in errors), errors)

    def test_side_strip_components_must_render_declared_ids_and_colors(self) -> None:
        spec = self.side_strip_spec({
            "id": "panel-c-row-block-strip",
            "type": "sideRowBlockStrip",
            "orientation": "vertical",
            "bbox": {"x": 66, "y": 20, "width": 12, "height": 120},
            "linkedAxis": "panel-c-y-axis",
            "sharedLayoutFrame": "panel-c.plot.dataBbox",
            "alignments": [
                {"id": "strip-top-to-data-top", "sourceEdge": "top", "target": "panel-c.plot.dataBbox.top", "deltaPx": 0},
            ],
            "exclusionZone": {"paddingPx": 1},
            "expectedComponentCount": 4,
            "components": [
                {"id": "dark-edge", "kind": "border", "bbox": {"x": 66, "y": 20, "width": 2, "height": 120}, "fill": "#111111"},
                {"id": "upper", "kind": "segment", "bbox": {"x": 68, "y": 20, "width": 10, "height": 50}, "fill": "#009688"},
                {"id": "middle", "kind": "segment", "bbox": {"x": 68, "y": 70, "width": 10, "height": 25}, "fill": "#8fd9cf"},
                {"id": "bottom-orange", "kind": "segment", "bbox": {"x": 68, "y": 95, "width": 10, "height": 45}, "fill": "#c97908"},
            ],
            "segments": [
                {"id": "upper", "fromY": 20, "toY": 70, "fill": "#009688"},
                {"id": "middle", "fromY": 70, "toY": 95, "fill": "#8fd9cf"},
                {"id": "bottom-orange", "fromY": 95, "toY": 140, "fill": "#c97908"},
            ],
            "separators": [{"id": "transition", "atY": 95, "stroke": "#ffffff", "strokeWidth": 1}],
            "borders": [{"side": "left", "width": 2, "fill": "#111111"}],
        })
        dom = """
        <html><body><div id="surface"><svg>
          <g data-role="side-row-block-strip" data-layout-id="panel-c-row-block-strip" data-alignments="strip-top-to-data-top">
            <rect data-role="side-row-block-component" data-layout-id="panel-c-row-block-strip" data-component-id="dark-edge" fill="#111111"></rect>
            <rect data-role="side-row-block-component" data-layout-id="panel-c-row-block-strip" data-component-id="upper" fill="#009688"></rect>
            <rect data-role="side-row-block-component" data-layout-id="panel-c-row-block-strip" data-component-id="middle" fill="#8fd9cf"></rect>
            <rect data-role="side-row-block-component" data-layout-id="panel-c-row-block-strip" data-component-id="bottom-orange" fill="#d6a300"></rect>
            <line data-role="side-row-block-separator" data-layout-id="panel-c-row-block-strip"></line>
            <rect data-role="side-row-block-border" data-layout-id="panel-c-row-block-strip"></rect>
          </g>
        </svg></div></body></html>
        """
        errors = validator.audit_side_strip_rendering(Path("candidate.html"), dom, spec)
        self.assertTrue(any("bottom-orange" in error and "wrong fill" in error for error in errors), errors)

    def test_side_strip_alignment_drift_fails_contract(self) -> None:
        spec = self.side_strip_spec({
            "id": "panel-c-row-block-strip",
            "type": "sideRowBlockStrip",
            "orientation": "vertical",
            "bbox": {"x": 66, "y": 20, "width": 12, "height": 120},
            "linkedAxis": "panel-c-y-axis",
            "sharedLayoutFrame": "panel-c.plot.dataBbox",
            "alignments": [
                {"id": "strip-right-to-data-left", "sourceEdge": "right", "target": "panel-c.plot.dataBbox.left", "deltaPx": 0},
            ],
            "exclusionZone": {"paddingPx": 1},
            "segments": [
                {"id": "upper", "fromY": 20, "toY": 90, "fill": "#009688"},
                {"id": "lower", "fromY": 90, "toY": 140, "fill": "#d6a300"},
            ],
            "separators": [{"id": "transition", "atY": 90, "stroke": "#ffffff", "strokeWidth": 1}],
            "borders": [{"side": "left", "width": 2, "fill": "#111111"}],
        })
        errors = validator.audit_semantic_layout_contract(Path("candidate.json"), spec)
        self.assertTrue(any("expected delta 0px but measured -2px" in error for error in errors), errors)

    def test_x_origin_tick_alignment_to_side_strip_fails_when_drifted(self) -> None:
        spec = self.side_strip_spec()
        plot = spec["panels"][0]["plot"]
        plot["axes"]["xAxis"] = {
            "id": "panel-c-x-axis",
            "sourceCalibrated": True,
            "line": {"x1": 80, "y1": 140, "x2": 180, "y2": 140},
            "originAlignment": {
                "id": "panel-c-x-origin-strip-alignment",
                "tickValue": 0,
                "target": "panel-c-row-block-strip.right",
                "deltaPx": 0,
            },
        }
        plot["x"]["ticks"] = [
            {
                "value": 0,
                "label": "0",
                "alignment": {
                    "id": "panel-c-x-tick-0-strip-alignment",
                    "target": "panel-c-row-block-strip.right",
                    "deltaPx": 0,
                },
            }
        ]
        errors = validator.audit_semantic_layout_contract(Path("candidate.json"), spec)
        self.assertTrue(any("x tick 0 alignment expected delta 0px but measured 2px" in error for error in errors), errors)

    def test_x_origin_alignment_requires_rendered_tick_metadata(self) -> None:
        spec = self.side_strip_spec()
        plot = spec["panels"][0]["plot"]
        plot["axes"]["xAxis"] = {
            "id": "panel-c-x-axis",
            "sourceCalibrated": True,
            "line": {"x1": 80, "y1": 140, "x2": 180, "y2": 140},
            "originAlignment": {
                "id": "panel-c-x-origin-strip-alignment",
                "tickValue": 0,
                "target": "panel-c-row-block-strip.right",
                "deltaPx": 2,
            },
        }
        plot["x"]["ticks"] = [{"value": 0, "label": "0"}]
        dom = """
        <html><body>
          <div id="surface">
            <svg>
              <line data-role="axis-tick-mark" data-axis="panel-c-x-axis" data-value="0" x1="80" y1="140" x2="80" y2="147"></line>
            </svg>
          </div>
        </body></html>
        """
        errors = validator.audit_explicit_axis_rendering(Path("candidate.html"), dom, spec)
        self.assertTrue(any("missing rendered alignment target" in error for error in errors), errors)

    def test_heatmap_plot_group_missing_explicit_x_axis_fails_contract(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "id": "panel-a",
                    "plotGroups": [
                        {
                            "id": "control",
                            "type": "heatmapPlot",
                            "dataBbox": {"x": 70, "y": 91, "width": 170, "height": 354},
                            "x": {"ticks": [{"value": 0, "label": "0"}]},
                        }
                    ],
                }
            ],
        }
        errors = validator.audit_semantic_layout_contract(Path("candidate.json"), spec)
        self.assertTrue(any("explicit xAxis.line" in error for error in errors), errors)

    def test_declared_offset_x_axis_cannot_equal_data_box_bottom(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "id": "panel-a",
                    "plotGroups": [
                        {
                            "id": "control",
                            "type": "heatmapPlot",
                            "dataBbox": {"x": 70, "y": 91, "width": 170, "height": 354},
                            "axes": {
                                "xAxis": {
                                    "id": "control-x-axis",
                                    "sourceCalibrated": True,
                                    "offsetFromDataBbox": {"edge": "bottom", "pixels": 6},
                                    "line": {"x1": 70, "y1": 445, "x2": 240, "y2": 445},
                                    "tickLabelBand": {"id": "control.xAxis.tickLabelBand", "x": 70, "y": 445, "width": 170, "height": 49},
                                }
                            },
                            "x": {"ticks": [{"value": 0, "label": "0"}]},
                        }
                    ],
                }
            ],
        }
        errors = validator.audit_semantic_layout_contract(Path("candidate.json"), spec)
        self.assertTrue(any("line is still derived from dataBbox edge" in error for error in errors), errors)

    def test_declared_offset_x_axis_passes_when_line_is_offset(self) -> None:
        spec = {
            "id": "reference-01-place-code-opto-A",
            "panels": [
                {
                    "id": "panel-a",
                    "plotGroups": [
                        {
                            "id": "control",
                            "type": "heatmapPlot",
                            "dataBbox": {"x": 70, "y": 91, "width": 170, "height": 354},
                            "axes": {
                                "xAxis": {
                                    "id": "control-x-axis",
                                    "sourceCalibrated": True,
                                    "offsetFromDataBbox": {"edge": "bottom", "pixels": 6},
                                    "line": {"x1": 70, "y1": 451, "x2": 240, "y2": 451},
                                    "tickLabelBand": {"id": "control.xAxis.tickLabelBand", "x": 70, "y": 451, "width": 170, "height": 49},
                                }
                            },
                            "x": {"ticks": [{"value": 0, "label": "0"}]},
                        }
                    ],
                }
            ],
        }
        self.assertEqual(validator.audit_semantic_layout_contract(Path("candidate.json"), spec), [])

    def test_text_over_side_strip_exclusion_zone_fails(self) -> None:
        report = {
            "layoutQa": {
                "protectedTextExclusionCollisions": [
                    {"text": {"id": "panel-c-y-tick-384-label"}, "zone": {"id": "panel-c-row-block-strip"}}
                ]
            }
        }
        errors = validator.audit_layout_qa_report(Path("candidate.html"), report)
        self.assertTrue(any("protected text intersects an exclusion zone" in error for error in errors), errors)

    def test_neighboring_small_multiple_tick_labels_collide_fails(self) -> None:
        report = {
            "layoutQa": {
                "protectedTextCollisions": [
                    {"a": {"id": "plot-1-x-tick-100-label"}, "b": {"id": "plot-2-x-tick-0-label"}}
                ]
            }
        }
        errors = validator.audit_layout_qa_report(Path("candidate.html"), report)
        self.assertTrue(any("plot-1-x-tick-100-label vs plot-2-x-tick-0-label" in error for error in errors), errors)

    def test_axis_derived_from_data_box_instead_of_explicit_offset_axis_fails(self) -> None:
        spec = self.side_strip_spec()
        dom = """
        <html><body>
          <div id="surface">
            <svg>
              <line data-role="y-axis" data-axis="panel-c-y-axis" x1="80" y1="20" x2="80" y2="140"></line>
            </svg>
          </div>
        </body></html>
        """
        errors = validator.audit_explicit_axis_rendering(Path("candidate.html"), dom, spec)
        self.assertTrue(any("coordinates that do not match" in error for error in errors), errors)

    def test_complete_side_strip_rendering_passes_counts(self) -> None:
        spec = self.side_strip_spec()
        dom = """
        <html><body>
          <div id="surface">
            <svg>
              <line data-role="y-axis" data-axis="panel-c-y-axis" x1="62" y1="20" x2="62" y2="140"></line>
              <g data-role="side-row-block-strip" data-layout-id="panel-c-row-block-strip" data-alignments="strip-top-to-data-top strip-bottom-to-data-bottom strip-right-to-data-left">
                <rect data-role="side-row-block-segment" data-layout-id="panel-c-row-block-strip"></rect>
                <rect data-role="side-row-block-segment" data-layout-id="panel-c-row-block-strip"></rect>
                <line data-role="side-row-block-separator" data-layout-id="panel-c-row-block-strip"></line>
                <rect data-role="side-row-block-border" data-layout-id="panel-c-row-block-strip"></rect>
              </g>
            </svg>
          </div>
        </body></html>
        """
        self.assertEqual(validator.audit_semantic_layout_contract(Path("candidate.json"), spec), [])
        self.assertEqual(validator.audit_explicit_axis_rendering(Path("candidate.html"), dom, spec), [])
        self.assertEqual(validator.audit_side_strip_rendering(Path("candidate.html"), dom, spec), [])

    def test_side_strip_alignments_require_dom_metadata(self) -> None:
        spec = self.side_strip_spec()
        dom = """
        <html><body>
          <div id="surface">
            <svg>
              <g data-role="side-row-block-strip" data-layout-id="panel-c-row-block-strip">
                <rect data-role="side-row-block-segment" data-layout-id="panel-c-row-block-strip"></rect>
                <rect data-role="side-row-block-segment" data-layout-id="panel-c-row-block-strip"></rect>
                <line data-role="side-row-block-separator" data-layout-id="panel-c-row-block-strip"></line>
                <rect data-role="side-row-block-border" data-layout-id="panel-c-row-block-strip"></rect>
              </g>
            </svg>
          </div>
        </body></html>
        """
        errors = validator.audit_side_strip_rendering(Path("candidate.html"), dom, spec)
        self.assertTrue(any("missing rendered alignment metadata" in error for error in errors), errors)


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
