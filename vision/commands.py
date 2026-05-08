"""Reusable command helpers for live ZED vision and snapshot workflows."""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from vision.calibration import Calibrator, detection_center
from vision.snapshot_inspection import SnapshotProduceInspector
from vision.vision import ImageRecognition


DEFAULT_CALIBRATION_PATH = "calibration/calibration.json"


def _annotate_board_mm(
    detections: Sequence[Dict[str, Any]],
    calibrator: Optional[Calibrator],
    image_size: tuple[int, int],
) -> None:
    """Add `board_xy_mm` to every detection in-place.

    Field shape: {"x": float|None, "y": float|None, "inside_zone": bool, "error"?: str}
    Coordinates are board-frame mm with origin at the centre of the calibrated
    work area (per the saved calibration).
    """
    if calibrator is None:
        return
    for d in detections:
        center = detection_center(d)
        if center is None:
            d["board_xy_mm"] = {"x": None, "y": None, "inside_zone": False}
            continue
        u, v = center
        try:
            x_mm, y_mm = calibrator.transform_pixel(u, v, image_size=image_size)
        except ValueError:
            d["board_xy_mm"] = {
                "x": None, "y": None, "inside_zone": False,
                "error": "image_size_mismatch",
            }
            continue
        d["board_xy_mm"] = {
            "x": round(float(x_mm), 2),
            "y": round(float(y_mm), 2),
            "inside_zone": bool(calibrator.is_inside_zone(x_mm, y_mm)),
        }


def _fmt_meters(value: Any) -> str:
    try:
        if value is None:
            return "n/a"
        return f"{float(value):.2f}m"
    except (TypeError, ValueError):
        return "n/a"


