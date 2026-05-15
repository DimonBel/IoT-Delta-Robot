"""Ergonomic runtime helpers built on top of vision.calibration.core.

Designed to be the one-line entry point used inside the live loop:

    from vision.calibration import Calibrator

    cal = Calibrator.load()                  # reads calibration/calibration.json

    # for each YOLO detection produced by vision.vision:
    target = cal.transform_detection(detection)
    if target is not None:
        x_mm, y_mm, z_mm = target
        robot.move_to(x_mm, y_mm, z_mm)
        robot.pick()

`transform_detection` returns None when the bbox is missing/invalid OR when the
corrected TCP position falls outside the effective active zone, so the caller can write a
single `if target is not None:` guard instead of branching twice.
"""

from __future__ import annotations

from typing import Mapping, MutableMapping, Sequence

from .core import Calibration, load_calibration, pixel_to_robot_xy


def detection_center(detection: Mapping) -> tuple[float, float] | None:
    """Pull the bbox centre pixel out of a detection dict.

    Accepts the shape produced by vision.vision (`bbox_xyxy: [x1, y1, x2, y2]`).
    Returns None if the bbox is missing or malformed.
    """
    bbox = detection.get("bbox_xyxy") if isinstance(detection, Mapping) else None
    if not isinstance(bbox, Sequence) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(b) for b in bbox)
    except (TypeError, ValueError):
        return None
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _bbox_floats(detection: Mapping) -> tuple[float, float, float, float] | None:
    bbox = detection.get("bbox_xyxy") if isinstance(detection, Mapping) else None
    if not isinstance(bbox, Sequence) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(b) for b in bbox)
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def refined_detection_center(
    detection: MutableMapping,
    rgb_frame,
) -> tuple[float, float] | None:
    """Sphere-aware bbox centre refinement for top-down near-spherical produce.

    Algorithm: pad the bbox a touch, threshold the saturation channel (Otsu),
    take the largest contour and fit a min-enclosing circle. If the fit passes
    a size sanity gate, return its centre in image coordinates; otherwise fall
    back to the bbox arithmetic-mean centre.

    Side effects (on `detection`):
        detection["center_uv"]     = [u, v]
        detection["center_method"] = "circle_fit" | "bbox_center"

    Returns the (u, v) used, or None when the bbox itself is missing/invalid.
    """
    bbox = _bbox_floats(detection)
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    fallback = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _set_fallback() -> tuple[float, float]:
        detection["center_uv"] = [float(fallback[0]), float(fallback[1])]
        detection["center_method"] = "bbox_center"
        return fallback

    if rgb_frame is None:
        return _set_fallback()

    try:
        import cv2
        import numpy as np
    except ImportError:
        return _set_fallback()

    try:
        h_img, w_img = rgb_frame.shape[:2]
    except (AttributeError, ValueError):
        return _set_fallback()

    bbox_w = x2 - x1
    bbox_h = y2 - y1
    pad = min(16.0, 0.10 * min(bbox_w, bbox_h))
    cx1 = max(0, int(round(x1 - pad)))
    cy1 = max(0, int(round(y1 - pad)))
    cx2 = min(w_img, int(round(x2 + pad)))
    cy2 = min(h_img, int(round(y2 + pad)))
    if cx2 <= cx1 or cy2 <= cy1:
        return _set_fallback()

    crop = rgb_frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return _set_fallback()

    try:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        _, mask = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    except cv2.error:
        return _set_fallback()

    if not contours:
        return _set_fallback()

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) <= 0:
        return _set_fallback()

    (cx, cy), radius = cv2.minEnclosingCircle(largest)
    diameter = 2.0 * float(radius)
    if diameter < 0.3 * min(bbox_w, bbox_h) or diameter > 1.3 * max(bbox_w, bbox_h):
        return _set_fallback()

    u = float(cx1) + float(cx)
    v = float(cy1) + float(cy)
    detection["center_uv"] = [u, v]
    detection["center_method"] = "circle_fit"
    return u, v


class Calibrator:
    """Small façade over a loaded Calibration. Use this in the runtime loop.

    Doesn't import OpenCV. Doesn't touch the camera. Maps pixels through the
    saved polynomial into master-frame mm, then applies the tool-centre offset.
    """

    DEFAULT_PATH = "calibration/calibration.json"

    def __init__(self, calibration: Calibration):
        self._cal = calibration

    @classmethod
    def load(cls, path: str | None = None) -> "Calibrator":
        return cls(load_calibration(path or cls.DEFAULT_PATH))

    @property
    def calibration(self) -> Calibration:
        return self._cal

    @property
    def pick_height_z_mm(self) -> float:
        return self._cal.pick_height_z_mm

    @property
    def image_size(self) -> tuple[int, int]:
        return self._cal.image_size

    def transform_pixel(
        self,
        u: float,
        v: float,
        image_size: tuple[int, int] | None = None,
    ) -> tuple[float, float]:
        """Pixel -> (X_mm, Y_mm) in robot frame after tool-centre offset.

        Raw polynomial board coordinates use `Calibration.pixel_to_robot_xy`; this
        adds the saved gripper TCP correction so `x/y` match the robot controller.
        """
        x_mm, y_mm = pixel_to_robot_xy(self._cal, u, v, image_size=image_size)
        return self._cal.apply_tool_center_offset(x_mm, y_mm)

    def board_xy_payload(
        self,
        u: float,
        v: float,
        image_size: tuple[int, int] | None = None,
    ) -> dict:
        """Structured pixel -> robot mapping for telemetry (raw vs corrected)."""
        x_raw, y_raw = pixel_to_robot_xy(self._cal, u, v, image_size=image_size)
        off = self._cal.tool_center_offset
        x_corr = x_raw + off.x_mm
        y_corr = y_raw + off.y_mm
        applied = abs(off.x_mm) > 1e-12 or abs(off.y_mm) > 1e-12
        return {
            "x_raw": round(float(x_raw), 2),
            "y_raw": round(float(y_raw), 2),
            "x": round(float(x_corr), 2),
            "y": round(float(y_corr), 2),
            "inside_zone": bool(self.is_inside_zone(x_corr, y_corr)),
            "frame": "robot_master_mm",
            "zone_mode": "active_zone_filter_only",
            "center_correction_applied": applied,
        }

    def is_inside_zone(self, x_mm: float, y_mm: float) -> bool:
        return self._cal.is_inside_zone(x_mm, y_mm)

    def transform_detection(
        self,
        detection: Mapping,
        image_size: tuple[int, int] | None = None,
    ) -> tuple[float, float, float] | None:
        """Detection dict -> (X_mm, Y_mm, Z_mm) or None.

        Returns None when:
          - the detection has no/invalid `bbox_xyxy`, or
          - the corrected TCP position is outside the effective active zone.

        Z is the configured pick-height from calibration.json.
        """
        center = detection_center(detection)
        if center is None:
            return None
        u, v = center
        x_mm, y_mm = self.transform_pixel(u, v, image_size=image_size)
        if not self._cal.is_inside_zone(x_mm, y_mm):
            return None
        return x_mm, y_mm, self._cal.pick_height_z_mm
