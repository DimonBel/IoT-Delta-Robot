"""Annotated result-image rendering for visual calibration verification.

These functions are NOT part of the runtime transform — they exist so the
operator can confirm with their eyes that the calibration captured the right
area. cv2 is imported lazily so the math/IO module (vision.calibration.core)
remains usable without OpenCV.
"""

from __future__ import annotations

import os
from typing import Sequence

import numpy as np

from .core import (
    Calibration,
    CalibrationPoint,
    HomographyFit,
    PolyFit,
    fit_polynomial,
)


def fit_inverse_polynomial(
    points: Sequence[CalibrationPoint], degree: int = 1
) -> PolyFit:
    """Fit a polynomial that goes the OTHER way: (X_mm, Y_mm) -> (u, v).

    Kept as a public helper for callers that need an inverse mapping. The
    result-image renderer does not use it any more (the cyan work-zone
    overlay was removed)."""
    swapped = [
        CalibrationPoint(u=p.x_mm, v=p.y_mm, x_mm=p.u, y_mm=p.v) for p in points
    ]
    return fit_polynomial(swapped, degree=degree)


def draw_result_image(
    image_bgr,
    calibration: Calibration,
    output_path: str,
):
    """Render an annotated PNG showing the 4-corner square + the home marker.

    Two things drawn:
      - The PINK square outline (4 clicked corners in CCW order).
      - Each clicked marker as a red dot with its robot-mm label.
        The home click is one of those markers; it is intentionally NOT part
        of the square's perimeter — its only job is to anchor the square to
        the robot's coordinate frame at (--home-x, --home-y).

    The cyan work-zone polygon was removed: the square IS the work area.
    """
    import cv2  # lazy import; calibration math itself doesn't need cv2.

    if image_bgr is None:
        raise ValueError("draw_result_image needs a BGR image array")

    overlay = image_bgr.copy()
    h_img, w_img = overlay.shape[:2]

    # 4-corner square outline (pink, CCW: mxmy -> mxpy -> pxpy -> pxmy).
    # The 5th point in the list (home) is NOT part of the perimeter; including
    # it would make the polygon a bowtie.
    PINK_BGR = (180, 105, 255)
    corner_perimeter_indices = (0, 1, 3, 2)
    pts = calibration.points
    if len(pts) >= 4:
        board_pts = np.array(
            [[[int(pts[i].u), int(pts[i].v)] for i in corner_perimeter_indices]],
            dtype=np.int32,
        )
        cv2.polylines(overlay, board_pts, isClosed=True, color=PINK_BGR, thickness=2)

    # Calibration markers + their robot-frame labels (red dots, white halo).
    for p in calibration.points:
        cx, cy = int(p.u), int(p.v)
        cv2.circle(overlay, (cx, cy), 9, (255, 255, 255), 2)
        cv2.circle(overlay, (cx, cy), 6, (0, 0, 255), -1)
        label = f"({p.x_mm:.0f}, {p.y_mm:.0f}) mm"
        text_org = (cx + 12, max(20, cy - 12))
        cv2.putText(
            overlay, label, text_org, cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            (0, 0, 0), 3, cv2.LINE_AA,
        )
        cv2.putText(
            overlay, label, text_org, cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            (255, 255, 255), 1, cv2.LINE_AA,
        )

    # Caption strip at the bottom.
    strip_h = 58
    cv2.rectangle(overlay, (0, h_img - strip_h), (w_img, h_img), (30, 30, 30), -1)
    home = calibration.robot_home_mm
    fit = calibration.fit
    fit_label = "homography" if isinstance(fit, HomographyFit) else f"poly{fit.degree}"
    line1 = (
        f"Fit: {fit_label}   "
        f"RMS residual = {fit.rms_residual_mm:.2f} mm   "
        f"N points = {len(calibration.points)}   "
        f"Home=({home[0]:.0f}, {home[1]:.0f}) mm   "
        f"Pick Z = {calibration.pick_height_z_mm:.0f} mm"
    )
    line2 = "Pink = calibrated zone   Red dots = clicked markers"
    cv2.putText(overlay, line1, (10, h_img - strip_h + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(overlay, line2, (10, h_img - strip_h + 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    ok = cv2.imwrite(output_path, overlay)
    if not ok:
        raise RuntimeError(f"cv2.imwrite failed for {output_path}")