def run_live_vision(
    duration_seconds: int = 0,
    confidence_threshold: int = 40,
    model: str = "medium",
    algorithm: str = "yolo",
    skip_display: bool = False,
    debug: bool = False,
    print_coordinates: bool = False,
    calibration_required: bool = True,
    calibration_path: str = DEFAULT_CALIBRATION_PATH,
) -> bool:
    """Run live vision loop and optional display.

    When `calibration_required` is True (default), a saved calibration JSON is
    loaded once at startup and each detection is annotated with `board_xy_mm`
    in board-frame millimetres. Pass `calibration_required=False` to run with
    only the existing camera/UV outputs.
    """
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV not installed. Install with: pip install opencv-python")
        return False

    calibrator: Optional[Calibrator] = None
    if calibration_required:
        try:
            calibrator = Calibrator.load(calibration_path)
        except FileNotFoundError:
            print(f"ERROR: calibration file not found at {calibration_path}")
            print("Run `python -m vision.calibration.ui --image PATH ...` first,")
            print("or pass --no-calibration to run live without board-mm coords.")
            return False
        cal = calibrator.calibration
        print(
            f"Loaded calibration: poly{cal.fit.degree}, "
            f"image {cal.image_size[0]}x{cal.image_size[1]}, "
            f"RMS {cal.fit.rms_residual_mm:.2f} mm"
        )

    print("Initializing vision system...")
    vision = ImageRecognition(
        confidence=confidence_threshold,
        model=model,
        algorithm=algorithm,
        auto_start=True,
        debug=debug,
    )

    if not vision._zed_enabled:
        print("ERROR: Could not initialize ZED camera")
        print("Run diagnostics: python -m tests.diagnose_zed")
        return False

    stats: Dict[str, Any] = {
        "total_frames": 0,
        "frames_with_detections": 0,
        "total_detections": 0,
        "last_best_detection": None,
        "fps_samples": deque(maxlen=30),
    }
    start_time = time.time()
    frame_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time
            if duration_seconds > 0 and elapsed > duration_seconds:
                break

            frame_data = vision.get_frame()
            if frame_data is None:
                time.sleep(0.1)
                continue

            stats["total_frames"] += 1
            now = time.time()
            frame_delta = now - frame_time
            if frame_delta > 0:
                stats["fps_samples"].append(1.0 / frame_delta)
            frame_time = now

            rgb_frame = frame_data.get("rgb")
            annotated_frame = frame_data.get("annotated_rgb")
            payload = frame_data.get("payload", {})
            detections = payload.get("detections", [])

            if calibrator is not None and detections:
                ref = rgb_frame if rgb_frame is not None else annotated_frame
                if ref is not None:
                    h_img, w_img = ref.shape[:2]
                    _annotate_board_mm(detections, calibrator, (w_img, h_img))

            if detections:
                stats["frames_with_detections"] += 1
                stats["total_detections"] += len(detections)
                best = max(detections, key=lambda d: d.get("confidence", 0))
                stats["last_best_detection"] = best

                print(
                    f"[Frame {payload.get('frame_index', 0)}] "
                    f"{best.get('label', 'unknown')} "
                    f"({best.get('confidence', 0):.2f}%)"
                )
                # Temporarily muted in live output while keeping coordinate logic active.
                # pos = best.get("position_m", {}) or {}
                # print(
                #     f"  X:{_fmt_meters(pos.get('x'))} "
                #     f"Y:{_fmt_meters(pos.get('y'))} "
                #     f"Z:{_fmt_meters(pos.get('z'))}"
                # )
                if print_coordinates:
                    pos = best.get("position_m", {}) or {}
                    print(
                        f"  X:{_fmt_meters(pos.get('x'))} "
                        f"Y:{_fmt_meters(pos.get('y'))} "
                        f"Z:{_fmt_meters(pos.get('z'))}"
                    )
                    bxy = best.get("board_xy_mm") or {}
                    if bxy.get("x") is not None and bxy.get("y") is not None:
                        zone = "inside" if bxy.get("inside_zone") else "outside"
                        print(
                            f"  board (mm) X:{bxy['x']:+.1f} "
                            f"Y:{bxy['y']:+.1f} ({zone})"
                        )
                    elif "error" in bxy:
                        print(f"  board (mm): {bxy['error']}")

            if not skip_display and (annotated_frame is not None or rgb_frame is not None):
                display_frame = annotated_frame if annotated_frame is not None else rgb_frame
                avg_fps = (
                    sum(stats["fps_samples"]) / len(stats["fps_samples"])
                    if stats["fps_samples"]
                    else 0
                )
                cv2.putText(
                    display_frame,
                    f"FPS: {avg_fps:.1f} | Detections: {len(detections)}",
                    (10, display_frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
                cv2.imshow("Vision Live", display_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        vision.stop()
        if not skip_display:
            cv2.destroyAllWindows()

    print("\nLive run summary")
    print(f"  frames: {stats['total_frames']}")
    print(f"  frames_with_detections: {stats['frames_with_detections']}")
    print(f"  detections: {stats['total_detections']}")
    return True


def capture_and_save_snapshot(
    output_path: str,
    confidence_threshold: int = 40,
    model: str = "medium",
    algorithm: str = "yolo",
    debug: bool = False,
) -> bool:
    """Capture one frame from ZED and save it."""
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV not installed. Install with: pip install opencv-python")
        return False

    vision = ImageRecognition(
        confidence=confidence_threshold,
        model=model,
        algorithm=algorithm,
        auto_start=True,
        debug=debug,
    )
    if not vision._zed_enabled:
        print("ERROR: Could not initialize ZED camera")
        return False

    ok = False
    try:
        frame_data = vision.get_frame()
        if frame_data is None:
            print("ERROR: No frame available from camera")
            return False
        image = frame_data.get("annotated_rgb") or frame_data.get("rgb")
        if image is None:
            print("ERROR: Frame has no image content")
            return False

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        ok = bool(cv2.imwrite(str(output), image))
        if ok:
            print(f"Saved snapshot to: {output}")
        else:
            print(f"ERROR: Failed to write snapshot: {output}")
        return ok
    finally:
        vision.stop()


def inspect_snapshot_images(
    image_paths: Iterable[str],
    confidence: int = 35,
    model: str = "medium",
    json_out: str = "",
) -> int:
    """Run snapshot inspector on one or more images."""
    images = [str(Path(p)) for p in image_paths]
    missing = [p for p in images if not Path(p).is_file()]
    if missing:
        print("ERROR: file not found:", ", ".join(missing))
        return 1

    inspector = SnapshotProduceInspector(confidence=confidence, model=model)
    report = inspector.inspect(images)
    if not report.get("ok"):
        print("ERROR:", report.get("error", "unknown"))
        return 1

    print("Snapshot inspection summary")
    print("  images:", len(images))
    print("  produce detections (items):", report.get("item_count", 0))

    if json_out:
        output = Path(json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Wrote {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vision command entry points")
    sub = parser.add_subparsers(dest="command", required=True)

    live = sub.add_parser("live", help="Run live ZED+YOLO stream")
    live.add_argument("--duration", type=int, default=0)
    live.add_argument("--confidence", type=int, default=40)
    live.add_argument("--model", default="medium")
    live.add_argument("--algorithm", default="yolo", choices=["yolo", "zed"])
    live.add_argument("--no-display", action="store_true")
    live.add_argument("--debug", action="store_true")
    live.add_argument("--print-coordinates", action="store_true")
    live.add_argument(
        "--calibration",
        default=DEFAULT_CALIBRATION_PATH,
        help=f"Path to saved calibration JSON (default {DEFAULT_CALIBRATION_PATH})",
    )
    live.add_argument(
        "--no-calibration",
        action="store_true",
        help="Skip board-mm annotation; run uncalibrated",
    )

    snap = sub.add_parser("snapshot", help="Capture and save one frame")
    snap.add_argument("--output", required=True)
    snap.add_argument("--confidence", type=int, default=40)
    snap.add_argument("--model", default="medium")
    snap.add_argument("--algorithm", default="yolo", choices=["yolo", "zed"])
    snap.add_argument("--debug", action="store_true")

    inspect = sub.add_parser("inspect", help="Run snapshot produce inspection")
    inspect.add_argument("--images", nargs="+", required=True)
    inspect.add_argument("--confidence", type=int, default=35)
    inspect.add_argument("--model", default="medium")
    inspect.add_argument("--json-out", default="")

    args = parser.parse_args()

    if args.command == "live":
        return 0 if run_live_vision(
            duration_seconds=args.duration,
            confidence_threshold=args.confidence,
            model=args.model,
            algorithm=args.algorithm,
            skip_display=args.no_display,
            debug=args.debug,
            print_coordinates=args.print_coordinates,
            calibration_required=not args.no_calibration,
            calibration_path=args.calibration,
        ) else 1
    if args.command == "snapshot":
        return 0 if capture_and_save_snapshot(
            output_path=args.output,
            confidence_threshold=args.confidence,
            model=args.model,
            algorithm=args.algorithm,
            debug=args.debug,
        ) else 1
    return inspect_snapshot_images(
        image_paths=args.images,
        confidence=args.confidence,
        model=args.model,
        json_out=args.json_out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
