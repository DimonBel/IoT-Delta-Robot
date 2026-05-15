"""Interactive click-and-confirm calibration UI.

When the printed master grid does not fully fit in frame, use
    `--partial-master-corners` with `--corner-4pt` or `--manual-wizard` (see CLI).

Modes (pick exactly one):
    --image PATH          load a static photo (e.g. from `python -m vision snapshot --output ...`)
    --live                grab frame(s) from the ZED camera (see --live-preview)

Camera tips:
    - Calibration uses the raw camera image (no YOLO overlay) when available.
    - `--live` grabs quickly after a short warmup; use `--live-preview` to aim,
      then press SPACE or c to freeze the frame used for clicking.
    - Or capture first: `python -m vision snapshot --output outputs/calib_board.jpg`
      then `python -m vision.calibration.ui --image outputs/calib_board.jpg ...`

Workflow:
     1. Master grid: click calibration markers whose (X_mm, Y_mm) are defined in
        the robot's absolute workspace frame (see --master-* bounds, default ±280 mm).
     2. Press 'y' to confirm each click, 'n' to redo, 'q' to quit.
     3. Optional --workflow-v2 / --pick-active-zone: two diagonal clicks define
        active_zone as a filtering rectangle in master-frame mm (never a new origin).
     4. Optional --tool-center-align: click a reference pixel and enter the robot
        TCP X,Y from the controller; offset is saved so runtime coordinates match TCP.
     5. Polynomial fit, work_zone (marker-derived inset), and JSON are saved.
        An annotated result image is also written (disable with --result-image "").

Usage:
    python -m vision.calibration.ui --live --live-preview --workflow-v2 --out calibration/calibration.json
    python -m vision.calibration.ui --live --live-preview --partial-master-corners --corner-4pt --grid 3x3 --out calibration/calibration.json
    python -m vision.calibration.ui --live --partial-master-corners --manual-wizard --workflow-v2 --out calibration/calibration.json
    python -m vision.calibration.ui --image outputs/calib_board.jpg --grid 3x3 --out calibration/calibration.json

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
from typing import Callable, Sequence

from .core import (
    Calibration,
    CalibrationPoint,
    DEFAULT_PICK_HEIGHT_MM,
    HARDWARE_LIMITS,
    ToolCenterOffset,
    WorkZone,
    auto_select_degree,
    compute_tool_center_offset,
    default_master_workspace,
    derive_work_zone,
    fit_polynomial,
    generate_grid_targets,
    infer_missing_grid_corner_from_edge_points,
    robot_bounds_from_pixel_rect,
    robot_bounds_from_quad_clicks,
    save_calibration,
)
from .draw import draw_result_image


@dataclass
class _ClickState:
    last_click: tuple[int, int] | None = None


@dataclass(frozen=True)
class _StageSpec:
    label: str
    count: int


def _cv_read_key(delay_ms: int) -> int:
    """cv2.waitKey / waitKeyEx wrapper (waitKeyEx behaves better on some Windows builds)."""
    import cv2

    wk = getattr(cv2, "waitKeyEx", cv2.waitKey)
    return int(wk(delay_ms))


def _cv_key_confirm(code: int) -> bool:
    if code < 0:
        return False
    k = code & 0xFF
    # Enter / Return; Space as alternate confirm (Windows HighGUI quirk).
    if k in (ord("y"), ord("Y"), 13, 10, ord(" ")):
        return True
    # Some waitKeyEx builds expose extended keys in the high word only.
    hi = (code >> 16) & 0xFF
    return hi in (13, 10)


def _cv_key_redo(code: int) -> bool:
    if code < 0:
        return False
    k = code & 0xFF
    return k in (ord("n"), ord("N"))


def _cv_key_quit(code: int) -> bool:
    if code < 0:
        return False
    k = code & 0xFF
    return k in (ord("q"), ord("Q"), 27)


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


def _bgr_from_zed_frame(frame: dict, *, prefer_clean: bool):
    """Return BGR image from `vision.get_frame()` payload.

    For calibration, prefer raw `rgb` so marker clicks are not biased by overlays."""
    if prefer_clean:
        img = frame.get("rgb")
        if img is None:
            img = frame.get("annotated_rgb")
    else:
        img = frame.get("annotated_rgb")
        if img is None:
            img = frame.get("rgb")
    return img


def _grab_live_frame(
    *,
    preview: bool,
    warmup_frames: int = 5,
    prefer_clean: bool = True,
):
    """Acquire one BGR frame from the ZED pipeline.

    Local import isolates the click UI from the camera module — `--image` mode
    never touches vision.vision.

    Args:
        preview: If True, show a live window until SPACE or ``c`` freezes a frame
            (``q`` aborts). If False, discard ``warmup_frames`` grabs then take one frame.
    """
    import cv2

    # Local import isolates the click UI from the camera module.
    from vision.vision import ImageRecognition

    vision = ImageRecognition(auto_start=True)
    if not vision._zed_enabled:
        vision.stop()
        raise RuntimeError(
            "Could not start ZED camera. Run `python -m tests.diagnose_zed`."
        )

    # ASCII-only title: Unicode here breaks keyboard focus on Windows OpenCV HighGUI.
    window = "Calib camera live (SPACE or C=capture Q=quit)"

    def _warmup_and_grab():
        frame = None
        for _ in range(max(1, warmup_frames)):
            frame = vision.get_frame()
            if frame is not None:
                break
        if frame is None:
            raise RuntimeError("ZED returned no frame.")
        img = _bgr_from_zed_frame(frame, prefer_clean=prefer_clean)
        if img is None:
            raise RuntimeError("ZED frame had no RGB image.")
        return img

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
                display = _bgr_from_zed_frame(frame, prefer_clean=prefer_clean)
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
            "Y or Enter=confirm  N=redo  Q=quit",
            (10, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
        )
    return overlay


def _draw_manual_overlay(
    img,
    stage_label: str,
    point_idx: int,
    point_count: int,
    collected,
    current_click: tuple[int, int] | None,
):
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

    if current_click is not None:
        cv2.drawMarker(overlay, current_click, (0, 0, 255), cv2.MARKER_CROSS, 16, 2)

    cv2.putText(
        overlay,
        f"{stage_label}: point {point_idx}/{point_count}",
        (10, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 220, 220),
        2,
    )
    cv2.putText(
        overlay,
        "Y or Enter=confirm  N=redo  Q=quit",
        (10, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1,
    )
    cv2.putText(
        overlay,
        "After confirm, type the robot X,Y for the clicked point in the terminal.",
        (10, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (220, 220, 120),
        1,
    )
    return overlay


def _parse_robot_xy(text: str) -> tuple[float, float]:
    cleaned = text.strip().replace(",", " ")
    parts = [part for part in cleaned.split() if part]
    if len(parts) != 2:
        raise ValueError("Expected two numbers like '10 20' or '10,20'")
    return float(parts[0]), float(parts[1])


def _prompt_robot_xy(
    stage_label: str,
    input_fn: Callable[[str], str] = input,
) -> tuple[float, float]:
    prompt = (
        f"Enter robot X,Y for {stage_label} "
        f"(example: -120, 80): "
    )
    while True:
        try:
            return _parse_robot_xy(input_fn(prompt))
        except ValueError:
            print("Invalid robot coordinates. Enter two numbers like '-120, 80'.")


def _manual_stage_plan(
    master_points: int = 4,
    slave_points: int = 4,
    robot_point_count: int = 1,
) -> list[_StageSpec]:
    if master_points < 1 or slave_points < 1 or robot_point_count < 1:
        raise ValueError("All manual stage counts must be >= 1")
    return [
        _StageSpec("master grid", master_points),
        _StageSpec("slave grid", slave_points),
        _StageSpec("robot point", robot_point_count),
    ]


def _slave_robot_stages(
    slave_points: int = 4,
    robot_point_count: int = 1,
) -> list[_StageSpec]:
    """Slave grid + TCP reference after partial master (corner-4pt or manual wizard)."""
    if slave_points < 1 or robot_point_count < 1:
        raise ValueError("Slave / robot stage counts must be >= 1")
    return [
        _StageSpec("Slave grid (step 2)", slave_points),
        _StageSpec("Robot TCP reference (step 3)", robot_point_count),
    ]


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
        key = _cv_read_key(30)

        if _cv_key_quit(key):
            cv2.destroyWindow(window)
            raise KeyboardInterrupt("Calibration aborted by user")
        if _cv_key_redo(key):
            state.last_click = None
            continue
        if _cv_key_confirm(key) and state.last_click is not None:
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


def collect_partial_master_grid_points(
    img,
    rows: int,
    cols: int,
    targets: list[tuple[float, float]],
) -> list[CalibrationPoint]:
    """Three visible robot corners + two edge samples infer BR (+x,+y); expand full grid.

    Click order / robot labels (axis-aligned grid in robot mm):
      1) TL (-x,-y), 2) BL (-x,+y), 3) TR (+x,-y),
      4) Any pixel along visible TR→BR edge (+x side),
      5) Any pixel along visible BL→BR edge (+y side).

    Steps 4–5 define infinite lines whose intersection is the missing BR marker."""
    import cv2

    if rows < 2 or cols < 2:
        raise ValueError("Partial master grid needs rows>=2 and cols>=2.")

    tl_mm = targets[0]
    tr_mm = targets[cols - 1]
    bl_mm = targets[(rows - 1) * cols]
    br_mm = targets[rows * cols - 1]

    banners = (
        (
            "1/5 Master TL robot (-x,-y) — click this corner marker",
            f"Expected mm X={tl_mm[0]:.0f} Y={tl_mm[1]:.0f}",
        ),
        (
            "2/5 Master BL robot (-x,+y) — click this corner marker",
            f"Expected mm X={bl_mm[0]:.0f} Y={bl_mm[1]:.0f}",
        ),
        (
            "3/5 Master TR robot (+x,-y) — click this corner marker",
            f"Expected mm X={tr_mm[0]:.0f} Y={tr_mm[1]:.0f}",
        ),
        (
            "4/5 Edge (+x,-y) to (+x,+y) — click ANY visible point on this edge",
            "(toward missing BR; must not coincide with TR)",
        ),
        (
            "5/5 Edge (-x,+y) to (+x,+y) — click ANY visible point on this edge",
            "(toward missing BR)",
        ),
    )

    print(
        "\n[Calib] Click the calibration IMAGE WINDOW so it has keyboard focus.\n"
        "    Left-click a point, then press Y or Enter to confirm (N redo, Q quit).\n",
        flush=True,
    )

    state = _ClickState()
    # ASCII-only: non-ASCII window titles break HighGUI key events on Windows.
    window = "Calib partial master"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.last_click = (x, y)

    cv2.setMouseCallback(window, on_mouse)

    clicks_uv: list[tuple[float, float]] = []
    step = 0

    try:
        while step < len(banners):
            overlay = img.copy()
            for i, (u, v) in enumerate(clicks_uv):
                cv2.circle(overlay, (int(u), int(v)), 6, (0, 220, 0), -1)
                cv2.putText(
                    overlay,
                    str(i + 1),
                    (int(u) + 8, int(v) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 220, 0),
                    1,
                )
            if state.last_click is not None:
                cv2.drawMarker(
                    overlay,
                    state.last_click,
                    (0, 0, 255),
                    cv2.MARKER_CROSS,
                    16,
                    2,
                )
            title, sub = banners[step]
            cv2.putText(
                overlay,
                title,
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (0, 220, 220),
                2,
            )
            cv2.putText(
                overlay,
                sub,
                (10, 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (200, 220, 160),
                1,
            )
            cv2.putText(
                overlay,
                "Focus THIS window | Y or Enter=confirm  N=redo  Q=quit",
                (10, 76),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (200, 200, 200),
                1,
            )
            cv2.putText(
                overlay,
                "(If keys do nothing, click this image once then try again)",
                (10, 96),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (180, 180, 255),
                1,
            )
            cv2.imshow(window, overlay)
            key = _cv_read_key(30)

            if _cv_key_quit(key):
                raise KeyboardInterrupt("Calibration aborted by user")
            if _cv_key_redo(key):
                state.last_click = None
                continue
            if _cv_key_confirm(key) and state.last_click is not None:
                u, v = float(state.last_click[0]), float(state.last_click[1])
                clicks_uv.append((u, v))
                state.last_click = None
                step += 1
    finally:
        cv2.destroyWindow(window)

    tl_uv, bl_uv, tr_uv, aux_r_uv, aux_t_uv = clicks_uv
    br_u, br_v = infer_missing_grid_corner_from_edge_points(
        tr_uv, bl_uv, aux_r_uv, aux_t_uv,
    )

    corner_pts = [
        CalibrationPoint(u=tl_uv[0], v=tl_uv[1], x_mm=tl_mm[0], y_mm=tl_mm[1]),
        CalibrationPoint(u=tr_uv[0], v=tr_uv[1], x_mm=tr_mm[0], y_mm=tr_mm[1]),
        CalibrationPoint(u=bl_uv[0], v=bl_uv[1], x_mm=bl_mm[0], y_mm=bl_mm[1]),
        CalibrationPoint(u=float(br_u), v=float(br_v), x_mm=br_mm[0], y_mm=br_mm[1]),
    ]
    return _expand_from_corner_clicks(rows, cols, targets, corner_pts)


def collect_axis_aligned_pixel_rect(
    img,
    *,
    window_title: str,
    banner: str,
) -> tuple[float, float, float, float]:
    """Two diagonal clicks define u_min,v_min,u_max,v_max; confirmed with 'y'."""
    import cv2

    state: dict[str, list[tuple[int, int]]] = {"corners": []}
    window = window_title
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(state["corners"]) >= 2:
                state["corners"].clear()
            state["corners"].append((int(x), int(y)))

    cv2.setMouseCallback(window, on_mouse)

    try:
        while True:
            overlay = img.copy()
            for i, (cx, cy) in enumerate(state["corners"]):
                cv2.circle(overlay, (cx, cy), 8, (0, 255, 0), -1)
                cv2.putText(
                    overlay,
                    str(i + 1),
                    (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
            if len(state["corners"]) == 2:
                (x0, y0), (x1, y1) = state["corners"]
                cv2.rectangle(overlay, (x0, y0), (x1, y1), (255, 200, 0), 2)
            cv2.putText(
                overlay,
                banner,
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (220, 220, 100),
                2,
            )
            cv2.putText(
                overlay,
                "Two diagonal clicks  |  Y or Enter=confirm  N=reset  Q=quit",
                (10, 54),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (200, 200, 200),
                1,
            )
            cv2.imshow(window, overlay)
            key = _cv_read_key(30)
            if _cv_key_quit(key):
                raise KeyboardInterrupt("Rectangle selection aborted")
            if _cv_key_redo(key):
                state["corners"].clear()
                continue
            if _cv_key_confirm(key) and len(state["corners"]) == 2:
                (xa, ya), (xb, yb) = state["corners"]
                return (
                    float(min(xa, xb)),
                    float(min(ya, yb)),
                    float(max(xa, xb)),
                    float(max(ya, yb)),
                )
    finally:
        cv2.destroyWindow(window)


def collect_quad_zone_clicks(
    img,
    *,
    window_title: str,
    banner: str,
) -> list[tuple[float, float]]:
    """Click 4 zone corners; live preview draws two crossing diagonals.

    Click order: any 4 corners going clockwise (or counter-clockwise) around
    the zone perimeter. Diagonal lines are drawn between corners 0↔2 and 1↔3
    so the selection looks identical to the master grid overlay in the result image.

    Controls:
      Left-click   -- place next corner (clicking a 5th time restarts from corner 1)
      N            -- undo the last corner
      Y / Enter    -- confirm (only active once all 4 corners are placed)
      Q / Escape   -- abort

    Returns a list of 4 (u, v) float pixel coordinates.
    """
    import cv2

    state: dict = {"corners": []}
    window = window_title

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(state["corners"]) >= 4:
                state["corners"].clear()
            state["corners"].append((int(x), int(y)))

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_mouse)

    try:
        while True:
            corners = list(state["corners"])
            n = len(corners)
            overlay = img.copy()

            # Polygon edge outline (partial while clicking, closed when 4 corners)
            if n >= 2:
                for i in range(n - 1):
                    cv2.line(overlay, corners[i], corners[i + 1], (0, 200, 0), 2)
            if n == 4:
                cv2.line(overlay, corners[3], corners[0], (0, 200, 0), 2)

            # Diagonal lines: 0↔2 appears as soon as corner 3 is placed; 1↔3 when all 4 set
            if n >= 3:
                cv2.line(overlay, corners[0], corners[2], (0, 180, 255), 2)
            if n == 4:
                cv2.line(overlay, corners[1], corners[3], (0, 180, 255), 2)

            # Corner markers + numbering
            for i, (cx, cy) in enumerate(corners):
                cv2.circle(overlay, (cx, cy), 8, (0, 255, 0), -1)
                cv2.putText(overlay, str(i + 1), (cx + 10, cy - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # HUD
            cv2.putText(overlay, banner, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 100), 2)
            if n < 4:
                cv2.putText(overlay,
                            f"Click corner {n + 1}/4  |  N=undo  Q=quit",
                            (10, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1)
            else:
                cv2.putText(overlay,
                            "4 corners set  |  Y or Enter=confirm  N=undo last  Q=quit",
                            (10, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100, 255, 100), 1)

            cv2.imshow(window, overlay)
            key = _cv_read_key(30)

            if _cv_key_quit(key):
                raise KeyboardInterrupt("Zone selection aborted")
            if _cv_key_redo(key) and n > 0:
                state["corners"].pop()
                continue
            if _cv_key_confirm(key) and n == 4:
                break
    finally:
        cv2.destroyWindow(window)

    return [(float(c[0]), float(c[1])) for c in state["corners"]]


def collect_tool_center_alignment_click(
    img,
    calibration: Calibration,
    input_fn: Callable[[str], str] = input,
) -> ToolCenterOffset:
    """Click reference pixel, then type robot TCP X,Y for `compute_tool_center_offset`."""
    import cv2

    state: dict[str, tuple[int, int] | None] = {"click": None}
    window = "Calib tool center"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["click"] = (int(x), int(y))

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_mouse)

    try:
        while True:
            overlay = img.copy()
            if state["click"] is not None:
                cv2.drawMarker(
                    overlay,
                    state["click"],
                    (0, 0, 255),
                    cv2.MARKER_CROSS,
                    16,
                    2,
                )
            cv2.putText(
                overlay,
                "Click reference point on image | Y or Enter=confirm | N=clear | Q=abort",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (0, 220, 220),
                2,
            )
            cv2.imshow(window, overlay)
            key = _cv_read_key(30)
            if _cv_key_quit(key):
                raise KeyboardInterrupt("Tool-centre alignment aborted")
            if _cv_key_redo(key):
                state["click"] = None
                continue
            if _cv_key_confirm(key) and state["click"] is not None:
                break
    finally:
        cv2.destroyWindow(window)

    cx, cy = state["click"]
    print()
    print(
        "Enter robot TCP X,Y (mm) from the controller with the tool on that pixel."
    )
    print(
        "Example reference home pose for this delta rig: X=-4.67 Y=-5.81 mm "
        "(always verify on your controller display)."
    )
    rx, ry = _prompt_robot_xy("tool-centre reference", input_fn=input_fn)
    return compute_tool_center_offset(calibration, float(cx), float(cy), rx, ry)


def collect_manual_clicks_for_stages(
    img,
    stages: Sequence[_StageSpec],
    input_fn: Callable[[str], str] = input,
) -> list[CalibrationPoint]:
    """Collect clicked points and ask the user to type robot XY for each one."""
    import cv2

    state = _ClickState()
    # ASCII-only; must close this window before stdin prompts on Windows (OpenCV+console deadlock/crash).
    window = "Calib manual marks"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.last_click = (x, y)

    def attach_gui() -> None:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window, on_mouse)

    def detach_gui() -> None:
        try:
            cv2.destroyWindow(window)
        except cv2.error:
            pass
        cv2.waitKey(1)

    collected: list[CalibrationPoint] = []
    attach_gui()
    try:
        for stage in stages:
            for stage_idx in range(stage.count):
                while True:
                    overlay = _draw_manual_overlay(
                        img,
                        stage.label,
                        stage_idx + 1,
                        stage.count,
                        collected,
                        state.last_click,
                    )
                    cv2.imshow(window, overlay)
                    key = _cv_read_key(30)

                    if _cv_key_quit(key):
                        raise KeyboardInterrupt("Calibration aborted by user")
                    if _cv_key_redo(key):
                        state.last_click = None
                        continue
                    if _cv_key_confirm(key) and state.last_click is not None:
                        detach_gui()
                        try:
                            print(
                                "\n(Type robot coordinates in this terminal; "
                                "the image window will reopen next.)",
                                flush=True,
                            )
                            x_mm, y_mm = _prompt_robot_xy(
                                f"{stage.label} point {stage_idx + 1}/{stage.count}",
                                input_fn=input_fn,
                            )
                        finally:
                            attach_gui()
                        collected.append(
                            CalibrationPoint(
                                u=float(state.last_click[0]),
                                v=float(state.last_click[1]),
                                x_mm=float(x_mm),
                                y_mm=float(y_mm),
                            )
                        )
                        state.last_click = None
                        break
    finally:
        detach_gui()

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


def build_calibration_from_collect(
    image,
    points: list[CalibrationPoint],
    pick_height_z_mm: float,
    notes: str,
    degree: int | None = None,
    master_workspace: WorkZone | None = None,
    active_zone: WorkZone | None = None,
    tool_center_offset: ToolCenterOffset | None = None,
) -> Calibration:
    """Fit polynomial + derive marker work_zone; master grid bounds come from `master_workspace`."""
    if not points:
        raise RuntimeError("No calibration points collected.")

    chosen_degree = degree if degree is not None else auto_select_degree(len(points))
    fit = fit_polynomial(points, degree=chosen_degree)
    zone = derive_work_zone(points)
    mw = master_workspace if master_workspace is not None else default_master_workspace()
    h, w = image.shape[:2]
    return Calibration(
        image_size=(int(w), int(h)),
        fit=fit,
        points=points,
        work_zone=zone,
        master_workspace=mw,
        active_zone=active_zone,
        tool_center_offset=(
            tool_center_offset if tool_center_offset is not None else ToolCenterOffset()
        ),
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


def _wizard_step_banner(step: int, total: int, title: str, description: str = "") -> None:
    sep = "=" * 60
    print(f"\n{sep}", flush=True)
    print(f"  STEP {step}/{total}: {title}", flush=True)
    print(sep, flush=True)
    for line in (description.split("\n") if description else []):
        print(f"  {line}", flush=True)
    print(flush=True)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Interactive camera calibration tool")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="Path to a static photo (e.g. camera snapshot saved as JPG)")
    src.add_argument(
        "--live",
        action="store_true",
        help="Use ZED: grab frame(s) after warmup, or use --live-preview to choose a moment",
    )

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
    p.add_argument(
        "--master-x-min",
        type=float,
        default=float(HARDWARE_LIMITS["x_min"]),
        help="Master workspace X_min (mm); absolute robot frame (default: hardware limit).",
    )
    p.add_argument(
        "--master-x-max",
        type=float,
        default=float(HARDWARE_LIMITS["x_max"]),
        help="Master workspace X_max (mm).",
    )
    p.add_argument(
        "--master-y-min",
        type=float,
        default=float(HARDWARE_LIMITS["y_min"]),
        help="Master workspace Y_min (mm).",
    )
    p.add_argument(
        "--master-y-max",
        type=float,
        default=float(HARDWARE_LIMITS["y_max"]),
        help="Master workspace Y_max (mm).",
    )
    p.add_argument(
        "--pick-active-zone",
        action="store_true",
        help=(
            "After marker calibration, click two diagonal corners to define active_zone "
            "(pick filtering only; coordinates stay in master mm)."
        ),
    )
    p.add_argument(
        "--tool-center-align",
        action="store_true",
        help=(
            "After marker calibration, click a reference pixel and enter robot TCP X,Y "
            "to save additive tool-centre offset."
        ),
    )
    p.add_argument(
        "--workflow-v2",
        action="store_true",
        help="Run --pick-active-zone then --tool-center-align after grid calibration.",
    )
    p.add_argument("--notes", default="", help="Free-text notes saved into the JSON")
    p.add_argument(
        "--live-preview",
        action="store_true",
        help=(
            "With --live: show the camera stream until SPACE or c captures the "
            "calibration frame (q aborts)."
        ),
    )
    p.add_argument(
        "--live-warmup-frames",
        type=int,
        default=5,
        metavar="N",
        help="With --live (no preview): discard N grabs before taking the frame (default 5)",
    )
    p.add_argument(
        "--save-camera-frame",
        metavar="PATH",
        default="",
        help=(
            "With --live: save the captured BGR frame to this path before clicking "
            "(same pixels used for calibration)."
        ),
    )
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
    p.add_argument(
        "--partial-master-corners",
        action="store_true",
        help=(
            "Master plate (+x,+y) corner is off-screen: click TL (-x,-y), BL (-x,+y), "
            "TR (+x,-y), then two auxiliary pixels on the TR→BR and BL→BR edges; BR "
            "is inferred by line intersection. With --corner-4pt, slave grid + TCP "
            "reference clicks follow unless --skip-slave-after-partial. "
            "Use with --manual-wizard to skip --corner-4pt (same slave stages)."
        ),
    )
    p.add_argument(
        "--skip-slave-after-partial",
        action="store_true",
        help=(
            "With --partial-master-corners --corner-4pt only: fit using the expanded "
            "master grid only (no slave grid or TCP reference clicks)."
        ),
    )
    p.add_argument(
        "--manual-wizard",
        action="store_true",
        help=(
            "Use the manual staged workflow: 4 master-grid points, 4 slave-grid "
            "points, then 1 robot reference point with typed robot coordinates."
        ),
    )
    p.add_argument(
        "--manual-master-points",
        type=int,
        default=4,
        help="Number of master-grid points in manual-wizard mode (default: 4)",
    )
    p.add_argument(
        "--manual-slave-points",
        type=int,
        default=4,
        help="Number of slave-grid points in manual-wizard mode (default: 4)",
    )
    p.add_argument(
        "--manual-robot-point",
        type=int,
        default=1,
        help="Number of robot reference points in manual-wizard mode (default: 1)",
    )
    p.add_argument(
        "--wizard",
        action="store_true",
        help=(
            "Run the recommended 3-step calibration wizard:\n"
            "  Step 1 -- Master grid: click 3 visible corners + 2 edge helpers\n"
            "            (4th corner inferred; inner grid expanded by interpolation)\n"
            "  Step 2 -- Active zone (slave area): draw pick rectangle\n"
            "            (filter only; coordinates stay in master robot frame)\n"
            "  Step 3 -- TCP/tool-centre reference: click reference point,\n"
            "            type robot TCP X,Y mm from controller.\n"
            "Requires --grid >=2x2 (default 3x3). "
            "Incompatible with --manual-wizard, --corner-4pt, --partial-master-corners."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    rows, cols = args.grid

    manual_wizard = bool(args.manual_wizard)
    partial_master = bool(args.partial_master_corners)

    manual_stage_plan = (
        _manual_stage_plan(
            master_points=args.manual_master_points,
            slave_points=args.manual_slave_points,
            robot_point_count=args.manual_robot_point,
        )
        if (manual_wizard and not partial_master)
        else None
    )

    slave_only_stages = (
        _slave_robot_stages(
            slave_points=args.manual_slave_points,
            robot_point_count=args.manual_robot_point,
        )
        if (manual_wizard and partial_master)
        else None
    )

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
        if args.live_preview and not args.live:
            print("ERROR: --live-preview requires --live", file=sys.stderr)
            return 2
        if int(args.live_warmup_frames) < 1:
            print("ERROR: --live-warmup-frames must be >= 1", file=sys.stderr)
            return 2
        try:
            image = _grab_live_frame(
                preview=bool(args.live_preview),
                warmup_frames=int(args.live_warmup_frames),
            )
        except KeyboardInterrupt:
            print("Calibration aborted.", file=sys.stderr)
            return 1

        save_cam = (args.save_camera_frame or "").strip()
        if save_cam:
            import cv2

            parent = os.path.dirname(os.path.abspath(save_cam))
            if parent:
                os.makedirs(parent, exist_ok=True)
            if not cv2.imwrite(save_cam, image):
                print(
                    f"ERROR: failed to write --save-camera-frame {save_cam}",
                    file=sys.stderr,
                )
                return 2
            print(f"Saved camera frame to {save_cam}")

    use_4pt = bool(args.corner_4pt)
    if manual_wizard and use_4pt:
        print("ERROR: --manual-wizard and --corner-4pt are mutually exclusive.", file=sys.stderr)
        return 2
    if partial_master and not (manual_wizard or use_4pt):
        print(
            "ERROR: --partial-master-corners requires --corner-4pt or --manual-wizard.",
            file=sys.stderr,
        )
        return 2
    if partial_master and (rows < 2 or cols < 2):
        print(
            "ERROR: --partial-master-corners needs a grid of at least 2x2.",
            file=sys.stderr,
        )
        return 2
    if args.skip_slave_after_partial and not (partial_master and use_4pt):
        print(
            "ERROR: --skip-slave-after-partial only applies with "
            "--partial-master-corners and --corner-4pt.",
            file=sys.stderr,
        )
        return 2
    if use_4pt and (rows < 2 or cols < 2):
        print("ERROR: --corner-4pt requires a grid of at least 2x2.", file=sys.stderr)
        return 2

    print(f"Calibrating against {rows}x{cols} grid ({len(targets)} markers).")
    master_workspace = WorkZone(
        x_min=float(args.master_x_min),
        x_max=float(args.master_x_max),
        y_min=float(args.master_y_min),
        y_max=float(args.master_y_max),
    )
    if (
        master_workspace.x_min >= master_workspace.x_max
        or master_workspace.y_min >= master_workspace.y_max
    ):
        print("ERROR: master workspace bounds are invalid (min >= max).", file=sys.stderr)
        return 2

    wf_v2 = bool(args.workflow_v2)
    pick_az = bool(args.pick_active_zone) or wf_v2
    tool_align = bool(args.tool_center_align) or wf_v2

    if args.result_image is None:
        out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
        result_image_path: str | None = os.path.join(out_dir, "calibration_result.png")
    elif args.result_image == "":
        result_image_path = None
    else:
        result_image_path = args.result_image

    # ── 3-step wizard ─────────────────────────────────────────────────────────
    if args.wizard:
        if manual_wizard or use_4pt or partial_master:
            print(
                "ERROR: --wizard cannot be combined with --manual-wizard, "
                "--corner-4pt, or --partial-master-corners.",
                file=sys.stderr,
            )
            return 2
        if rows < 2 or cols < 2:
            print("ERROR: --wizard requires --grid of at least 2x2.", file=sys.stderr)
            return 2
        try:
            _wizard_step_banner(
                1, 3, "Master Grid Calibration",
                f"Grid: {rows}x{cols}  Spacing: {args.spacing:.0f} mm\n"
                "The camera sees only 3 of 4 grid corners — the 4th is inferred.\n"
                "Click 5 points in the image window:\n"
                "  1/5  Top-Left corner      (robot -X, -Y)\n"
                "  2/5  Bottom-Left corner   (robot -X, +Y)\n"
                "  3/5  Top-Right corner     (robot +X, -Y)\n"
                "  4/5  Any visible point on the TR->BR edge  (right edge, toward +Y)\n"
                "  5/5  Any visible point on the BL->BR edge  (bottom edge, toward +X)\n"
                "Bottom-Right corner (+X, +Y) will be inferred by line intersection.",
            )
            points = collect_partial_master_grid_points(image, rows, cols, targets)
            calibration = build_calibration_from_collect(
                image=image,
                points=points,
                pick_height_z_mm=args.pick_height_z,
                notes=args.notes,
                degree=args.degree,
                master_workspace=master_workspace,
            )
            print(
                f"  Master fit: poly{calibration.fit.degree}  "
                f"RMS {calibration.fit.rms_residual_mm:.2f} mm",
                flush=True,
            )

            _wizard_step_banner(
                2, 3, "Active Work Zone  (Slave Area)",
                "Click 4 corners of the slave/pick area (any clockwise order).\n"
                "  Two crossing diagonals will appear live as you click.\n"
                "  Press Y or Enter to confirm once all 4 corners are placed.\n"
                "  IMPORTANT: This zone is a FILTER ONLY.\n"
                "  Object coordinates always stay in the master robot frame.\n"
                "  The zone does NOT create a new origin or re-scale coordinates.",
            )
            quad_corners = collect_quad_zone_clicks(
                image,
                window_title="STEP 2/3: Active Zone",
                banner="STEP 2/3: Slave area -- click 4 corners, Y=confirm",
            )
            az = robot_bounds_from_quad_clicks(calibration, quad_corners)
            az = az.clipped_to(calibration.master_workspace)
            if az.x_min >= az.x_max or az.y_min >= az.y_max:
                raise ValueError(
                    "Active zone is empty after clipping to master workspace. "
                    "Draw a larger rectangle or re-check the master grid."
                )
            calibration.active_zone = az
            print(
                f"  Active zone (mm): X[{az.x_min:.0f}, {az.x_max:.0f}]  "
                f"Y[{az.y_min:.0f}, {az.y_max:.0f}]",
                flush=True,
            )

            _wizard_step_banner(
                3, 3, "Tool / TCP Centre Alignment",
                "Move the robot gripper to a known reference point visible in the image.\n"
                "  Robot Home: X=-4.67, Y=-5.81 mm  (verify on controller display)\n"
                "  1. Click the gripper tip location in the image window.\n"
                "  2. In this terminal, type the actual robot TCP X, Y mm.",
            )
            calibration.tool_center_offset = collect_tool_center_alignment_click(
                image, calibration,
            )
            off = calibration.tool_center_offset
            print(
                f"  Tool-centre offset: X{off.x_mm:+.2f} mm  Y{off.y_mm:+.2f} mm",
                flush=True,
            )

            write_calibration_artifacts(calibration, image, args.out, result_image_path)
        except KeyboardInterrupt:
            print("\nCalibration wizard aborted.", file=sys.stderr)
            return 1
        except (ValueError, RuntimeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        mw = calibration.master_workspace
        az2 = calibration.effective_active_zone()
        off2 = calibration.tool_center_offset
        print(f"\nSaved calibration to {args.out}")
        print(
            f"  fit             : poly{calibration.fit.degree}  "
            f"RMS {calibration.fit.rms_residual_mm:.2f} mm"
        )
        print(
            f"  master workspace: X[{mw.x_min:.0f}, {mw.x_max:.0f}]  "
            f"Y[{mw.y_min:.0f}, {mw.y_max:.0f}] mm"
        )
        print(
            f"  active zone     : X[{az2.x_min:.0f}, {az2.x_max:.0f}]  "
            f"Y[{az2.y_min:.0f}, {az2.y_max:.0f}] mm"
        )
        print(f"  tool offset     : X{off2.x_mm:+.2f}  Y{off2.y_mm:+.2f} mm")
        if result_image_path:
            print(f"  result image    : {result_image_path}")
        return 0

    points: list[CalibrationPoint]
    if manual_wizard:
        if partial_master:
            print(
                "Partial master grid: click TL (-x,-y), BL (-x,+y), TR (+x,-y), "
                "then two edge points toward missing (+x,+y); BR is inferred."
            )
            print(
                "Step 2–3: slave grid + robot TCP reference — after each click confirm "
                "(Y/Enter), then type robot X,Y in the terminal.",
                flush=True,
            )
            master_pts = collect_partial_master_grid_points(image, rows, cols, targets)
            points = master_pts + collect_manual_clicks_for_stages(
                image,
                slave_only_stages,
            )
        else:
            print("Manual wizard mode: master grid -> slave grid -> robot point.")
            print("After each confirmed click, type the robot coordinates for that point.")
            points = collect_manual_clicks_for_stages(
                image,
                manual_stage_plan,
            )
    elif use_4pt:
        if partial_master:
            print(
                "Step 1 — Partial master / 4pt-expand: TL -> BL -> TR -> edge (+x) -> edge (+y); "
                "infer BR then interpolate inner master markers.",
                flush=True,
            )
            master_pts = collect_partial_master_grid_points(image, rows, cols, targets)
            if args.skip_slave_after_partial:
                points = master_pts
            else:
                print(
                    "\nStep 2 — Slave grid: "
                    f"{args.manual_slave_points} separate marker click(s) on the slave plate.",
                    flush=True,
                )
                print(
                    "After each click press Y or Enter, then type that marker's robot X,Y mm "
                    "in this terminal.",
                    flush=True,
                )
                print(
                    f"Step 3 — Robot TCP reference: {args.manual_robot_point} click(s), "
                    "same confirm + type coordinates.",
                    flush=True,
                )
                slave_pts = collect_manual_clicks_for_stages(
                    image,
                    _slave_robot_stages(
                        slave_points=args.manual_slave_points,
                        robot_point_count=args.manual_robot_point,
                    ),
                )
                points = master_pts + slave_pts
        else:
            print("4-point mode: click corners in this order:")
            print("  1) top-left  2) top-right  3) bottom-left  4) bottom-right")
            corner_idx = _corner_target_indices(rows, cols)
            click_targets = [targets[i] for i in corner_idx]
            clicked = collect_clicks_for_targets(image, click_targets)
            if len(clicked) != 4:
                print("ERROR: expected 4 corner clicks.", file=sys.stderr)
                return 1
            points = _expand_from_corner_clicks(rows, cols, targets, clicked)
    else:
        print("Click each marker in row-major order (top-left first).")
        points = collect_clicks_for_targets(image, targets)
    try:
        calibration = build_calibration_from_collect(
            image=image,
            points=points,
            pick_height_z_mm=args.pick_height_z,
            notes=args.notes,
            degree=args.degree,
            master_workspace=master_workspace,
        )

        if pick_az:
            rect = collect_axis_aligned_pixel_rect(
                image,
                window_title="Active zone",
                banner="Pick-area rectangle (maps to master-frame mm)",
            )
            u1, v1, u2, v2 = rect
            az = robot_bounds_from_pixel_rect(calibration, u1, v1, u2, v2)
            az = az.clipped_to(calibration.master_workspace)
            if az.x_min >= az.x_max or az.y_min >= az.y_max:
                raise ValueError(
                    "Active zone is empty after clipping to master_workspace."
                )
            calibration.active_zone = az

        if tool_align:
            calibration.tool_center_offset = collect_tool_center_alignment_click(
                image,
                calibration,
            )

        write_calibration_artifacts(calibration, image, args.out, result_image_path)
    except KeyboardInterrupt:
        print("Calibration aborted.", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Saved calibration to {args.out}")
    print(f"  fit: poly{calibration.fit.degree}, "
          f"RMS residual: {calibration.fit.rms_residual_mm:.2f} mm")
    mw = calibration.master_workspace
    print(
        f"  master workspace (mm): X[{mw.x_min:.0f}, {mw.x_max:.0f}] "
        f"Y[{mw.y_min:.0f}, {mw.y_max:.0f}]"
    )
    wz = calibration.work_zone
    print(
        f"  marker work zone (mm): X[{wz.x_min:.0f}, {wz.x_max:.0f}] "
        f"Y[{wz.y_min:.0f}, {wz.y_max:.0f}]"
    )
    az = calibration.effective_active_zone()
    print(
        f"  effective active zone (mm): X[{az.x_min:.0f}, {az.x_max:.0f}] "
        f"Y[{az.y_min:.0f}, {az.y_max:.0f}]"
    )
    off = calibration.tool_center_offset
    print(f"  tool-centre offset (mm): X{off.x_mm:+.2f}  Y{off.y_mm:+.2f}")
    if result_image_path:
        print(f"  result image: {result_image_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
