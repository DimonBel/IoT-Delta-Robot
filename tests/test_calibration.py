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
    derive_work_zone,
    detection_center,
    fit_polynomial,
    generate_grid_targets,
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
        det = {"bbox_xyxy": [10, 10, 30, 30]}  # centre (20, 20) -> (-300, -220) outside
        self.assertIsNone(wrap.transform_detection(det))

    def test_transform_detection_no_bbox_returns_none(self):
        wrap = Calibrator(_make_calibration())
        self.assertIsNone(wrap.transform_detection({}))


if __name__ == "__main__":
    unittest.main()
