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
    WorkZone,
    auto_select_degree,
    build_square_calibration_points,
    derive_work_zone,
    detection_center,
    fit_polynomial,
    generate_grid_targets,
    infer_hidden_corner,
    intersect_infinite_lines_2d,
    load_calibration,
    pixel_to_robot_xy,
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


# ----- fit math ---------------------------------------------------------

class FitTests(unittest.TestCase):
    def test_recovers_known_poly2(self):
        truth_x = [-200.0, 0.5, 0.0, 1e-4, 0.0, 0.0]
        truth_y = [-200.0, 0.0, 0.5, 0.0, 0.0, 1e-4]
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
        pts = [CalibrationPoint(u=u, v=v, x_mm=u, y_mm=v)
               for (u, v) in [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0)]]
        with self.assertRaises(ValueError):
            fit_polynomial(pts, degree=2)

    def test_degree_3_requires_more_points(self):
        pts = [CalibrationPoint(u=float(i), v=float(i), x_mm=float(i), y_mm=float(i))
               for i in range(9)]
        with self.assertRaises(ValueError):
            fit_polynomial(pts, degree=3)

    def test_invalid_degree(self):
        pts = [CalibrationPoint(u=float(i), v=float(i), x_mm=float(i), y_mm=float(i))
               for i in range(20)]
        with self.assertRaises(ValueError):
            fit_polynomial(pts, degree=4)


# ----- work zone --------------------------------------------------------

class WorkZoneTests(unittest.TestCase):
    def test_contains_inside_and_outside(self):
        zone = WorkZone(x_min=-100, x_max=100, y_min=-50, y_max=50)
        self.assertTrue(zone.contains(0, 0))
        self.assertTrue(zone.contains(-100, 50))
        self.assertFalse(zone.contains(100.01, 0))
        self.assertFalse(zone.contains(0, 60))

    def test_derive_with_margin(self):
        pts = [CalibrationPoint(u=0, v=0, x_mm=x, y_mm=y)
               for x in (-100.0, 0.0, 100.0) for y in (-100.0, 0.0, 100.0)]
        zone = derive_work_zone(pts, margin_mm=20.0)
        self.assertEqual(zone.x_min, -80.0)
        self.assertEqual(zone.x_max, 80.0)
        self.assertEqual(zone.y_min, -80.0)
        self.assertEqual(zone.y_max, 80.0)

    def test_derive_clamped_to_hardware_limits(self):
        pts = [CalibrationPoint(u=0, v=0, x_mm=x, y_mm=y)
               for x in (-1000.0, 1000.0) for y in (-1000.0, 1000.0)]
        zone = derive_work_zone(pts, margin_mm=0.0)
        self.assertEqual(zone.x_min, -280.0)
        self.assertEqual(zone.x_max, 280.0)
        self.assertEqual(zone.y_min, -280.0)
        self.assertEqual(zone.y_max, 280.0)

    def test_derive_empty_zone_raises(self):
        pts = [CalibrationPoint(u=0, v=0, x_mm=x, y_mm=y)
               for x in (-5.0, 5.0) for y in (-5.0, 5.0)]
        with self.assertRaises(ValueError):
            derive_work_zone(pts, margin_mm=20.0)


# ----- ui keyboard helpers ---------------------------------------------

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


# ----- grid generation --------------------------------------------------

class GridTargetsTests(unittest.TestCase):
    def test_3x3_centred_at_origin(self):
        targets = generate_grid_targets(rows=3, cols=3, spacing_mm=100.0)
        self.assertEqual(len(targets), 9)
        self.assertEqual(targets[0], (-100.0, -100.0))
        self.assertEqual(targets[-1], (100.0, 100.0))

    def test_offset_grid_uses_home_xy(self):
        targets = generate_grid_targets(
            rows=2, cols=2, spacing_mm=50.0, home_x_mm=10.0, home_y_mm=-20.0,
        )
        self.assertEqual(targets[0], (-15.0, -45.0))
        self.assertEqual(targets[-1], (35.0, 5.0))

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            generate_grid_targets(rows=0, cols=3, spacing_mm=10.0)


