"""Interactive click-and-confirm calibration UI.

Modes:
    --image PATH     load a static photo (offline; no camera needed)
    --live           grab a single frame from the ZED pipeline

Workflow:
    1. UI shows the image with the next target's known robot (X, Y) in the title.
    2. Operator left-clicks the marker centre.
    3. Press 'y' to confirm the click and advance, 'n' to redo, 'q' to quit.
    4. Once all targets are clicked, the polynomial fit + work zone are computed
       and saved to the --out JSON path. An annotated result image is also
       written next to it (disable with --result-image "").

Usage:
    python -m vision.calibration.ui --image samples/top_down.jpg \
        --grid 3x3 --spacing 100 --out calibration/calibration.json

Notes:
    - The order of targets is row-major from top-left of the printed grid.
      Place the printed grid so its row/col directions match the robot's +X/+Y
      axes (or rotate the printout to compensate).
    - --pick-height-z sets the configured pick Z in robot mm (default -940).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass

from .core import (
    Calibration,
    CalibrationPoint,
    DEFAULT_PICK_HEIGHT_MM,
    auto_select_degree,
    derive_work_zone,
    fit_polynomial,
    generate_grid_targets,
    save_calibration,
)
from .draw import draw_result_image


@dataclass
class _ClickState:
    last_click: tuple[int, int] | None = None


def _parse_grid(grid_str: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", grid_str)
    if not m:
        raise argparse.ArgumentTypeError(
            f"--grid must look like ROWSxCOLS (e.g. '3x3'), got {grid_str!r}"
        )
    rows, cols = int(m.group(1)), int(m.group(2))
    if rows < 1 or cols < 1:
        raise argparse.ArgumentTypeError("grid rows and cols must be >= 1")
    return rows, cols


def _load_static_image(path: str):
    import cv2  # local import so unit tests don't require opencv

    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {path}")
    return img


def _grab_live_frame():
    # Local import isolates the click UI from the camera module — running
    # `--image` mode never touches vision.vision.
    from vision.vision import ImageRecognition

    vision = ImageRecognition(auto_start=True)
    if not vision._zed_enabled:
        vision.stop()
        raise RuntimeError(
            "Could not start ZED camera. Run `python -m tests.diagnose_zed`."
        )

    try:
        frame = vision.get_frame()
        if frame is None:
            raise RuntimeError("ZED returned no frame.")
        rgb = frame.get("annotated_rgb")
        if rgb is None:
            rgb = frame.get("rgb")
        if rgb is None:
            raise RuntimeError("ZED frame had no RGB image.")
        return rgb
    finally:
        vision.stop()


def _draw_overlay(img, targets, collected, current_idx):
    import cv2

    overlay = img.copy()
    for i, p in enumerate(collected):
        cv2.circle(overlay, (int(p.u), int(p.v)), 6, (0, 220, 0), -1)
        cv2.putText(
            overlay,
            f"{i + 1}",
            (int(p.u) + 8, int(p.v) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 220, 0),
            1,
        )

    if 0 <= current_idx < len(targets):
        x_mm, y_mm = targets[current_idx]
        cv2.putText(
            overlay,
            f"Click marker {current_idx + 1}/{len(targets)}: "
            f"X={x_mm:.0f} Y={y_mm:.0f} mm",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 220, 220),
            2,
        )
        cv2.putText(
            overlay,
            "y=confirm  n=redo  q=quit",
            (10, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
        )
    return overlay


def collect_clicks_for_targets(img, targets):
    """Show img, ask the operator to click each target in order, return list of
    CalibrationPoint."""
    import cv2

    state = _ClickState()
    window = "Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.last_click = (x, y)

    cv2.setMouseCallback(window, on_mouse)

    collected: list[CalibrationPoint] = []
    idx = 0

    while idx < len(targets):
        overlay = _draw_overlay(img, targets, collected, idx)
        if state.last_click is not None:
            cx, cy = state.last_click
            cv2.drawMarker(overlay, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 16, 2)

        cv2.imshow(window, overlay)
        key = cv2.waitKey(20) & 0xFF

        if key == ord("q"):
            cv2.destroyWindow(window)
            raise KeyboardInterrupt("Calibration aborted by user")
        if key == ord("n"):
            state.last_click = None
            continue
        if key == ord("y") and state.last_click is not None:
            x_mm, y_mm = targets[idx]
            collected.append(
                CalibrationPoint(
                    u=float(state.last_click[0]),
                    v=float(state.last_click[1]),
                    x_mm=float(x_mm),
                    y_mm=float(y_mm),
                )
            )
            state.last_click = None
            idx += 1

    cv2.destroyWindow(window)
    return collected


def _corner_target_indices(rows: int, cols: int) -> list[int]:
    """Return unique grid indices for the 4 corners in row-major targets."""
    idx = [
        0,  # top-left
        cols - 1,  # top-right
        (rows - 1) * cols,  # bottom-left
        rows * cols - 1,  # bottom-right
    ]
    # De-duplicate for degenerate grids (e.g. 1xN).
    out: list[int] = []
    for i in idx:
        if i not in out:
            out.append(i)
    return out


def _expand_from_corner_clicks(
    rows: int,
    cols: int,
    all_targets: list[tuple[float, float]],
    corner_clicks: list[CalibrationPoint],
) -> list[CalibrationPoint]:
    """Build full-grid calibration points from 4 corner clicks.

    Pixel coordinates are bilinearly interpolated across the grid from the 4
    clicked corners while robot-space coordinates come from `all_targets`.
    """
    if len(corner_clicks) < 4:
        raise ValueError("Need 4 corner clicks to expand a full grid.")

    # Corner click order is fixed by _corner_target_indices:
    #   0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right
    tl, tr, bl, br = corner_clicks[0], corner_clicks[1], corner_clicks[2], corner_clicks[3]

    points: list[CalibrationPoint] = []
    for r in range(rows):
        t = 0.0 if rows == 1 else r / float(rows - 1)
        for c in range(cols):
            s = 0.0 if cols == 1 else c / float(cols - 1)
            # Bilinear interpolation in image pixel space.
            u = (
                (1.0 - s) * (1.0 - t) * tl.u
                + s * (1.0 - t) * tr.u
                + (1.0 - s) * t * bl.u
                + s * t * br.u
            )
            v = (
                (1.0 - s) * (1.0 - t) * tl.v
                + s * (1.0 - t) * tr.v
                + (1.0 - s) * t * bl.v
                + s * t * br.v
            )
            x_mm, y_mm = all_targets[r * cols + c]
            points.append(
                CalibrationPoint(
                    u=float(u),
                    v=float(v),
                    x_mm=float(x_mm),
                    y_mm=float(y_mm),
                )
            )
    return points


def run_calibration(
    image,
    targets,
    out_path: str,
    pick_height_z_mm: float,
    notes: str,
    degree: int | None = None,
    result_image_path: str | None = None,
    precollected_points: list[CalibrationPoint] | None = None,
) -> Calibration:
    points = precollected_points
    if points is None:
        points = collect_clicks_for_targets(image, targets)
    if not points:
        raise RuntimeError("No calibration points collected.")

    chosen_degree = degree if degree is not None else auto_select_degree(len(points))
    fit = fit_polynomial(points, degree=chosen_degree)
    zone = derive_work_zone(points)

    h, w = image.shape[:2]
    calibration = Calibration(
        image_size=(int(w), int(h)),
        fit=fit,
        points=points,
        work_zone=zone,
        pick_height_z_mm=pick_height_z_mm,
        notes=notes,
    )
    save_calibration(out_path, calibration)

    if result_image_path:
        draw_result_image(image, calibration, result_image_path)

    return calibration


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Interactive camera calibration tool")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="Path to a static photo to calibrate against")
    src.add_argument("--live", action="store_true", help="Grab a frame from the ZED")

    p.add_argument(
        "--grid",
        default="3x3",
        type=_parse_grid,
        help="Marker grid size, e.g. 3x3 or 4x4 (default: 3x3)",
    )
    p.add_argument(
        "--spacing",
        type=float,
        default=100.0,
        help="Spacing between markers in mm (default: 100)",
    )
    p.add_argument(
        "--center-x", type=float, default=0.0, help="Grid centre X in robot mm"
    )
    p.add_argument(
        "--center-y", type=float, default=0.0, help="Grid centre Y in robot mm"
    )
    p.add_argument(
        "--out",
        default="calibration/calibration.json",
        help="Output JSON path (default: calibration/calibration.json)",
    )
    p.add_argument(
        "--pick-height-z",
        type=float,
        default=DEFAULT_PICK_HEIGHT_MM,
        help=f"Pick height Z in robot mm (default: {DEFAULT_PICK_HEIGHT_MM})",
    )
    p.add_argument("--notes", default="", help="Free-text notes saved into the JSON")
    p.add_argument(
        "--degree",
        type=int,
        default=None,
        choices=[1, 2, 3],
        help=(
            "Polynomial degree (default: auto; 1 for <6 points, "
            "2 for 6-15 points, 3 for >=16 points)"
        ),
    )
    p.add_argument(
        "--result-image",
        default=None,
        help=(
            "Path for an annotated PNG verifying the calibration. "
            "Default: same dir as --out, named calibration_result.png. "
            "Pass empty string to disable."
        ),
    )
    p.add_argument(
        "--corner-4pt",
        action="store_true",
        help=(
            "Click only the 4 corner markers, then interpolate all inner grid "
            "points algorithmically before fitting."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    rows, cols = args.grid

    targets = generate_grid_targets(
        rows=rows,
        cols=cols,
        spacing_mm=args.spacing,
        center_x_mm=args.center_x,
        center_y_mm=args.center_y,
    )

    if args.image:
        if not os.path.isfile(args.image):
            print(f"ERROR: image not found: {args.image}", file=sys.stderr)
            return 2
        image = _load_static_image(args.image)
    else:
        image = _grab_live_frame()

    use_4pt = bool(args.corner_4pt)
    if use_4pt and (rows < 2 or cols < 2):
        print("ERROR: --corner-4pt requires a grid of at least 2x2.", file=sys.stderr)
        return 2

    print(f"Calibrating against {rows}x{cols} grid ({len(targets)} markers).")
    if use_4pt:
        print("4-point mode: click corners in this order:")
        print("  1) top-left  2) top-right  3) bottom-left  4) bottom-right")
        corner_idx = _corner_target_indices(rows, cols)
        click_targets = [targets[i] for i in corner_idx]
        clicked = collect_clicks_for_targets(image, click_targets)
        if len(clicked) != 4:
            print("ERROR: expected 4 corner clicks.", file=sys.stderr)
            return 1
        calibration_targets = _expand_from_corner_clicks(rows, cols, targets, clicked)
    else:
        print("Click each marker in row-major order (top-left first).")
        calibration_targets = targets

    if args.result_image is None:
        out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
        result_image_path: str | None = os.path.join(out_dir, "calibration_result.png")
    elif args.result_image == "":
        result_image_path = None
    else:
        result_image_path = args.result_image

    try:
        calibration = run_calibration(
            image=image,
            targets=targets,
            out_path=args.out,
            pick_height_z_mm=args.pick_height_z,
            notes=args.notes,
            degree=args.degree,
            result_image_path=result_image_path,
            precollected_points=(calibration_targets if use_4pt else None),
        )
    except KeyboardInterrupt:
        print("Calibration aborted.", file=sys.stderr)
        return 1

    print(f"Saved calibration to {args.out}")
    print(f"  fit: poly{calibration.fit.degree}, "
          f"RMS residual: {calibration.fit.rms_residual_mm:.2f} mm")
    z = calibration.work_zone
    print(
        f"  work zone (mm): X[{z.x_min:.0f}, {z.x_max:.0f}] "
        f"Y[{z.y_min:.0f}, {z.y_max:.0f}]"
    )
    if result_image_path:
        print(f"  result image: {result_image_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
