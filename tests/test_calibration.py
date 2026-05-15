"""Unit tests for vision.calibration. No camera/robot/opencv required."""

from __future__ import annotations

import json
import math
import os
import tempfile
import unittest

import numpy as np

from vision.calibration import (
    Calibration,
    CalibrationPoint,
    Calibrator,
    PolyFit,
    SCHEMA_VERSION,
    ToolCenterOffset,
    WorkZone,
    auto_select_degree,
    compute_tool_center_offset,
    derive_work_zone,
    detection_center,
    fit_polynomial,
    generate_grid_targets,
    infer_missing_grid_corner_from_edge_points,
    intersect_infinite_lines_2d,
    load_calibration,
    pixel_to_robot_xy,
    robot_bounds_from_pixel_rect,
    robot_bounds_from_quad_clicks,
    save_calibration,
)


def _synth_points_from_known_poly(coeffs_x, coeffs_y, uv_pairs):
    """Build CalibrationPoints whose (X, Y) come from a known degree-2 poly."""

    def eval_at(c, u, v):
        a0, a1, a2, a3, a4, a5 = c
        return a0 + a1 * u + a2 * v + a3 * u * u + a4 * u * v + a5 * v * v

    return [
        CalibrationPoint(
            u=float(u),
            v=float(v),
            x_mm=float(eval_at(coeffs_x, u, v)),
            y_mm=float(eval_at(coeffs_y, u, v)),
        )
        for (u, v) in uv_pairs
    ]