# ----- IO round-trip ----------------------------------------------------

class IORoundTripTests(unittest.TestCase):
    def _build_calibration(self) -> Calibration:
        pts = [CalibrationPoint(u=u, v=v, x_mm=float(u - 320), y_mm=float(v - 240))
               for u in (100, 320, 540) for v in (80, 240, 400)]
        fit = fit_polynomial(pts, degree=2)
        zone = derive_work_zone(pts, margin_mm=10.0)
        return Calibration(
            image_size=(640, 480),
            fit=fit,
            points=pts,
            work_zone=zone,
            robot_home_mm=(0.0, 0.0),
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
        self.assertEqual(loaded.robot_home_mm, cal.robot_home_mm)
        self.assertEqual(loaded.pick_height_z_mm, cal.pick_height_z_mm)
        self.assertEqual(len(loaded.points), len(cal.points))

    def test_round_trip_with_non_zero_robot_home(self):
        cal = self._build_calibration()
        cal.robot_home_mm = (50.0, -20.0)
        d = cal.to_dict()
        self.assertEqual(d["robot_home_mm"], {"x": 50.0, "y": -20.0})
        loaded = Calibration.from_dict(d)
        self.assertEqual(loaded.robot_home_mm, (50.0, -20.0))

    def test_old_v1_json_raises(self):
        # An old v1 JSON looks structurally similar but lacks robot_home_mm and
        # carries removed fields. `from_dict` must refuse loudly.
        v1_blob = {
            "schema_version": 1,
            "image_size": [640, 480],
            "master_workspace": {"x_min": -280, "x_max": 280, "y_min": -280, "y_max": 280},
            "fit": {
                "type": "poly1",
                "coeffs_x": [0.0, 1.0, 0.0],
                "coeffs_y": [0.0, 0.0, 1.0],
                "rms_residual_mm": 0.0,
            },
            "calibration_points": [],
            "work_zone": {"x_min": -100, "x_max": 100, "y_min": -100, "y_max": 100},
            "tool_center_offset": {"x_mm": 0.0, "y_mm": 0.0},
            "pick_height_z_mm": -940.0,
            "created_at": "2026-05-15T00:00:00Z",
            "notes": "",
        }
        with self.assertRaises(ValueError) as ctx:
            Calibration.from_dict(v1_blob)
        self.assertIn("re-run", str(ctx.exception).lower())

    def test_schema_version_mismatch_raises(self):
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
        x, y = pixel_to_robot_xy(cal, 320, 240, image_size=(640, 480))
        self.assertTrue(math.isfinite(x))
        self.assertTrue(math.isfinite(y))


# ----- auto degree ------------------------------------------------------

class AutoDegreeTests(unittest.TestCase):
    def test_below_threshold(self):
        self.assertEqual(auto_select_degree(9), 2)
        self.assertEqual(auto_select_degree(15), 2)

    def test_at_and_above_threshold(self):
        self.assertEqual(auto_select_degree(16), 3)
        self.assertEqual(auto_select_degree(25), 3)


# ----- PolyFit JSON shape -----------------------------------------------

class PolyFitJSONTests(unittest.TestCase):
    def test_unsupported_type_rejected(self):
        with self.assertRaises(ValueError):
            PolyFit.from_dict({"type": "rbf", "coeffs_x": [], "coeffs_y": [], "rms_residual_mm": 0})

    def test_coeff_shape_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            PolyFit.from_dict({
                "type": "poly2",
                "coeffs_x": [1.0, 2.0],
                "coeffs_y": [1.0, 2.0],
                "rms_residual_mm": 0,
            })


# ----- runtime helpers --------------------------------------------------

def _make_calibration() -> Calibration:
    """Affine sanity calibration: X = u - 320, Y = v - 240, zone ±90 mm."""
    pts = [CalibrationPoint(u=u, v=v, x_mm=float(u - 320), y_mm=float(v - 240))
           for u in (220, 320, 420) for v in (140, 240, 340)]
    fit = fit_polynomial(pts, degree=2)
    zone = WorkZone(x_min=-90, x_max=90, y_min=-90, y_max=90)
    return Calibration(
        image_size=(640, 480),
        fit=fit,
        points=pts,
        work_zone=zone,
        robot_home_mm=(0.0, 0.0),
        pick_height_z_mm=-940.0,
        notes="unit test calibration",
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
        self.assertEqual(wrap.robot_home_mm, (0.0, 0.0))

    def test_transform_pixel(self):
        wrap = Calibrator(_make_calibration())
        x, y = wrap.transform_pixel(370, 290)
        self.assertAlmostEqual(x, 50.0, places=5)
        self.assertAlmostEqual(y, 50.0, places=5)

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
        wrap = Calibrator(_make_calibration())
        det = {"bbox_xyxy": [10, 10, 30, 30]}  # well outside zone
        self.assertIsNone(wrap.transform_detection(det))

    def test_transform_detection_no_bbox_returns_none(self):
        wrap = Calibrator(_make_calibration())
        self.assertIsNone(wrap.transform_detection({}))


# ----- _annotate_board_mm shape (no x_raw/y_raw split) ------------------

class AnnotateBoardMmTests(unittest.TestCase):
    def _annotate(self):
        from vision.commands import _annotate_board_mm
        return _annotate_board_mm

    def test_annotates_inside_and_outside_zone(self):
        annotate = self._annotate()
        wrap = Calibrator(_make_calibration())
        detections = [
            {"label": "apple", "bbox_xyxy": [360, 280, 380, 300]},  # -> (50, 50), inside
            {"label": "apple", "bbox_xyxy": [10, 10, 30, 30]},       # well outside
            {"label": "apple"},                                       # no bbox
        ]
        annotate(detections, wrap, image_size=(640, 480))
        b0 = detections[0]["board_xy_mm"]
        self.assertAlmostEqual(b0["x"], 50.0, places=2)
        self.assertAlmostEqual(b0["y"], 50.0, places=2)
        self.assertTrue(b0["inside_zone"])
        self.assertNotIn("error", b0)
        self.assertNotIn("x_raw", b0)
        self.assertNotIn("y_raw", b0)

        b1 = detections[1]["board_xy_mm"]
        self.assertFalse(b1["inside_zone"])
        self.assertIsNotNone(b1["x"])

        b2 = detections[2]["board_xy_mm"]
        self.assertIsNone(b2["x"])
        self.assertIsNone(b2["y"])
        self.assertFalse(b2["inside_zone"])

    def test_image_size_mismatch_marks_error(self):
        annotate = self._annotate()
        wrap = Calibrator(_make_calibration())
        detections = [{"label": "apple", "bbox_xyxy": [360, 280, 380, 300]}]
        annotate(detections, wrap, image_size=(1280, 720))
        b = detections[0]["board_xy_mm"]
        self.assertEqual(b["error"], "image_size_mismatch")
        self.assertIsNone(b["x"])
        self.assertIsNone(b["y"])
        self.assertFalse(b["inside_zone"])

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
        self.assertNotIn("quality", detections[0])

    def test_no_frame_is_noop(self):
        annotate = self._annotate()
        detections = [{"detection_type": "produce", "label": "orange",
                       "confidence": 80.0, "bbox_xyxy": [10, 10, 190, 190]}]
        annotate(detections, None)
        self.assertNotIn("quality", detections[0])


@unittest.skipUnless(_has_cv2_for_quality(), "opencv-python not installed")
class RefinedDetectionCenterTests(unittest.TestCase):
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


# ----- labels (kept here because the test was already here) -------------

class LineIntersectionTests(unittest.TestCase):
    def test_simple_perpendicular_lines(self):
        # Vertical x=10, horizontal y=5 -> (10, 5)
        u, v = intersect_infinite_lines_2d(
            (10.0, 0.0), (10.0, 100.0), (0.0, 5.0), (100.0, 5.0),
        )
        self.assertAlmostEqual(u, 10.0, places=6)
        self.assertAlmostEqual(v, 5.0, places=6)

    def test_parallel_lines_raise(self):
        with self.assertRaises(ValueError):
            intersect_infinite_lines_2d(
                (0.0, 0.0), (10.0, 0.0), (0.0, 5.0), (10.0, 5.0),
            )


class HiddenCornerTests(unittest.TestCase):
    def test_axis_aligned_square_recovers_hidden(self):
        # Hidden corner at (100, 100); known corners at (100, 0) and (0, 100).
        # Edge line from (100,0) through hidden has helper at (100, 40).
        # Edge line from (0,100) through hidden has helper at (60, 100).
        hidden = infer_hidden_corner(
            corner_a_uv=(100.0, 0.0),
            helper_a_uv=(100.0, 40.0),
            corner_b_uv=(0.0, 100.0),
            helper_b_uv=(60.0, 100.0),
        )
        self.assertAlmostEqual(hidden[0], 100.0, places=6)
        self.assertAlmostEqual(hidden[1], 100.0, places=6)

    def test_perspective_skewed_square_recovers_hidden(self):
        # Trapezoidal "square" from a slight perspective tilt. Corners (150,30)
        # and (40,140) are known; helpers sit on their respective edges that
        # meet at the hidden corner (170, 160).
        helper_a = (160.0, 95.0)    # on the (150,30) -> (170,160) edge
        helper_b = (105.0, 150.0)   # on the (40,140) -> (170,160) edge
        hidden = infer_hidden_corner(
            corner_a_uv=(150.0, 30.0),
            helper_a_uv=helper_a,
            corner_b_uv=(40.0, 140.0),
            helper_b_uv=helper_b,
        )
        self.assertAlmostEqual(hidden[0], 170.0, places=4)
        self.assertAlmostEqual(hidden[1], 160.0, places=4)


class BuildSquareCalibrationPointsTests(unittest.TestCase):
    def test_default_corners_at_half_side(self):
        pts = build_square_calibration_points(
            mxmy_uv=(0, 100), mxpy_uv=(0, 0),
            pxmy_uv=(100, 100), pxpy_uv=(100, 0),
            home_uv=(50, 50),
            side_mm=200.0, home_x_mm=0.0, home_y_mm=0.0,
        )
        self.assertEqual(len(pts), 5)
        self.assertEqual((pts[0].x_mm, pts[0].y_mm), (-100.0, -100.0))  # mxmy
        self.assertEqual((pts[1].x_mm, pts[1].y_mm), (-100.0, 100.0))   # mxpy
        self.assertEqual((pts[2].x_mm, pts[2].y_mm), (100.0, -100.0))   # pxmy
        self.assertEqual((pts[3].x_mm, pts[3].y_mm), (100.0, 100.0))    # pxpy
        self.assertEqual((pts[4].x_mm, pts[4].y_mm), (0.0, 0.0))        # home

    def test_home_off_centre(self):
        # Home click is a separate labelled point at user-supplied robot mm.
        pts = build_square_calibration_points(
            mxmy_uv=(0, 100), mxpy_uv=(0, 0),
            pxmy_uv=(100, 100), pxpy_uv=(100, 0),
            home_uv=(70, 55),
            side_mm=200.0, home_x_mm=40.0, home_y_mm=-15.0,
        )
        self.assertEqual((pts[4].x_mm, pts[4].y_mm), (40.0, -15.0))
        # Corners remain anchored to robot origin regardless of where home is.
        self.assertEqual((pts[0].x_mm, pts[0].y_mm), (-100.0, -100.0))

    def test_invalid_side_raises(self):
        with self.assertRaises(ValueError):
            build_square_calibration_points(
                mxmy_uv=(0, 0), mxpy_uv=(0, 0), pxmy_uv=(0, 0), pxpy_uv=(0, 0),
                home_uv=(0, 0),
                side_mm=0.0, home_x_mm=0.0, home_y_mm=0.0,
            )


class SixClickEndToEndTests(unittest.TestCase):
    """Drive build_square_calibration_points -> fit_polynomial and check it recovers an affine map."""

    def test_perfect_top_down_square_recovers_affine(self):
        # Pretend the camera maps the work plane affinely:
        #     u = 320 + 0.8 * X_mm
        #     v = 240 - 0.8 * Y_mm     (image-y grows DOWN, robot-y grows UP)
        # Hidden corner in the new convention is (+X, +Y).
        side = 200.0
        half = side / 2.0
        def to_pixel(x, y):
            return (320.0 + 0.8 * x, 240.0 - 0.8 * y)

        mxmy_uv = to_pixel(-half, -half)
        mxpy_uv = to_pixel(-half, +half)
        pxmy_uv = to_pixel(+half, -half)
        pxpy_uv = to_pixel(+half, +half)        # hidden corner
        home_uv = to_pixel(0.0, 0.0)

        # +X edge helper: collinear with pxmy and the hidden pxpy (midpoint).
        helper_px_edge = (
            (pxmy_uv[0] + pxpy_uv[0]) / 2.0,
            (pxmy_uv[1] + pxpy_uv[1]) / 2.0,
        )
        # +Y edge helper: collinear with mxpy and the hidden pxpy.
        helper_py_edge = (
            (mxpy_uv[0] + pxpy_uv[0]) / 2.0,
            (mxpy_uv[1] + pxpy_uv[1]) / 2.0,
        )
        inferred_pxpy = infer_hidden_corner(
            corner_a_uv=pxmy_uv, helper_a_uv=helper_px_edge,
            corner_b_uv=mxpy_uv, helper_b_uv=helper_py_edge,
        )
        self.assertAlmostEqual(inferred_pxpy[0], pxpy_uv[0], places=4)
        self.assertAlmostEqual(inferred_pxpy[1], pxpy_uv[1], places=4)

        pts = build_square_calibration_points(
            mxmy_uv=mxmy_uv, mxpy_uv=mxpy_uv, pxmy_uv=pxmy_uv, pxpy_uv=inferred_pxpy,
            home_uv=home_uv,
            side_mm=side, home_x_mm=0.0, home_y_mm=0.0,
        )
        fit = fit_polynomial(pts, degree=1)
        # The known inverse is X = (u - 320) / 0.8, Y = -(v - 240) / 0.8.
        x_at_origin, y_at_origin = fit.apply(320.0, 240.0)
        self.assertAlmostEqual(x_at_origin, 0.0, places=3)
        self.assertAlmostEqual(y_at_origin, 0.0, places=3)
        x_far, y_far = fit.apply(320.0 + 80.0, 240.0)  # +80 px on u
        self.assertAlmostEqual(x_far, 100.0, places=3)
        self.assertAlmostEqual(y_far, 0.0, places=3)
        self.assertLess(fit.rms_residual_mm, 1e-3)


class LabelTaxonomyTests(unittest.TestCase):
    def test_labels_object_type_is_now_skip(self):
        from vision.labels import classify_yolo_label
        for label in ("bicycle", "car", "chair"):
            dtype, _ = classify_yolo_label(label)
            self.assertEqual(dtype, "skip", msg=label)

    def test_labels_produce_and_human_still_pass(self):
        from vision.labels import classify_yolo_label
        self.assertEqual(classify_yolo_label("apple")[0], "produce")
        self.assertEqual(classify_yolo_label("person")[0], "human")


if __name__ == "__main__":
    unittest.main()
