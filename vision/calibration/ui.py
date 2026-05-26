"""Interactive 5-click calibration UI.

Click all 4 corners of the printed square + the robot home position.

Modes:
    --image PATH    load a static photo (offline, no camera needed)
    --live          grab a frame from the ZED camera

Usage:
    python -m vision.calibration.ui --live --side 980 --home-x 0 --home-y 0
    python -m vision.calibration.ui --image samples/board.jpg --side 980

Workflow (5 clicks, robot-frame labels — NOT image-space "top/bottom"):
    1. Corner at (-X, -Y).
    2. Corner at (-X, +Y).
    3. Corner at (+X, -Y).
    4. Corner at (+X, +Y).
    5. Robot HOME position (where the gripper tip is when robot is at home).

Press Y / Enter / Space to confirm each click, N to redo, Q / Esc to abort.

Geometry (square centred at robot origin (0, 0)):
    (-X, -Y) = (-side/2, -side/2)     (+X, -Y) = (+side/2, -side/2)
    (-X, +Y) = (-side/2, +side/2)     (+X, +Y) = (+side/2, +side/2)
    HOME = (--home-x, --home-y)       (anywhere inside or near the square)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from .core import (
    Calibration,
    CalibrationPoint,
    DEFAULT_PICK_HEIGHT_MM,
    auto_select_degree,
    build_square_calibration_points,
    derive_work_zone,
    fit_polynomial,
    infer_hidden_corner,
    save_calibration,
)
from .draw import draw_result_image


@dataclass
class _ClickState:
    last_click: tuple[int, int] | None = None


# Stage labels (robot-frame coordinates, NOT image-space "top/bottom").
_STAGE_LABELS = (
    "1/5  Corner at (-X, -Y)",
    "2/5  Corner at (-X, +Y)",
    "3/5  Corner at (+X, -Y)",
    "4/5  Corner at (+X, +Y)",
    "5/5  ROBOT HOME (gripper position; mm given by --home-x / --home-y)",
)


# ----- keyboard helpers ------------------------------------------------

def _cv_read_key(delay_ms: int) -> int:
    """cv2.waitKeyEx wrapper; falls back to waitKey when not available."""
    import cv2

    wk = getattr(cv2, "waitKeyEx", cv2.waitKey)
    return int(wk(delay_ms))


def _cv_key_confirm(code: int) -> bool:
    if code < 0:
        return False
    k = code & 0xFF
    if k in (ord("y"), ord("Y"), 13, 10, ord(" ")):
        return True
    hi = (code >> 16) & 0xFF
    return hi in (13, 10)


def _cv_key_redo(code: int) -> bool:
    if code < 0:
        return False
    return (code & 0xFF) in (ord("n"), ord("N"))


def _cv_key_quit(code: int) -> bool:
    if code < 0:
        return False
    return (code & 0xFF) in (ord("q"), ord("Q"), 27)


# ----- frame sources ---------------------------------------------------

def _load_static_image(path: str):
    import cv2

    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {path}")
    return img


def _bgr_from_zed_frame(frame: dict, *, prefer_clean: bool = True):
    """Pull the clean RGB BGR array out of a vision.get_frame() payload."""
    if prefer_clean:
        img = frame.get("rgb")
        if img is None:
            img = frame.get("annotated_rgb")
    else:
        img = frame.get("annotated_rgb")
        if img is None:
            img = frame.get("rgb")
    return img


def _grab_live_frame(*, preview: bool, warmup_frames: int = 5):
    """Acquire one BGR frame from the ZED pipeline."""
    import cv2
    from vision.vision import ImageRecognition

    vision = ImageRecognition(auto_start=True)
    if not vision._zed_enabled:
        vision.stop()
        raise RuntimeError(
            "Could not start ZED camera. Run `python -m tests.diagnose_zed`."
        )

    def _warmup_and_grab():
        frame = None
        for _ in range(max(1, warmup_frames)):
            frame = vision.get_frame()
            if frame is not None:
                break
        if frame is None:
            raise RuntimeError("ZED returned no frame.")
        img = _bgr_from_zed_frame(frame, prefer_clean=True)
        if img is None:
            raise RuntimeError("ZED frame had no RGB image.")
        return img

    window = "Calib camera live (SPACE or C=capture Q=quit)"
    try:
        if not preview:
            return _warmup_and_grab()

        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        captured = None
        print(
            "Calib camera: aim the board, click the image window, "
            "then SPACE or C to capture, Q to abort.",
            flush=True,
        )
        try:
            while captured is None:
                frame = vision.get_frame()
                if frame is None:
                    _cv_read_key(50)
                    continue
                display = _bgr_from_zed_frame(frame, prefer_clean=True)
                if display is None:
                    _cv_read_key(50)
                    continue
                cv2.imshow(window, display)
                key = _cv_read_key(1)
                kb = key & 0xFF
                if kb in (ord(" "), ord("c"), ord("C")):
                    captured = display.copy()
                elif _cv_key_quit(key):
                    raise KeyboardInterrupt("Live preview aborted")
        finally:
            cv2.destroyWindow(window)
        return captured
    finally:
        vision.stop()


# ----- click collection ------------------------------------------------

_STAGE_COLOURS_BGR = [
    (0, 220, 0),     # TL corner - green
    (0, 220, 0),     # TR corner - green
    (0, 220, 0),     # BL corner - green
    (0, 200, 220),   # right edge helper - amber
    (0, 200, 220),   # bottom edge helper - amber
    (0, 0, 220),     # home - red
]


def _draw_six_overlay(img, collected_px, current_idx, pending_click):
    """Draw the in-progress 6-click overlay with stage label + collected points."""
    import cv2

    overlay = img.copy()
    for i, (cx, cy) in enumerate(collected_px):
        colour = _STAGE_COLOURS_BGR[i]
        cv2.circle(overlay, (int(cx), int(cy)), 6, colour, -1)
        cv2.putText(
            overlay, str(i + 1), (int(cx) + 8, int(cy) - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1,
        )

    if pending_click is not None:
        px, py = pending_click
        cv2.drawMarker(overlay, (int(px), int(py)), (0, 0, 255),
                       cv2.MARKER_CROSS, 16, 2)

    if 0 <= current_idx < len(_STAGE_LABELS):
        label = _STAGE_LABELS[current_idx]
        cv2.putText(
            overlay, label, (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 220), 2,
        )
        cv2.putText(
            overlay, "Y or Enter=confirm   N=redo   Q=quit",
            (10, 48),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
        )
    return overlay


def collect_six_clicks(img) -> list[tuple[float, float]]:
    """Walk the operator through the 6 stages. Returns 6 (u, v) pixel pairs.

    Raises KeyboardInterrupt if the operator aborts.
    """
    import cv2

    state = _ClickState()
    window = "Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.last_click = (x, y)

    cv2.setMouseCallback(window, on_mouse)

    collected: list[tuple[float, float]] = []
    idx = 0
    try:
        while idx < len(_STAGE_LABELS):
            overlay = _draw_six_overlay(img, collected, idx, state.last_click)
            cv2.imshow(window, overlay)
            key = _cv_read_key(30)

            if _cv_key_quit(key):
                raise KeyboardInterrupt("Calibration aborted by user")
            if _cv_key_redo(key):
                state.last_click = None
                continue
            if _cv_key_confirm(key) and state.last_click is not None:
                collected.append(
                    (float(state.last_click[0]), float(state.last_click[1]))
                )
                state.last_click = None
                idx += 1
    finally:
        cv2.destroyWindow(window)
    return collected


# ----- fit + IO --------------------------------------------------------

def build_calibration(
    image,
    points: list[CalibrationPoint],
    *,
    robot_home_mm: tuple[float, float],
    pick_height_z_mm: float,
    notes: str,
    degree: int | None,
) -> Calibration:
    if not points:
        raise RuntimeError("No calibration points collected.")
    chosen_degree = degree if degree is not None else auto_select_degree(len(points))
    fit = fit_polynomial(points, degree=chosen_degree)
    zone = derive_work_zone(points)
    h, w = image.shape[:2]
    return Calibration(
        image_size=(int(w), int(h)),
        fit=fit,
        points=points,
        work_zone=zone,
        robot_home_mm=(float(robot_home_mm[0]), float(robot_home_mm[1])),
        pick_height_z_mm=pick_height_z_mm,
        notes=notes,
    )


def write_calibration_artifacts(
    calibration: Calibration,
    image,
    out_path: str,
    result_image_path: str | None,
) -> None:
    save_calibration(out_path, calibration)
    if result_image_path:
        draw_result_image(image, calibration, result_image_path)


# ----- CLI -------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="6-click camera calibration tool")

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="Path to a static photo (offline, no camera)")
    src.add_argument(
        "--live", action="store_true",
        help="Grab a frame from the ZED camera (see --live-preview)",
    )

    p.add_argument(
        "--side", type=float, default=200.0,
        help="Side length of the printed square in mm (default: 200)",
    )
    p.add_argument(
        "--home-x", type=float, default=0.0,
        help="Robot X of the home pixel in mm (default: 0)",
    )
    p.add_argument(
        "--home-y", type=float, default=0.0,
        help="Robot Y of the home pixel in mm (default: 0)",
    )
    p.add_argument(
        "--out", default="calibration/calibration.json",
        help="Output JSON path (default: calibration/calibration.json)",
    )
    p.add_argument(
        "--pick-height-z", type=float, default=DEFAULT_PICK_HEIGHT_MM,
        help=f"Robot Z used at pick-time (default: {DEFAULT_PICK_HEIGHT_MM})",
    )
    p.add_argument("--notes", default="", help="Free-text note saved in the JSON")
    p.add_argument(
        "--degree", type=int, default=None, choices=[1, 2, 3],
        help="Polynomial degree override (default: auto = 1 for 5 points)",
    )
    p.add_argument(
        "--result-image", default=None,
        help=(
            "Path for an annotated PNG verifying the calibration. "
            "Default: same dir as --out, named calibration_result.png. "
            "Pass empty string to disable."
        ),
    )
    p.add_argument(
        "--live-preview", action="store_true",
        help="With --live: show a live window until SPACE/C captures the frame",
    )
    p.add_argument(
        "--live-warmup-frames", type=int, default=5,
        help="With --live (no preview): discard N frames before grabbing (default 5)",
    )
    p.add_argument(
        "--save-camera-frame", default="",
        help="With --live: save the captured BGR frame to this path before clicking",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.side <= 0:
        print("ERROR: --side must be positive", file=sys.stderr)
        return 2
    if args.live_warmup_frames < 1:
        print("ERROR: --live-warmup-frames must be >= 1", file=sys.stderr)
        return 2
    if args.live_preview and not args.live:
        print("ERROR: --live-preview requires --live", file=sys.stderr)
        return 2

    if args.image:
        if not os.path.isfile(args.image):
            print(f"ERROR: image not found: {args.image}", file=sys.stderr)
            return 2
        image = _load_static_image(args.image)
    else:
        try:
            image = _grab_live_frame(
                preview=args.live_preview,
                warmup_frames=args.live_warmup_frames,
            )
        except KeyboardInterrupt:
            print("Live capture aborted.", file=sys.stderr)
            return 1

    if args.live and args.save_camera_frame:
        import cv2
        os.makedirs(os.path.dirname(os.path.abspath(args.save_camera_frame)) or ".", exist_ok=True)
        if not cv2.imwrite(args.save_camera_frame, image):
            print(f"ERROR: failed to write --save-camera-frame {args.save_camera_frame}",
                  file=sys.stderr)
            return 2
        print(f"Saved captured frame to {args.save_camera_frame}")

    if args.result_image is None:
        out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
        result_image_path: str | None = os.path.join(out_dir, "calibration_result.png")
    elif args.result_image == "":
        result_image_path = None
    else:
        result_image_path = args.result_image

    print(
        f"6-click calibration: side={args.side:.0f} mm, "
        f"home=({args.home_x:.0f}, {args.home_y:.0f}) mm. "
        f"Square is centred at robot origin (0, 0)."
    )
    print("Click each stage in order; press Y/Enter to confirm, N to redo, Q to abort.")
    for label in _STAGE_LABELS:
        print(f"  {label}")

    try:
        clicks = collect_six_clicks(image)
    except KeyboardInterrupt:
        print("Calibration aborted.", file=sys.stderr)
        return 1

    if len(clicks) != 6:
        print(f"ERROR: expected 6 clicks, got {len(clicks)}", file=sys.stderr)
        return 1

    mxmy_uv, mxpy_uv, pxmy_uv, helper_px_edge, helper_py_edge, home_uv = clicks

    try:
        pxpy_uv = infer_hidden_corner(
            corner_a_uv=pxmy_uv,    helper_a_uv=helper_px_edge,
            corner_b_uv=mxpy_uv,    helper_b_uv=helper_py_edge,
        )
    except ValueError as exc:
        print(f"ERROR: could not infer hidden (+X, +Y) corner: {exc}", file=sys.stderr)
        return 1

    print(
        f"Inferred (+X, +Y) corner pixel: ({pxpy_uv[0]:.1f}, {pxpy_uv[1]:.1f})"
    )

    points = build_square_calibration_points(
        mxmy_uv=mxmy_uv, mxpy_uv=mxpy_uv, pxmy_uv=pxmy_uv, pxpy_uv=pxpy_uv,
        home_uv=home_uv,
        side_mm=args.side,
        home_x_mm=args.home_x, home_y_mm=args.home_y,
    )

    calibration = build_calibration(
        image=image,
        points=points,
        robot_home_mm=(args.home_x, args.home_y),
        pick_height_z_mm=args.pick_height_z,
        notes=args.notes,
        degree=args.degree,
    )
    write_calibration_artifacts(
        calibration=calibration,
        image=image,
        out_path=args.out,
        result_image_path=result_image_path,
    )

    print(f"Saved calibration to {args.out}")
    print(f"  fit: poly{calibration.fit.degree}, "
          f"RMS residual: {calibration.fit.rms_residual_mm:.2f} mm")
    z = calibration.work_zone
    print(
        f"  work zone (mm): X[{z.x_min:.0f}, {z.x_max:.0f}] "
        f"Y[{z.y_min:.0f}, {z.y_max:.0f}]"
    )
    print(
        f"  robot home (mm): X={calibration.robot_home_mm[0]:.0f}  "
        f"Y={calibration.robot_home_mm[1]:.0f}"
    )
    if result_image_path:
        print(f"  result image: {result_image_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