class FitTests(unittest.TestCase):
    def test_recovers_known_poly2(self):
        # Truth coefficients (a0..a5)
        truth_x = [-200.0, 0.5, 0.0, 1e-4, 0.0, 0.0]
        truth_y = [-200.0, 0.0, 0.5, 0.0, 0.0, 1e-4]

        # 4x4 grid in pixel space, well-spread to make the fit well-conditioned.
        uv_pairs = [(u, v) for u in (50, 200, 400, 600) for v in (50, 200, 400, 600)]
        pts = _synth_points_from_known_poly(truth_x, truth_y, uv_pairs)

        fit = fit_polynomial(pts, degree=2)

        np.testing.assert_allclose(fit.coeffs_x, truth_x, atol=1e-6)
        np.testing.assert_allclose(fit.coeffs_y, truth_y, atol=1e-6)
        self.assertLess(fit.rms_residual_mm, 1e-6)

    def test_apply_matches_truth_on_new_points(self):
        truth_x = [10.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        truth_y = [-5.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        uv_pairs = [(u, v) for u in (0, 100, 200, 300) for v in (0, 100, 200, 300)]
        pts = _synth_points_from_known_poly(truth_x, truth_y, uv_pairs)

        fit = fit_polynomial(pts, degree=2)

        x, y = fit.apply(150.0, 50.0)
        self.assertAlmostEqual(x, 10.0 + 150.0, places=5)
        self.assertAlmostEqual(y, -5.0 + 50.0, places=5)

    def test_minimum_points_rejected(self):
        # Degree 2 needs >= 6 points.
        pts = [
            CalibrationPoint(u=u, v=v, x_mm=u, y_mm=v)
            for (u, v) in [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0)]
        ]
        with self.assertRaises(ValueError):
            fit_polynomial(pts, degree=2)

    def test_degree_3_requires_more_points(self):
        # Degree 3 needs >= 10 points.
        pts = [
            CalibrationPoint(u=float(i), v=float(i), x_mm=float(i), y_mm=float(i))
            for i in range(9)
        ]
        with self.assertRaises(ValueError):
            fit_polynomial(pts, degree=3)

    def test_invalid_degree(self):
        pts = [
            CalibrationPoint(u=float(i), v=float(i), x_mm=float(i), y_mm=float(i))
            for i in range(20)
        ]
        with self.assertRaises(ValueError):
            fit_polynomial(pts, degree=4)


class WorkZoneTests(unittest.TestCase):
    def test_contains_inside_and_outside(self):
        zone = WorkZone(x_min=-100, x_max=100, y_min=-50, y_max=50)
        self.assertTrue(zone.contains(0, 0))
        self.assertTrue(zone.contains(-100, 50))  # boundary inclusive
        self.assertFalse(zone.contains(100.01, 0))
        self.assertFalse(zone.contains(0, 60))

    def test_subset_and_clip(self):
        outer = WorkZone(x_min=-100, x_max=100, y_min=-100, y_max=100)
        inner = WorkZone(x_min=-10, x_max=10, y_min=-5, y_max=5)
        self.assertTrue(inner.is_subset_of(outer))
        self.assertFalse(outer.is_subset_of(inner))

        half = WorkZone(x_min=0, x_max=100, y_min=0, y_max=100)
        clip = inner.clipped_to(half)
        self.assertEqual(clip.x_min, 0.0)
        self.assertEqual(clip.x_max, 10.0)
        self.assertEqual(clip.y_min, 0.0)
        self.assertEqual(clip.y_max, 5.0)

    def test_derive_with_margin(self):
        # 200x200 grid centred at origin; 20 mm margin -> 160x160 zone.
        pts = [
            CalibrationPoint(u=0, v=0, x_mm=x, y_mm=y)
            for x in (-100.0, 0.0, 100.0)
            for y in (-100.0, 0.0, 100.0)
        ]
        zone = derive_work_zone(pts, margin_mm=20.0)
        self.assertEqual(zone.x_min, -80.0)
        self.assertEqual(zone.x_max, 80.0)
        self.assertEqual(zone.y_min, -80.0)
        self.assertEqual(zone.y_max, 80.0)

    def test_derive_clamped_to_hardware_limits(self):
        pts = [
            CalibrationPoint(u=0, v=0, x_mm=x, y_mm=y)
            for x in (-1000.0, 1000.0)
            for y in (-1000.0, 1000.0)
        ]
        zone = derive_work_zone(pts, margin_mm=0.0)
        self.assertEqual(zone.x_min, -280.0)
        self.assertEqual(zone.x_max, 280.0)
        self.assertEqual(zone.y_min, -280.0)
        self.assertEqual(zone.y_max, 280.0)

    def test_derive_empty_zone_raises(self):
        # Tiny grid + huge margin -> no inner zone.
        pts = [
            CalibrationPoint(u=0, v=0, x_mm=x, y_mm=y)
            for x in (-5.0, 5.0)
            for y in (-5.0, 5.0)
        ]
        with self.assertRaises(ValueError):
            derive_work_zone(pts, margin_mm=20.0)


class CvKeyHelperTests(unittest.TestCase):
    def test_confirm_redo_quit_masks(self):
        from vision.calibration.ui import _cv_key_confirm, _cv_key_quit, _cv_key_redo

        self.assertTrue(_cv_key_confirm(ord("y")))
        self.assertTrue(_cv_key_confirm(ord("Y")))
        self.assertTrue(_cv_key_confirm(13))
        self.assertTrue(_cv_key_confirm(ord(" ")))
        self.assertFalse(_cv_key_confirm(-1))
        self.assertTrue(_cv_key_quit(ord("q")))
        self.assertTrue(_cv_key_quit(27))
        self.assertTrue(_cv_key_redo(ord("N")))


class PartialMasterGeometryTests(unittest.TestCase):
    def test_infer_br_axis_aligned_pixel_square(self):
        br = infer_missing_grid_corner_from_edge_points(
            tr_uv=(100.0, 0.0),
            bl_uv=(0.0, 100.0),
            aux_right_edge_uv=(100.0, 55.0),
            aux_top_edge_uv=(40.0, 100.0),
        )
        self.assertAlmostEqual(br[0], 100.0, places=9)
        self.assertAlmostEqual(br[1], 100.0, places=9)

    def test_infer_br_skewed_parallelogram_edges(self):
        br = infer_missing_grid_corner_from_edge_points(
            tr_uv=(120.0, 30.0),
            bl_uv=(40.0, 120.0),
            aux_right_edge_uv=(135.0, 85.0),
            aux_top_edge_uv=(95.0, 130.0),
        )
        self.assertAlmostEqual(br[0], 150.0, places=9)
        self.assertAlmostEqual(br[1], 140.0, places=9)

    def test_parallel_lines_raise(self):
        with self.assertRaises(ValueError):
            intersect_infinite_lines_2d((0.0, 0.0), (10.0, 0.0), (0.0, 1.0), (25.0, 1.0))


class GridTargetsTests(unittest.TestCase):
    def test_3x3_centred_at_origin(self):
        targets = generate_grid_targets(rows=3, cols=3, spacing_mm=100.0)
        self.assertEqual(len(targets), 9)
        # First (top-left): X=-100, Y=-100. Last: X=+100, Y=+100.
        self.assertEqual(targets[0], (-100.0, -100.0))
        self.assertEqual(targets[-1], (100.0, 100.0))

    def test_offset_grid(self):
        targets = generate_grid_targets(
            rows=2, cols=2, spacing_mm=50.0, center_x_mm=10.0, center_y_mm=-20.0
        )
        # 2x2 -> half-extent 25.
        self.assertEqual(targets[0], (-15.0, -45.0))
        self.assertEqual(targets[-1], (35.0, 5.0))

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            generate_grid_targets(rows=0, cols=3, spacing_mm=10.0)


class ManualWizardHelpersTests(unittest.TestCase):
    def test_manual_stage_plan_defaults(self):
        from vision.calibration.ui import _manual_stage_plan

        stages = _manual_stage_plan()
        self.assertEqual([stage.label for stage in stages], ["master grid", "slave grid", "robot point"])
        self.assertEqual([stage.count for stage in stages], [4, 4, 1])

    def test_slave_robot_stages_defaults(self):
        from vision.calibration.ui import _slave_robot_stages

        stages = _slave_robot_stages()
        self.assertEqual([stage.label for stage in stages], ["Slave grid (step 2)", "Robot TCP reference (step 3)"])
        self.assertEqual([stage.count for stage in stages], [4, 1])

    def test_manual_stage_plan_rejects_invalid_counts(self):
        from vision.calibration.ui import _manual_stage_plan

        with self.assertRaises(ValueError):
            _manual_stage_plan(master_points=0)

    def test_parse_robot_xy(self):
        from vision.calibration.ui import _parse_robot_xy

        self.assertEqual(_parse_robot_xy("10,20"), (10.0, 20.0))
        self.assertEqual(_parse_robot_xy("-5  12.5"), (-5.0, 12.5))
        with self.assertRaises(ValueError):
            _parse_robot_xy("not numbers")


class IORoundTripTests(unittest.TestCase):
    def _build_calibration(self) -> Calibration:
        pts = [
            CalibrationPoint(u=u, v=v, x_mm=float(u - 320), y_mm=float(v - 240))
            for u in (100, 320, 540)
            for v in (80, 240, 400)
        ]
        fit = fit_polynomial(pts, degree=2)
        zone = derive_work_zone(pts, margin_mm=10.0)
        return Calibration(
            image_size=(640, 480),
            fit=fit,
            points=pts,
            work_zone=zone,
            active_zone=zone,
            pick_height_z_mm=-940.0,
            notes="unit test",
        )

    def test_save_and_load_round_trip(self):
        cal = self._build_calibration()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            save_calibration(path, cal)
            loaded = load_calibration(path)

        self.assertEqual(loaded.image_size, cal.image_size)
        self.assertEqual(loaded.fit.degree, cal.fit.degree)
        np.testing.assert_allclose(loaded.fit.coeffs_x, cal.fit.coeffs_x, atol=1e-9)
        np.testing.assert_allclose(loaded.fit.coeffs_y, cal.fit.coeffs_y, atol=1e-9)
        self.assertAlmostEqual(loaded.fit.rms_residual_mm, cal.fit.rms_residual_mm)
        self.assertEqual(loaded.work_zone.to_dict(), cal.work_zone.to_dict())
        self.assertEqual(loaded.master_workspace.to_dict(), cal.master_workspace.to_dict())
        self.assertEqual(loaded.active_zone.to_dict(), cal.active_zone.to_dict())
        self.assertEqual(loaded.tool_center_offset.to_dict(), cal.tool_center_offset.to_dict())
        self.assertEqual(loaded.pick_height_z_mm, cal.pick_height_z_mm)
        self.assertEqual(len(loaded.points), len(cal.points))

    def test_schema_version_mismatch(self):
        cal = self._build_calibration()
        d = cal.to_dict()
        d["schema_version"] = SCHEMA_VERSION + 1
        with self.assertRaises(ValueError):
            Calibration.from_dict(d)

    def test_image_size_mismatch_raises(self):
        cal = self._build_calibration()
        with self.assertRaises(ValueError):
            pixel_to_robot_xy(cal, 100, 100, image_size=(1280, 720))

    def test_image_size_match_passes(self):
        cal = self._build_calibration()
        # No exception, returns floats.
        x, y = pixel_to_robot_xy(cal, 320, 240, image_size=(640, 480))
        self.assertTrue(math.isfinite(x))
        self.assertTrue(math.isfinite(y))

    def test_old_schema_without_new_fields_still_loads(self):
        cal = self._build_calibration()
        data = cal.to_dict()
        data.pop("active_zone", None)
        data.pop("tool_center_offset", None)
        data.pop("master_workspace", None)
        data["schema_version"] = 1

        loaded = Calibration.from_dict(data)

        self.assertEqual(loaded.work_zone.to_dict(), cal.work_zone.to_dict())
        self.assertIsNone(loaded.active_zone)
        self.assertEqual(loaded.effective_active_zone().to_dict(), cal.work_zone.to_dict())
        self.assertEqual(loaded.tool_center_offset.to_dict(), ToolCenterOffset().to_dict())

    def test_active_zone_key_absent_means_implicit_work_zone(self):
        cal = self._build_calibration()
        data = cal.to_dict()
        data.pop("active_zone", None)
        loaded = Calibration.from_dict(data)
        self.assertIsNone(loaded.active_zone)

    def test_to_dict_omits_none_active_zone(self):
        cal = self._build_calibration()
        cal.active_zone = None
        self.assertNotIn("active_zone", cal.to_dict())


class AutoDegreeTests(unittest.TestCase):
    def test_below_threshold(self):
        self.assertEqual(auto_select_degree(9), 2)
        self.assertEqual(auto_select_degree(15), 2)

    def test_at_and_above_threshold(self):
        self.assertEqual(auto_select_degree(16), 3)
        self.assertEqual(auto_select_degree(25), 3)


class PolyFitJSONTests(unittest.TestCase):
    def test_unsupported_type_rejected(self):
        with self.assertRaises(ValueError):
            PolyFit.from_dict({"type": "rbf", "coeffs_x": [], "coeffs_y": [], "rms_residual_mm": 0})

    def test_coeff_shape_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            PolyFit.from_dict(
                {
                    "type": "poly2",
                    "coeffs_x": [1.0, 2.0],
                    "coeffs_y": [1.0, 2.0],
                    "rms_residual_mm": 0,
                }
            )


def _make_calibration() -> Calibration:
    """Build a calibration whose forward transform is a clean affine for tests:
    pixel -> robot mm with X = u - 320, Y = v - 240, work zone ±100 mm."""
    pts = [
        CalibrationPoint(u=u, v=v, x_mm=float(u - 320), y_mm=float(v - 240))
        for u in (220, 320, 420)
        for v in (140, 240, 340)
    ]
    fit = fit_polynomial(pts, degree=2)
    zone = WorkZone(x_min=-90, x_max=90, y_min=-90, y_max=90)
    return Calibration(
        image_size=(640, 480),
        fit=fit,
        points=pts,
        work_zone=zone,
        active_zone=zone,
        pick_height_z_mm=-940.0,
        notes="unit test calibration",
    )


def _make_calibration_with_offset_and_active_zone() -> Calibration:
    pts = [
        CalibrationPoint(u=u, v=v, x_mm=float(u - 320), y_mm=float(v - 240))
        for u in (220, 320, 420)
        for v in (140, 240, 340)
    ]
    fit = fit_polynomial(pts, degree=2)
    work_zone = WorkZone(x_min=-120, x_max=120, y_min=-120, y_max=120)
    active_zone = WorkZone(x_min=-60, x_max=60, y_min=-60, y_max=60)
    return Calibration(
        image_size=(640, 480),
        fit=fit,
        points=pts,
        work_zone=work_zone,
        active_zone=active_zone,
        tool_center_offset=ToolCenterOffset(x_mm=-5.0, y_mm=2.0),
        pick_height_z_mm=-940.0,
        notes="unit test calibration with offset",
    )


class DetectionCenterTests(unittest.TestCase):
    def test_returns_center(self):
        self.assertEqual(detection_center({"bbox_xyxy": [10, 20, 30, 40]}), (20.0, 30.0))

    def test_missing_bbox_returns_none(self):
        self.assertIsNone(detection_center({}))

    def test_malformed_bbox_returns_none(self):
        self.assertIsNone(detection_center({"bbox_xyxy": [10, 20]}))
        self.assertIsNone(detection_center({"bbox_xyxy": "not a list"}))
        self.assertIsNone(detection_center({"bbox_xyxy": [None, 0, 0, 0]}))

    def test_non_dict_returns_none(self):
        self.assertIsNone(detection_center(None))
        self.assertIsNone(detection_center([1, 2, 3, 4]))


class CalibratorTests(unittest.TestCase):
    def test_load_and_round_trip(self):
        cal = _make_calibration()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            save_calibration(path, cal)
            wrap = Calibrator.load(path)
        self.assertEqual(wrap.image_size, (640, 480))
        self.assertEqual(wrap.pick_height_z_mm, -940.0)

    def test_transform_pixel(self):
        wrap = Calibrator(_make_calibration())
        x, y = wrap.transform_pixel(370, 290)
        self.assertAlmostEqual(x, 50.0, places=5)
        self.assertAlmostEqual(y, 50.0, places=5)

    def test_transform_pixel_applies_tool_center_offset(self):
        wrap = Calibrator(_make_calibration_with_offset_and_active_zone())
        x, y = wrap.transform_pixel(370, 290)
        self.assertAlmostEqual(x, 45.0, places=5)
        self.assertAlmostEqual(y, 52.0, places=5)

    def test_active_zone_filtering_does_not_change_coordinates(self):
        wrap = Calibrator(_make_calibration_with_offset_and_active_zone())
        x_raw, y_raw = pixel_to_robot_xy(
            wrap.calibration, 370, 290, image_size=(640, 480)
        )
        x, y = wrap.transform_pixel(370, 290)
        self.assertAlmostEqual(x_raw, 50.0, places=5)
        self.assertAlmostEqual(y_raw, 50.0, places=5)
        self.assertAlmostEqual(x, 45.0, places=5)
        self.assertAlmostEqual(y, 52.0, places=5)
        self.assertTrue(wrap.is_inside_zone(x, y))

    def test_transform_pixel_image_size_mismatch_raises(self):
        wrap = Calibrator(_make_calibration())
        with self.assertRaises(ValueError):
            wrap.transform_pixel(370, 290, image_size=(1280, 720))

    def test_transform_detection_inside_zone(self):
        wrap = Calibrator(_make_calibration())
        det = {"bbox_xyxy": [360, 280, 380, 300]}  # centre (370, 290) -> (50, 50)
        result = wrap.transform_detection(det)
        self.assertIsNotNone(result)
        x, y, z = result
        self.assertAlmostEqual(x, 50.0, places=5)
        self.assertAlmostEqual(y, 50.0, places=5)
        self.assertEqual(z, -940.0)

    def test_transform_detection_outside_zone_returns_none(self):
        wrap = Calibrator(_make_calibration_with_offset_and_active_zone())
        det = {"bbox_xyxy": [10, 10, 30, 30]}  # centre (20, 20) -> (-300, -220) outside
        self.assertIsNone(wrap.transform_detection(det))

    def test_transform_detection_no_bbox_returns_none(self):
        wrap = Calibrator(_make_calibration())
        self.assertIsNone(wrap.transform_detection({}))


class ToolCenterOffsetRegressionTests(unittest.TestCase):
    def test_additive_runtime_matches_controller_example(self):
        cal = _make_calibration()
        off = compute_tool_center_offset(cal, 370.0, 290.0, 100.0, 50.0)
        self.assertAlmostEqual(off.x_mm, 50.0, places=4)
        self.assertAlmostEqual(off.y_mm, 0.0, places=4)
        cal.tool_center_offset = off
        wrap = Calibrator(cal)
        x, y = wrap.transform_pixel(370, 290)
        self.assertAlmostEqual(x, 100.0, places=4)
        self.assertAlmostEqual(y, 50.0, places=4)

    def test_robot_bounds_from_pixels_non_empty(self):
        cal = _make_calibration()
        z = robot_bounds_from_pixel_rect(cal, 360.0, 280.0, 380.0, 300.0)
        self.assertLess(z.x_min, z.x_max)
        self.assertLess(z.y_min, z.y_max)
        mid_x = 0.5 * (z.x_min + z.x_max)
        mid_y = 0.5 * (z.y_min + z.y_max)
        self.assertAlmostEqual(mid_x, 50.0, delta=0.5)
        self.assertAlmostEqual(mid_y, 50.0, delta=0.5)


class AnnotateBoardMmTests(unittest.TestCase):
    """Integration tests for vision.commands._annotate_board_mm.

    Imported lazily because vision.commands pulls in vision.vision -> pyzed
    paths; the import works without ZED but is heavier than the rest of the
    test module.
    """

    def _annotate(self):
        from vision.commands import _annotate_board_mm
        return _annotate_board_mm

    def test_annotates_inside_and_outside_zone(self):
        annotate = self._annotate()
        wrap = Calibrator(_make_calibration_with_offset_and_active_zone())
        detections = [
            {"label": "apple", "bbox_xyxy": [360, 280, 380, 300]},  # centre (370, 290) -> (50, 50)
            {"label": "apple", "bbox_xyxy": [10, 10, 30, 30]},      # centre (20, 20) -> way outside
            {"label": "apple"},                                      # no bbox
        ]
        annotate(detections, wrap, image_size=(640, 480))

        b0 = detections[0]["board_xy_mm"]
        self.assertAlmostEqual(b0["x_raw"], 50.0, places=2)
        self.assertAlmostEqual(b0["y_raw"], 50.0, places=2)
        self.assertAlmostEqual(b0["x"], 45.0, places=2)
        self.assertAlmostEqual(b0["y"], 52.0, places=2)
        self.assertTrue(b0["inside_zone"])
        self.assertEqual(b0["frame"], "robot_master_mm")
        self.assertEqual(b0["zone_mode"], "active_zone_filter_only")
        self.assertTrue(b0["center_correction_applied"])

        self.assertFalse(detections[1]["board_xy_mm"]["inside_zone"])
        self.assertIsNotNone(detections[1]["board_xy_mm"]["x"])  # mm still emitted
        self.assertNotIn("error", detections[1]["board_xy_mm"])

        self.assertIsNone(detections[2]["board_xy_mm"]["x"])
        self.assertIsNone(detections[2]["board_xy_mm"]["y"])
        self.assertIsNone(detections[2]["board_xy_mm"]["x_raw"])
        self.assertIsNone(detections[2]["board_xy_mm"]["y_raw"])
        self.assertFalse(detections[2]["board_xy_mm"]["inside_zone"])

    def test_image_size_mismatch_marks_error(self):
        annotate = self._annotate()
        wrap = Calibrator(_make_calibration())
        detections = [{"label": "apple", "bbox_xyxy": [360, 280, 380, 300]}]
        annotate(detections, wrap, image_size=(1280, 720))
        self.assertEqual(detections[0]["board_xy_mm"]["error"], "image_size_mismatch")
        self.assertIsNone(detections[0]["board_xy_mm"]["x"])
        self.assertIsNone(detections[0]["board_xy_mm"]["y"])
        self.assertIsNone(detections[0]["board_xy_mm"]["x_raw"])
        self.assertIsNone(detections[0]["board_xy_mm"]["y_raw"])
        self.assertFalse(detections[0]["board_xy_mm"]["inside_zone"])

    def test_no_calibrator_is_noop(self):
        annotate = self._annotate()
        detections = [{"label": "apple", "bbox_xyxy": [360, 280, 380, 300]}]
        annotate(detections, None, image_size=(640, 480))
        self.assertNotIn("board_xy_mm", detections[0])


def _has_cv2_for_quality() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_cv2_for_quality(), "opencv-python not installed")
class AnnotateQualityTests(unittest.TestCase):
    """Integration tests for vision.commands._annotate_quality."""

    def _annotate(self):
        from vision.commands import _annotate_quality
        return _annotate_quality

    def _orange(self, size: int = 200):
        import numpy as np
        img = np.zeros((size, size, 3), dtype=np.uint8)
        img[:, :] = (50, 140, 240)
        return img

    def test_attaches_quality_only_to_produce(self):
        annotate = self._annotate()
        img = self._orange()
        detections = [
            {"detection_type": "produce", "label": "orange",
             "confidence": 80.0, "bbox_xyxy": [10, 10, 190, 190]},
            {"detection_type": "human", "label": "person",
             "confidence": 95.0, "bbox_xyxy": [10, 10, 190, 190]},
        ]
        annotate(detections, img)
        self.assertIn("quality", detections[0])
        self.assertIn(detections[0]["quality"]["grade"],
                      {"excellent", "good", "fair", "poor", "reject"})
        self.assertNotIn("quality", detections[1])

    def test_handles_missing_bbox(self):
        annotate = self._annotate()
        img = self._orange()
        detections = [{"detection_type": "produce", "label": "orange",
                       "confidence": 80.0}]
        annotate(detections, img)
        # grade_detection returns None for missing bbox, so no quality key set.
        self.assertNotIn("quality", detections[0])

    def test_no_frame_is_noop(self):
        annotate = self._annotate()
        detections = [{"detection_type": "produce", "label": "orange",
                       "confidence": 80.0, "bbox_xyxy": [10, 10, 190, 190]}]
        annotate(detections, None)
        self.assertNotIn("quality", detections[0])


