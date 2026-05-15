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

from .core import Calibration, CalibrationPoint, PolyFit, WorkZone, fit_polynomial


def fit_inverse_polynomial(
    points: Sequence[CalibrationPoint], degree: int = 1
) -> PolyFit:
    """Fit a polynomial that goes the OTHER way: (X_mm, Y_mm) -> (u, v).

    Used purely for drawing the work-zone polygon back onto the image. Default
    degree is 1 (affine) because the inverse only needs to be good enough to
    visualise; the production transform stays the forward fit."""
    swapped = [
        CalibrationPoint(u=p.x_mm, v=p.y_mm, x_mm=p.u, y_mm=p.v) for p in points
    ]
    return fit_polynomial(swapped, degree=degree)


def _zone_perimeter_robot(zone: WorkZone, samples_per_edge: int = 24):
    """Return a list of (X_mm, Y_mm) points walking the zone perimeter."""
    pts: list[tuple[float, float]] = []
    xs = np.linspace(zone.x_min, zone.x_max, samples_per_edge)
    ys = np.linspace(zone.y_min, zone.y_max, samples_per_edge)
    for x in xs:
        pts.append((float(x), zone.y_min))
    for y in ys:
        pts.append((zone.x_max, float(y)))
    for x in xs[::-1]:
        pts.append((float(x), zone.y_max))
    for y in ys[::-1]:
        pts.append((zone.x_min, float(y)))
    return pts


def draw_result_image(
    image_bgr,
    calibration: Calibration,
    output_path: str,
    samples_per_edge: int = 24,
):
    """Render an annotated PNG showing markers + work-zone outline.

    The image is for the human operator to confirm the calibration covers the
    intended area. It is not used by the runtime transform.
    """
    import cv2  # lazy import; calibration math itself doesn't need cv2.

    if image_bgr is None:
        raise ValueError("draw_result_image needs a BGR image array")

    overlay = image_bgr.copy()
    h_img, w_img = overlay.shape[:2]

    # Inverse fit (robot mm -> pixel) just for the visualization.
    try:
        inverse_fit = fit_inverse_polynomial(calibration.points, degree=1)
    except ValueError:
        inverse_fit = None

    # Full board outline = polygon through clicked markers.
    board_pts = np.array(
        [[[int(p.u), int(p.v)] for p in calibration.points]], dtype=np.int32
    )
    cv2.polylines(overlay, board_pts, isClosed=True, color=(0, 200, 0), thickness=2)

    # Active zone (cyan), drawn via inverse fit if available.
    if inverse_fit is not None:
        zone_pts_mm = _zone_perimeter_robot(calibration.effective_active_zone(), samples_per_edge)
        zone_pts_px = []
        for (x_mm, y_mm) in zone_pts_mm:
            u, v = inverse_fit.apply(x_mm, y_mm)
            zone_pts_px.append([int(round(u)), int(round(v))])
        zone_arr = np.array([zone_pts_px], dtype=np.int32)
        cv2.polylines(overlay, zone_arr, isClosed=True, color=(0, 255, 255), thickness=2)

    # Calibration markers + their robot-frame labels.
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
    strip_h = 78
    cv2.rectangle(overlay, (0, h_img - strip_h), (w_img, h_img), (30, 30, 30), -1)
    line1 = (
        f"Fit: poly{calibration.fit.degree}   "
        f"RMS residual = {calibration.fit.rms_residual_mm:.2f} mm   "
        f"N points = {len(calibration.points)}"
    )
    z = calibration.effective_active_zone()
    line2 = (
        f"Active zone (mm): X[{z.x_min:.0f}, {z.x_max:.0f}]  "
        f"Y[{z.y_min:.0f}, {z.y_max:.0f}]   "
        f"Pick Z = {calibration.pick_height_z_mm:.0f} mm"
    )
    line3 = (
        "Green = calibrated marker outline   "
        "Cyan = active zone   "
        "Red dots = clicked markers"
    )
    cv2.putText(overlay, line1, (10, h_img - strip_h + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(overlay, line2, (10, h_img - strip_h + 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(overlay, line3, (10, h_img - strip_h + 67),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    ok = cv2.imwrite(output_path, overlay)
    if not ok:
        raise RuntimeError(f"cv2.imwrite failed for {output_path}")
