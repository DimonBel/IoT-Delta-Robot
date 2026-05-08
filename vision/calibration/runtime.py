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
predicted point falls outside the saved work zone, so the caller can write a
single `if target is not None:` guard instead of branching twice.
"""

from __future__ import annotations

from typing import Mapping, Sequence

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


class Calibrator:
    """Small façade over a loaded Calibration. Use this in the runtime loop.

    Doesn't import OpenCV. Doesn't touch the camera. Pure pixel -> robot mm.
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
        """Pixel -> (X_mm, Y_mm) in robot frame.

        Pass `image_size=(W, H)` to assert the runtime resolution matches the
        calibrated one. Mismatch raises ValueError.
        """
        return pixel_to_robot_xy(self._cal, u, v, image_size=image_size)

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
          - the predicted point is outside the saved work zone.

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