@unittest.skipUnless(_has_cv2_for_quality(), "opencv-python not installed")
class RefinedDetectionCenterTests(unittest.TestCase):
    """Sphere-aware bbox-centre refinement for top-down near-spherical produce."""

    def _import(self):
        from vision.calibration.runtime import refined_detection_center
        return refined_detection_center

    def _orange_disc(self, size: int = 200, cx: int = 100, cy: int = 100, r: int = 40):
        import cv2
        import numpy as np
        img = np.full((size, size, 3), 180, dtype=np.uint8)
        cv2.circle(img, (cx, cy), r, (0, 140, 240), thickness=-1)
        return img

    def test_circle_fit_recovers_disc_centre(self):
        refined = self._import()
        img = self._orange_disc()
        # Loose bbox: arithmetic-mean centre is (115, 115); disc centre is (100, 100).
        d = {"bbox_xyxy": [50, 50, 180, 180]}
        u, v = refined(d, img)
        self.assertAlmostEqual(u, 100.0, delta=3.0)
        self.assertAlmostEqual(v, 100.0, delta=3.0)
        self.assertEqual(d["center_method"], "circle_fit")
        self.assertEqual(d["center_uv"], [u, v])

    def test_uniform_crop_falls_back_to_bbox_centre(self):
        import numpy as np
        refined = self._import()
        img = np.full((200, 200, 3), 180, dtype=np.uint8)
        d = {"bbox_xyxy": [50, 50, 180, 180]}
        u, v = refined(d, img)
        self.assertEqual((u, v), (115.0, 115.0))
        self.assertEqual(d["center_method"], "bbox_center")

    def test_no_frame_falls_back_to_bbox_centre(self):
        refined = self._import()
        d = {"bbox_xyxy": [50, 50, 180, 180]}
        u, v = refined(d, None)
        self.assertEqual((u, v), (115.0, 115.0))
        self.assertEqual(d["center_method"], "bbox_center")

    def test_missing_bbox_returns_none(self):
        refined = self._import()
        d = {"label": "orange"}
        self.assertIsNone(refined(d, None))
        self.assertNotIn("center_method", d)


