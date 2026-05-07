"""One-shot calibration demo for a stereo top-down photo of the work area.

Workflow (no camera, no robot, no clicks needed):
  1. Read the JPG.
  2. Split the side-by-side stereo image -> use the LEFT view only (matches
     the ZED SDK convention used in vision/vision.py for detection).
  3. Auto-crop black letterbox borders.
  4. Auto-detect the bright-green corner markers via HSV thresholding.
  5. Sort the four corners as TL, TR, BR, BL.
  6. Assume a known board size in mm (default 300 mm) centred on the robot
     origin -> assign each corner a robot (X_mm, Y_mm).
  7. Fit a degree-1 (affine) polynomial -> save calibration.json.
  8. Draw an annotated result image -> calibration_result.png.

This script is INDEPENDENT of vision/vision.py — it does not import the ZED
pipeline and will not affect the camera code in any way. It only depends on
opencv-python + numpy + the local calibration core/draw modules.

Run:
    python -m vision.calibration.demo --image tests/photo_5467843704455370617_y.jpg

Tweak board size / margin if the four green markers do not actually enclose a
300x300 mm square in robot frame:
    python -m vision.calibration.demo --image PATH --board-size 250 --margin 10
"""

from __future__ import annotations

import argparse
import os
import sys
from itertools import combinations
from typing import Sequence

import numpy as np

from .core import (
    Calibration,
    CalibrationPoint,
    DEFAULT_PICK_HEIGHT_MM,
    derive_work_zone,
    fit_polynomial,
    save_calibration,
)
from .draw import draw_result_image


def split_stereo_left(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    return image[:, : w // 2].copy()


def crop_black_borders(image: np.ndarray, threshold: int = 12) -> np.ndarray:
    gray = image.mean(axis=2) if image.ndim == 3 else image
    mask = gray > threshold
    if not mask.any():
        return image
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    return image[y0:y1, x0:x1].copy()


def detect_green_blobs(
    image_bgr: np.ndarray,
    top_exclude_frac: float = 0.20,
    bottom_exclude_frac: float = 0.05,
    side_exclude_frac: float = 0.05,
    min_area: float = 30.0,
) -> tuple[list[tuple[int, int, float]], "np.ndarray"]:
    """Detect green-tape blobs and return (blobs, mask).

    The four corner markers sit on the central work board, so we exclude blobs
    too close to the image edges (background props can also be green). Strong
    morphological closing merges L-shape fragments into single blobs.
    """
    import cv2

    h, w = image_bgr.shape[:2]
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 70, 70], dtype=np.uint8)
    upper = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs: list[tuple[int, int, float]] = []
    x_lo, x_hi = int(w * side_exclude_frac), int(w * (1 - side_exclude_frac))
    y_lo, y_hi = int(h * top_exclude_frac), int(h * (1 - bottom_exclude_frac))
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area:
            continue
        m = cv2.moments(c)
        if m["m00"] == 0:
            continue
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        if not (x_lo <= cx <= x_hi and y_lo <= cy <= y_hi):
            continue
        blobs.append((cx, cy, area))

    blobs.sort(key=lambda t: t[2], reverse=True)
    return blobs, mask


def pick_four_corners_max_hull(
    blobs: Sequence[tuple[int, int, float]]
) -> list[tuple[int, int, float]]:
    """From N>=4 candidate blobs pick the 4 whose convex hull is largest.

    With only 4 markers placed sensibly on the work board, this picks the four
    most-spread-out points and naturally rejects extra noise like centre marks
    or small fragments."""
    import cv2

    if len(blobs) < 4:
        raise ValueError(f"Need >=4 candidate blobs, got {len(blobs)}")
    if len(blobs) == 4:
        return list(blobs)

    best_combo: tuple[int, ...] | None = None
    best_area = -1.0
    for combo in combinations(range(len(blobs)), 4):
        pts = np.array([(blobs[i][0], blobs[i][1]) for i in combo], dtype=np.float32)
        area = float(cv2.contourArea(cv2.convexHull(pts)))
        if area > best_area:
            best_area, best_combo = area, combo
    assert best_combo is not None
    return [blobs[i] for i in best_combo]


