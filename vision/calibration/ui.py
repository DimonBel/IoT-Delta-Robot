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
        rgb = frame.get("annotated_rgb") or frame.get("rgb")
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


def run_calibration(
    image,
    targets,
    out_path: str,
    pick_height_z_mm: float,
    notes: str,
    degree: int | None = None,
    result_image_path: str | None = None,
) -> Calibration:
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
        help="Polynomial degree (default: auto, 2 below 16 points, 3 above)",
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

    print(f"Calibrating against {rows}x{cols} grid ({len(targets)} markers).")
    print("Click each marker in row-major order (top-left first).")

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