class QuadZoneTests(unittest.TestCase):
    """Tests for 4-click slave zone: robot_bounds_from_quad_clicks."""

    def test_quad_zone_bounding_box_matches_4_corners(self):
        cal = _make_calibration()
        # Calibration: X = u - 320, Y = v - 240.  Pick 4 pixel corners.
        # pixel (270,190) -> (-50,-50), (370,190) -> (50,-50),
        # (370,290) -> (50,50),  (270,290) -> (-50,50)
        corners = [(270.0, 190.0), (370.0, 190.0), (370.0, 290.0), (270.0, 290.0)]
        zone = robot_bounds_from_quad_clicks(cal, corners)
        self.assertAlmostEqual(zone.x_min, -50.0, places=4)
        self.assertAlmostEqual(zone.x_max,  50.0, places=4)
        self.assertAlmostEqual(zone.y_min, -50.0, places=4)
        self.assertAlmostEqual(zone.y_max,  50.0, places=4)

    def test_quad_zone_coordinates_stay_in_master_frame(self):
        """Active zone must never change the master-frame coordinates of a point."""
        cal = _make_calibration()
        corners = [(270.0, 190.0), (370.0, 190.0), (370.0, 290.0), (270.0, 290.0)]
        zone = robot_bounds_from_quad_clicks(cal, corners)
        cal.active_zone = zone
        # Point inside the zone
        x, y = pixel_to_robot_xy(cal, 320.0, 240.0)  # -> (0, 0)
        self.assertAlmostEqual(x, 0.0, places=4)
        self.assertAlmostEqual(y, 0.0, places=4)
        self.assertTrue(zone.contains(x, y))

    def test_quad_zone_fewer_than_3_corners_raises(self):
        cal = _make_calibration()
        with self.assertRaises(ValueError):
            robot_bounds_from_quad_clicks(cal, [(100.0, 100.0), (200.0, 200.0)])

    def test_labels_object_type_is_now_skip(self):
        from vision.labels import classify_yolo_label
        dtype, _ = classify_yolo_label("bicycle")
        self.assertEqual(dtype, "skip")
        dtype2, _ = classify_yolo_label("car")
        self.assertEqual(dtype2, "skip")
        dtype3, _ = classify_yolo_label("chair")
        self.assertEqual(dtype3, "skip")

    def test_labels_produce_and_human_still_pass(self):
        from vision.labels import classify_yolo_label
        dtype, _ = classify_yolo_label("apple")
        self.assertEqual(dtype, "produce")
        dtype2, _ = classify_yolo_label("person")
        self.assertEqual(dtype2, "human")


class WizardArgTests(unittest.TestCase):
    """Argument-parser smoke tests for --wizard (no OpenCV / camera required)."""

    def _parser(self):
        from vision.calibration.ui import _build_arg_parser
        return _build_arg_parser()

    def test_wizard_flag_accepted(self):
        args = self._parser().parse_args(["--image", "dummy.jpg", "--wizard"])
        self.assertTrue(args.wizard)

    def test_wizard_defaults_to_false(self):
        args = self._parser().parse_args(["--image", "dummy.jpg"])
        self.assertFalse(args.wizard)

    def test_wizard_with_live(self):
        args = self._parser().parse_args(["--live", "--wizard"])
        self.assertTrue(args.wizard)
        self.assertTrue(args.live)

    def test_wizard_accepts_grid_and_spacing(self):
        args = self._parser().parse_args(
            ["--image", "dummy.jpg", "--wizard", "--grid", "4x4", "--spacing", "80"]
        )
        self.assertTrue(args.wizard)
        self.assertEqual(args.grid, (4, 4))
        self.assertAlmostEqual(args.spacing, 80.0)


if __name__ == "__main__":
    unittest.main()