def draw_debug_candidates(
    image_bgr: np.ndarray,
    all_blobs: Sequence[tuple[int, int, float]],
    chosen: Sequence[tuple[int, int, float]],
    output_path: str,
):
    """Annotate every detected blob (yellow circles, numbered) and the four
    chosen corners (red rings). Saves a debug PNG so the operator can confirm
    auto-detection at a glance."""
    import cv2

    overlay = image_bgr.copy()
    chosen_set = {(b[0], b[1]) for b in chosen}
    for i, (cx, cy, area) in enumerate(all_blobs):
        cv2.circle(overlay, (cx, cy), 12, (0, 255, 255), 2)
        cv2.putText(
            overlay, f"#{i + 1}", (cx + 14, cy - 14),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA,
        )
        if (cx, cy) in chosen_set:
            cv2.circle(overlay, (cx, cy), 18, (0, 0, 255), 3)

    cv2.putText(
        overlay,
        "Yellow = all green blobs   Red ring = chosen corner",
        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    cv2.imwrite(output_path, overlay)


def sort_corners_tl_tr_br_bl(
    points: Sequence[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Order four points clockwise from top-left in image coordinates."""
    if len(points) != 4:
        raise ValueError("sort_corners_tl_tr_br_bl needs exactly 4 points")
    arr = np.array(points, dtype=float)
    s = arr.sum(axis=1)
    d = arr[:, 0] - arr[:, 1]
    tl = tuple(arr[int(np.argmin(s))].astype(int))
    br = tuple(arr[int(np.argmax(s))].astype(int))
    tr = tuple(arr[int(np.argmax(d))].astype(int))
    bl = tuple(arr[int(np.argmin(d))].astype(int))
    return [tl, tr, br, bl]


def build_calibration_points(
    corners_tl_tr_br_bl: Sequence[tuple[int, int]],
    board_size_mm: float,
) -> list[CalibrationPoint]:
    """Map sorted image corners to robot (X, Y) assuming the green-marker square
    is centred on the robot origin. Image-y-down is converted to robot-y-up."""
    half = board_size_mm / 2.0
    robot_xy = [
        (-half, +half),  # TL  in image -> robot (-X, +Y)
        (+half, +half),  # TR
        (+half, -half),  # BR
        (-half, -half),  # BL
    ]
    points: list[CalibrationPoint] = []
    for (u, v), (x_mm, y_mm) in zip(corners_tl_tr_br_bl, robot_xy):
        points.append(CalibrationPoint(u=float(u), v=float(v), x_mm=x_mm, y_mm=y_mm))
    return points


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--image", required=True, help="Path to the stereo JPG")
    parser.add_argument(
        "--out-dir",
        default="calibration",
        help="Where to save calibration.json + calibration_result.png",
    )
    parser.add_argument(
        "--board-size",
        type=float,
        default=300.0,
        help="Side length in mm of the square enclosed by the four green markers (default 300)",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=10.0,
        help="Inset (mm) from board edge to safe work zone (default 10)",
    )
    parser.add_argument(
        "--pick-height-z",
        type=float,
        default=DEFAULT_PICK_HEIGHT_MM,
        help=f"Pick-height Z in robot mm (default {DEFAULT_PICK_HEIGHT_MM})",
    )
    parser.add_argument(
        "--no-stereo-split",
        action="store_true",
        help="Skip the stereo split (use the whole image as-is)",
    )
    args = parser.parse_args(argv)

    try:
        import cv2
    except ImportError:
        print("ERROR: opencv-python is required (pip install opencv-python)", file=sys.stderr)
        return 2

    if not os.path.isfile(args.image):
        print(f"ERROR: image not found: {args.image}", file=sys.stderr)
        return 2

    raw = cv2.imread(args.image)
    if raw is None:
        print(f"ERROR: cv2.imread failed for {args.image}", file=sys.stderr)
        return 2
    print(f"Loaded {args.image} -> shape {raw.shape}")

    work = raw if args.no_stereo_split else split_stereo_left(raw)
    if not args.no_stereo_split:
        print(f"Stereo split: using LEFT view -> shape {work.shape}")

    cropped = crop_black_borders(work)
    print(f"Auto-crop black borders -> shape {cropped.shape}")

    blobs, mask = detect_green_blobs(cropped)
    print(f"Detected {len(blobs)} green-blob candidates (after edge filter, largest first):")
    for i, (cx, cy, area) in enumerate(blobs[:12]):
        print(f"  #{i + 1}: pixel=({cx}, {cy})  area={area:.0f}")

    if len(blobs) < 4:
        print("ERROR: fewer than 4 green markers detected.", file=sys.stderr)
        print("Try adjusting --board-size, the HSV range in detect_green_blobs(),")
        print("or fall back to the click UI: python -m vision.calibration.ui --image ...")
        return 3

    chosen = pick_four_corners_max_hull(blobs)
    print("Chose 4 corners (max convex-hull area):")
    for c in chosen:
        print(f"  {c}")

    corners = sort_corners_tl_tr_br_bl([(b[0], b[1]) for b in chosen])
    print("Corners in TL, TR, BR, BL order (pixel):")
    for c in corners:
        print(f"  {c}")

    points = build_calibration_points(corners, args.board_size)

    fit = fit_polynomial(points, degree=1)
    print(f"Affine fit: RMS residual = {fit.rms_residual_mm:.4f} mm "
          f"(should be ~0 for a perfect 4-point affine)")

    zone = derive_work_zone(points, margin_mm=args.margin)

    h_img, w_img = cropped.shape[:2]
    cal = Calibration(
        image_size=(int(w_img), int(h_img)),
        fit=fit,
        points=points,
        work_zone=zone,
        pick_height_z_mm=args.pick_height_z,
        notes=(
            f"Demo from {os.path.basename(args.image)}; auto-detected green "
            f"corners; assumed board={args.board_size} mm, margin={args.margin} mm. "
            "Robot XY assignment is centred on robot origin (TL=-X+Y, TR=+X+Y, "
            "BR=+X-Y, BL=-X-Y); rotate the printout if your real frame differs."
        ),
    )

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "calibration.json")
    img_path = os.path.join(args.out_dir, "calibration_result.png")
    debug_path = os.path.join(args.out_dir, "calibration_debug.png")
    mask_path = os.path.join(args.out_dir, "calibration_mask.png")
    save_calibration(json_path, cal)
    print(f"Saved {json_path}")
    draw_result_image(cropped, cal, img_path)
    print(f"Saved {img_path}")
    draw_debug_candidates(cropped, blobs, chosen, debug_path)
    print(f"Saved {debug_path}")
    cv2.imwrite(mask_path, mask)
    print(f"Saved {mask_path}")

    print()
    print("Quick sanity check (forward transform on detected corners):")
    for p, (x_mm, y_mm) in zip(points, [(p.x_mm, p.y_mm) for p in points]):
        gx, gy = cal.pixel_to_robot_xy(p.u, p.v)
        print(
            f"  pixel ({p.u:.0f}, {p.v:.0f}) -> robot "
            f"({gx:+.2f}, {gy:+.2f}) mm  (target {x_mm:+.0f}, {y_mm:+.0f})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
