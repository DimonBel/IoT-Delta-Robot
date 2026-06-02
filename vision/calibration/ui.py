"""Interactive camera calibration UI.

DATASET MODE (recommended — default when calibration/points.txt exists):
    Reads robot X,Y positions from a text file (format: "N:(X;Y)" per line).
    For each point the OpenCV window shows its robot coordinates; move the
    robot arm to that position and click the gripper tip in the image.
    After all points a homography is computed and the RMS residual printed.

    Usage:
        python -m vision.calibration.ui --live
        python -m vision.calibration.ui --live --points-file calibration/points.txt

MANUAL MODE (fallback when no points file):
    Click the 3 visible corners + robot HOME, entering coordinates after each.

LEGACY MODE (--side):
    Original 6-click polynomial flow, kept for reference.

Usage:
    python -m vision.calibration.ui --live
    python -m vision.calibration.ui --image samples/board.jpg
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
    HomographyFit,
    auto_select_degree,
    build_square_calibration_points,
    derive_work_zone,
    fit_homography,
    fit_polynomial,
    infer_hidden_corner,
    save_calibration,
)
from .draw import draw_result_image


@dataclass
class _ClickState:
    last_click: tuple[int, int] | None = None


# ── keyboard helpers ──────────────────────────────────────────────────────────

def _cv_read_key(delay_ms: int) -> int:
    import cv2
    wk = getattr(cv2, "waitKeyEx", cv2.waitKey)
    return int(wk(delay_ms))


def _cv_key_confirm(code: int) -> bool:
    if code < 0:
        return False
    k = code & 0xFF
    if k in (ord("y"), ord("Y"), 13, 10, ord(" ")):
        return True
    return (code >> 16) & 0xFF in (13, 10)


def _cv_key_redo(code: int) -> bool:
    if code < 0:
        return False
    return (code & 0xFF) in (ord("n"), ord("N"))


def _cv_key_quit(code: int) -> bool:
    if code < 0:
        return False
    return (code & 0xFF) in (ord("q"), ord("Q"), 27)


# ── frame sources ─────────────────────────────────────────────────────────────

def _load_static_image(path: str):
    import cv2
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {path}")
    return img


def _bgr_from_zed_frame(frame: dict, *, prefer_clean: bool = True):
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


# ── shared overlay drawing ────────────────────────────────────────────────────

_POINT_COLOURS_BGR = [
    (0, 220, 0),    # corners 1-4  — green
    (0, 220, 0),
    (0, 220, 0),
    (0, 220, 0),
    (0, 200, 220),  # extra points — amber
    (0, 200, 220),
    (0, 200, 220),
    (0, 200, 220),
]


def _draw_overlay(img, confirmed_px, stage_idx: int, pending_click, label: str):
    import cv2
    overlay = img.copy()
    for i, (cx, cy) in enumerate(confirmed_px):
        c = _POINT_COLOURS_BGR[min(i, len(_POINT_COLOURS_BGR) - 1)]
        cv2.circle(overlay, (int(cx), int(cy)), 6, c, -1)
        cv2.putText(overlay, str(i + 1), (int(cx) + 8, int(cy) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)
    if pending_click is not None:
        cv2.drawMarker(overlay, (int(pending_click[0]), int(pending_click[1])),
                       (0, 0, 255), cv2.MARKER_CROSS, 16, 2)
    cv2.putText(overlay, label, (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 220), 2)
    cv2.putText(overlay, "Y/Enter=confirm   N=redo   Q=quit",
                (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    return overlay


# ── DATASET MODE: read robot positions from file, click each in image ─────────

# Human-readable display names for named labels in the points file.
_LABEL_DISPLAY = {
    "-x-y": "(-X, -Y) corner",
    "+x-y": "(+X, -Y) corner",
    "-x+y": "(-X, +Y) corner",
    "+x+y": "(+X, +Y) corner",
    "home": "HOME",
}


def _display_name(label: str) -> str:
    """Convert a raw file label to a friendly display string."""
    if label in _LABEL_DISPLAY:
        return _LABEL_DISPLAY[label]
    try:
        return f"Point {int(label)}"
    except ValueError:
        return label


def parse_points_file(path: str) -> list[tuple[str, float, float]]:
    """Parse calibration/points.txt.  Each line: 'label:(X;Y)'.

    label can be a named key (-x-y, +x-y, -x+y, home) or a plain integer.
    Returns list of (label, x_mm, y_mm) in file order — no sorting, order matters.

    Supported examples:
        -x-y:(-470;-430)
        home:(-4.5;-5.5)
        1:(+95;+94)
    """
    points: list[tuple[str, float, float]] = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            colon = line.index(":")
            label = line[:colon].strip()
            inner = line[colon + 1:].strip().strip("()")
            x_str, y_str = inner.split(";")
            points.append((label, float(x_str.strip()), float(y_str.strip())))
    return points


def _draw_overlay_dataset(img,
                          confirmed: list[tuple[float, float, float, float]],
                          current_idx: int, total: int,
                          current_x: float, current_y: float,
                          display_label: str,
                          pending_click) -> object:
    """Dark-banner overlay showing the target robot position and all confirmed dots."""
    import cv2
    overlay = img.copy()
    h_img, w_img = overlay.shape[:2]

    # Confirmed points — green dots with small coord tag
    for i, (pu, pv, px, py) in enumerate(confirmed):
        cv2.circle(overlay, (int(pu), int(pv)), 7, (0, 220, 0), -1)
        cv2.circle(overlay, (int(pu), int(pv)), 7, (255, 255, 255), 1)
        tag = f"{i + 1}: ({px:+.0f},{py:+.0f})"
        cv2.putText(overlay, tag, (int(pu) + 9, int(pv) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 2)
        cv2.putText(overlay, tag, (int(pu) + 9, int(pv) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 240, 0), 1)

    # Pending crosshair
    if pending_click is not None:
        cv2.drawMarker(overlay, (int(pending_click[0]), int(pending_click[1])),
                       (0, 80, 255), cv2.MARKER_CROSS, 20, 2)

    # Top banner
    banner_h = 78
    cv2.rectangle(overlay, (0, 0), (w_img, banner_h), (20, 20, 20), -1)
    cv2.putText(overlay,
                f"{current_idx}/{total}  —  {display_label}",
                (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (100, 220, 255), 2)
    cv2.putText(overlay,
                f"Robot  X = {current_x:+.1f} mm    Y = {current_y:+.1f} mm",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    # Bottom hint
    cv2.putText(overlay,
                "Move robot to position above  |  Click gripper tip  |  Y=confirm  N=redo  Q=abort",
                (8, h_img - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    return overlay


def collect_from_dataset(img,
                         robot_points: list[tuple[str, float, float]],
                         ) -> list[tuple[float, float, float, float]]:
    """Click the pixel location for each robot position in robot_points.

    robot_points: list of (label, x_mm, y_mm) as returned by parse_points_file.
    Returns: list of (u, v, x_mm, y_mm) for every confirmed click.
    """
    import cv2

    state = _ClickState()
    window = "Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.last_click = (x, y)

    cv2.setMouseCallback(window, on_mouse)

    results: list[tuple[float, float, float, float]] = []
    total = len(robot_points)

    print(f"\n=== Dataset calibration: {total} points ===")
    print("Move the robot arm to each shown position, click the gripper tip, press Y.\n")

    try:
        for seq_i, (label, x_mm, y_mm) in enumerate(robot_points):
            display_label = _display_name(label)
            state.last_click = None
            print(f"Point {seq_i + 1}/{total}  [{display_label}]  →  X={x_mm:+.1f} mm  Y={y_mm:+.1f} mm")

            while True:
                overlay = _draw_overlay_dataset(
                    img, results, seq_i + 1, total,
                    x_mm, y_mm, display_label, state.last_click,
                )
                cv2.imshow(window, overlay)
                key = _cv_read_key(30)
                if _cv_key_quit(key):
                    raise KeyboardInterrupt("Calibration aborted")
                if _cv_key_redo(key):
                    state.last_click = None
                if _cv_key_confirm(key) and state.last_click is not None:
                    u, v = float(state.last_click[0]), float(state.last_click[1])
                    results.append((u, v, x_mm, y_mm))
                    print(f"  ✓  pixel ({u:.0f}, {v:.0f})")
                    state.last_click = None
                    break

            if len(results) >= 4:
                pts = [CalibrationPoint(u=r[0], v=r[1], x_mm=r[2], y_mm=r[3])
                       for r in results]
                try:
                    fit = fit_homography(pts)
                    print(f"  Running RMS: {fit.rms_residual_mm:.2f} mm  "
                          f"({len(results)} pts total)")
                except Exception:
                    pass

    finally:
        cv2.destroyWindow(window)

    return results


# ── PRIMARY: 4-corner homography flow ─────────────────────────────────────────

def _wait_for_click(img, window: str, state: _ClickState,
                    confirmed_px: list, label: str) -> tuple[float, float] | None:
    """Block until the user confirms a click (Y) or quits (Q)."""
    import cv2
    state.last_click = None
    while True:
        overlay = _draw_overlay(img, confirmed_px, len(confirmed_px),
                                state.last_click, label)
        cv2.imshow(window, overlay)
        key = _cv_read_key(30)
        if _cv_key_quit(key):
            return None
        if _cv_key_redo(key):
            state.last_click = None
        if _cv_key_confirm(key) and state.last_click is not None:
            return float(state.last_click[0]), float(state.last_click[1])


def _prompt_robot_xy(label: str) -> tuple[float, float]:
    """Terminal prompt for robot (X, Y) in mm with retry on bad input."""
    while True:
        try:
            x = float(input(f"  Robot X [{label}] in mm  (e.g. 200 or -150.5): "))
            y = float(input(f"  Robot Y [{label}] in mm  (e.g. 200 or -150.5): "))
            return x, y
        except ValueError:
            print("  ✗ Enter a plain number in mm, no units (e.g. -280 or 87.5)")
        except EOFError:
            raise KeyboardInterrupt("Input stream closed")


def _compute_and_print_rms(results: list[tuple[float, float, float, float]]) -> float:
    points = [CalibrationPoint(u=r[0], v=r[1], x_mm=r[2], y_mm=r[3])
              for r in results]
    fit = fit_homography(points)
    print(f"\n  Homography fit: {len(points)} points  |  RMS = {fit.rms_residual_mm:.2f} mm")
    return fit.rms_residual_mm


def collect_calibration_data(img) -> list[tuple[float, float, float, float]]:
    """4-corner + optional extra points.  Returns [(u, v, x_mm, y_mm), ...].

    Phase 1 — click the 4 corners of the active robot zone in any order.
              For each, enter its exact robot (X, Y) in the terminal.
    Phase 2 — add as many extra known points as desired to reduce RMS.
    """
    import cv2

    state = _ClickState()
    window = "Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.last_click = (x, y)

    cv2.setMouseCallback(window, on_mouse)

    results: list[tuple[float, float, float, float]] = []

    try:
        # ── Phase 1: exactly 4 points ──────────────────────────────────
        print("\n=== Phase 1: click 4 known points in the robot workspace ===")
        print("FORMAT: type the number in mm exactly as the robot controller shows.")
        print("  e.g.  X = 200   or   X = -150.5")
        print("The camera is near (+X,+Y) so that corner is SKIPPED.")
        print("Points 1-3 are the 3 visible corners; point 4 is the robot HOME (0, 0).\n")

        # (+X,+Y) is where the camera sits — not visible in the image.
        # Use the 3 remaining corners + robot HOME as the 4 spanning points.
        _CORNER_LABELS = [
            "(-X, -Y)  robot min-X  min-Y",
            "(-X, +Y)  robot min-X  max-Y",
            "(+X, -Y)  robot max-X  min-Y",
            "HOME (0, 0)  robot origin",
        ]

        for i in range(4):
            robot_label = _CORNER_LABELS[i]
            label = f"{i + 1}/4  Click  {robot_label}"
            confirmed = _wait_for_click(
                img, window, state,
                [(r[0], r[1]) for r in results], label,
            )
            if confirmed is None:
                raise KeyboardInterrupt("Calibration aborted")
            u, v = confirmed
            print(f"\nPoint {i + 1}: {robot_label}  pixel ({u:.0f}, {v:.0f})")
            x_mm, y_mm = _prompt_robot_xy(robot_label)
            results.append((u, v, x_mm, y_mm))
            print(f"  → pixel ({u:.0f}, {v:.0f})  =  robot X={x_mm:+.2f} mm  Y={y_mm:+.2f} mm")

        _compute_and_print_rms(results)

        # ── Phase 2: optional extra points ────────────────────────────
        print("\n=== Phase 2: add extra calibration points (optional) ===")
        print("More points improve accuracy.  Add known positions one at a time.")

        extra_n = 0
        while True:
            try:
                ans = input("\nAdd another calibration point? (y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break
            if ans not in ("y", "yes"):
                break

            extra_n += 1
            label = f"Extra {extra_n}  Click a point — enter its robot (X, Y) in terminal"
            confirmed = _wait_for_click(
                img, window, state,
                [(r[0], r[1]) for r in results], label,
            )
            if confirmed is None:
                break
            u, v = confirmed
            x_mm, y_mm = _prompt_robot_xy(f"extra point {extra_n}")
            results.append((u, v, x_mm, y_mm))
            print(f"  → pixel ({u:.0f}, {v:.0f})  =  robot ({x_mm:+.2f}, {y_mm:+.2f}) mm")
            _compute_and_print_rms(results)

    finally:
        cv2.destroyWindow(window)

    return results


def build_calibration_homography(
    image,
    data: list[tuple[float, float, float, float]],
    *,
    robot_home_mm: tuple[float, float],
    pick_height_z_mm: float,
    notes: str,
) -> Calibration:
    points = [CalibrationPoint(u=r[0], v=r[1], x_mm=r[2], y_mm=r[3])
              for r in data]
    fit = fit_homography(points)
    zone = derive_work_zone(points)
    h, w = image.shape[:2]
    return Calibration(
        image_size=(int(w), int(h)),
        fit=fit,
        points=points,
        work_zone=zone,
        robot_home_mm=robot_home_mm,
        pick_height_z_mm=pick_height_z_mm,
        notes=notes,
    )


# ── LEGACY: 6-click polynomial flow ──────────────────────────────────────────

_LEGACY_STAGE_LABELS = (
    "1/6  Corner at (-X, -Y)",
    "2/6  Corner at (-X, +Y)",
    "3/6  Corner at (+X, -Y)",
    "4/6  Helper on the +X edge (between (+X,-Y) and hidden (+X,+Y))",
    "5/6  Helper on the +Y edge (between (-X,+Y) and hidden (+X,+Y))",
    "6/6  ROBOT HOME (gripper position; mm given by --home-x / --home-y)",
)

_LEGACY_COLOURS_BGR = [
    (0, 220, 0),
    (0, 220, 0),
    (0, 220, 0),
    (0, 200, 220),
    (0, 200, 220),
    (0, 0, 220),
]


def _draw_overlay_legacy(img, collected_px, current_idx, pending_click):
    import cv2
    overlay = img.copy()
    for i, (cx, cy) in enumerate(collected_px):
        colour = _LEGACY_COLOURS_BGR[i]
        cv2.circle(overlay, (int(cx), int(cy)), 6, colour, -1)
        cv2.putText(overlay, str(i + 1), (int(cx) + 8, int(cy) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1)
    if pending_click is not None:
        px, py = pending_click
        cv2.drawMarker(overlay, (int(px), int(py)), (0, 0, 255),
                       cv2.MARKER_CROSS, 16, 2)
    if 0 <= current_idx < len(_LEGACY_STAGE_LABELS):
        label = _LEGACY_STAGE_LABELS[current_idx]
        cv2.putText(overlay, label, (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 220), 2)
        cv2.putText(overlay, "Y or Enter=confirm   N=redo   Q=quit", (10, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    return overlay


def collect_clicks_legacy(img) -> list[tuple[float, float]]:
    """Legacy 6-click flow.  Returns 6 (u, v) pairs."""
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
        while idx < len(_LEGACY_STAGE_LABELS):
            overlay = _draw_overlay_legacy(img, collected, idx, state.last_click)
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


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Camera calibration tool (homography or legacy polynomial)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="Path to a static photo (offline, no camera)")
    src.add_argument("--live", action="store_true",
                     help="Grab a frame from the ZED camera")

    p.add_argument(
        "--points-file",
        default="calibration/points.txt",
        help=(
            "Path to robot position dataset (default: calibration/points.txt). "
            "Format per line: 'N:(X;Y)' in mm.  "
            "When the file exists this dataset mode is used automatically."
        ),
    )
    p.add_argument(
        "--side", type=float, default=None,
        help=(
            "[Legacy] Side length of the printed square in mm. "
            "When omitted (default) the new 4-corner homography mode is used — "
            "more accurate and does not require a hidden corner."
        ),
    )
    p.add_argument("--home-x", type=float, default=0.0,
                   help="Robot X of the home position in mm (default: 0)")
    p.add_argument("--home-y", type=float, default=0.0,
                   help="Robot Y of the home position in mm (default: 0)")
    p.add_argument("--out", default="calibration/calibration.json",
                   help="Output JSON path (default: calibration/calibration.json)")
    p.add_argument("--pick-height-z", type=float, default=DEFAULT_PICK_HEIGHT_MM,
                   help=f"Robot Z at pick-time mm (default: {DEFAULT_PICK_HEIGHT_MM})")
    p.add_argument("--notes", default="", help="Free-text note saved in the JSON")
    p.add_argument("--degree", type=int, default=None, choices=[1, 2, 3],
                   help="[Legacy] Polynomial degree override (default: auto)")
    p.add_argument(
        "--result-image", default=None,
        help=(
            "Path for an annotated PNG verifying the calibration. "
            "Default: same dir as --out, named calibration_result.png. "
            "Pass empty string to disable."
        ),
    )
    p.add_argument("--live-preview", action="store_true",
                   help="With --live: show a live window until SPACE/C captures")
    p.add_argument("--live-warmup-frames", type=int, default=5,
                   help="With --live (no preview): discard N frames before grabbing (default 5)")
    p.add_argument("--save-camera-frame", default="",
                   help="With --live: save the captured frame to this path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.live_warmup_frames < 1:
        print("ERROR: --live-warmup-frames must be >= 1", file=sys.stderr)
        return 2
    if args.live_preview and not args.live:
        print("ERROR: --live-preview requires --live", file=sys.stderr)
        return 2
    if args.side is not None and args.side <= 0:
        print("ERROR: --side must be positive", file=sys.stderr)
        return 2

    # ── load image ──────────────────────────────────────────────────────
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

    robot_home_mm = (args.home_x, args.home_y)

    # ── choose calibration mode ─────────────────────────────────────────
    points_file = args.points_file
    use_dataset = args.side is None and os.path.isfile(points_file)

    if use_dataset:
        # ── DATASET: all points read from file, no manual input ────────
        try:
            robot_pts = parse_points_file(points_file)
        except Exception as exc:
            print(f"ERROR reading points file: {exc}", file=sys.stderr)
            return 2
        print(f"=== Dataset calibration: {len(robot_pts)} points from {points_file} ===")

        try:
            data = collect_from_dataset(image, robot_pts)
        except KeyboardInterrupt:
            print("Calibration aborted.", file=sys.stderr)
            return 1

        if len(data) < 4:
            print("ERROR: need at least 4 confirmed points.", file=sys.stderr)
            return 1

        calibration = build_calibration_homography(
            image=image,
            data=data,
            robot_home_mm=robot_home_mm,
            pick_height_z_mm=args.pick_height_z,
            notes=args.notes,
        )

    elif args.side is None:
        # ── MANUAL: 4-corner + extras with terminal coord entry ────────
        print("=== Homography calibration (manual 4-corner mode) ===")
        print(f"Home: ({args.home_x:.1f}, {args.home_y:.1f}) mm  "
              f"Pick Z: {args.pick_height_z:.0f} mm")

        try:
            data = collect_calibration_data(image)
        except KeyboardInterrupt:
            print("Calibration aborted.", file=sys.stderr)
            return 1

        if len(data) < 4:
            print("ERROR: need at least 4 calibration points.", file=sys.stderr)
            return 1

        calibration = build_calibration_homography(
            image=image,
            data=data,
            robot_home_mm=robot_home_mm,
            pick_height_z_mm=args.pick_height_z,
            notes=args.notes,
        )

    else:
        # ── LEGACY: 6-click polynomial ─────────────────────────────────
        print(
            f"[Legacy] 6-click calibration: side={args.side:.0f} mm, "
            f"home=({args.home_x:.0f}, {args.home_y:.0f}) mm."
        )
        print("Click each stage in order; press Y/Enter to confirm, N to redo, Q to abort.")
        for label in _LEGACY_STAGE_LABELS:
            print(f"  {label}")

        try:
            clicks = collect_clicks_legacy(image)
        except KeyboardInterrupt:
            print("Calibration aborted.", file=sys.stderr)
            return 1

        if len(clicks) != 6:
            print(f"ERROR: expected 6 clicks, got {len(clicks)}", file=sys.stderr)
            return 1

        mxmy_uv, mxpy_uv, pxmy_uv, helper_px_edge, helper_py_edge, home_uv = clicks

        try:
            pxpy_uv = infer_hidden_corner(
                corner_a_uv=pxmy_uv, helper_a_uv=helper_px_edge,
                corner_b_uv=mxpy_uv, helper_b_uv=helper_py_edge,
            )
        except ValueError as exc:
            print(f"ERROR: could not infer hidden (+X,+Y) corner: {exc}", file=sys.stderr)
            return 1

        # Validate the inferred corner is within (or near) the image
        h_img, w_img = image.shape[:2]
        margin = 0.25
        if not (
            -w_img * margin <= pxpy_uv[0] <= w_img * (1 + margin)
            and -h_img * margin <= pxpy_uv[1] <= h_img * (1 + margin)
        ):
            print(
                f"ERROR: inferred corner ({pxpy_uv[0]:.0f}, {pxpy_uv[1]:.0f}) "
                f"is far outside image {w_img}×{h_img}.",
                file=sys.stderr,
            )
            print(
                "       Place edge helpers further along the edges (closer to mid-edge).",
                file=sys.stderr,
            )
            return 1

        print(f"Inferred (+X,+Y) corner pixel: ({pxpy_uv[0]:.1f}, {pxpy_uv[1]:.1f})")

        points = build_square_calibration_points(
            mxmy_uv=mxmy_uv, mxpy_uv=mxpy_uv, pxmy_uv=pxmy_uv, pxpy_uv=pxpy_uv,
            home_uv=home_uv,
            side_mm=args.side,
            home_x_mm=args.home_x, home_y_mm=args.home_y,
        )
        calibration = build_calibration(
            image=image, points=points,
            robot_home_mm=robot_home_mm,
            pick_height_z_mm=args.pick_height_z,
            notes=args.notes, degree=args.degree,
        )

    # ── save ────────────────────────────────────────────────────────────
    write_calibration_artifacts(
        calibration=calibration,
        image=image,
        out_path=args.out,
        result_image_path=result_image_path,
    )

    fit = calibration.fit
    fit_label = "homography" if isinstance(fit, HomographyFit) else f"poly{fit.degree}"
    print(f"\nSaved calibration to {args.out}")
    print(f"  fit: {fit_label},  RMS residual: {fit.rms_residual_mm:.2f} mm")
    z = calibration.work_zone
    print(f"  work zone (mm): X[{z.x_min:.0f}, {z.x_max:.0f}]  "
          f"Y[{z.y_min:.0f}, {z.y_max:.0f}]")
    print(f"  robot home (mm): X={calibration.robot_home_mm[0]:.1f}  "
          f"Y={calibration.robot_home_mm[1]:.1f}")
    if result_image_path:
        print(f"  result image: {result_image_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
