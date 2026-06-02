"""Reusable command helpers for live ZED vision and snapshot workflows."""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from vision.calibration import Calibrator, HomographyFit, detection_center, refined_detection_center
from vision.quality import grade_detection
from vision.snapshot_inspection import SnapshotProduceInspector
from vision.tracker import FruitTracker
from vision.vision import ImageRecognition


DEFAULT_CALIBRATION_PATH = "calibration/calibration.json"
DEFAULT_TRACKER_SNAPSHOT = "outputs/latest_tracks.json"
DEFAULT_TRACKER_EVENTS = "outputs/track_events.jsonl"


def _expand_image_inputs(image_paths: Iterable[str]) -> list[str]:
    """Expand wildcard image arguments in a cross-shell way."""
    expanded: list[str] = []
    for p in image_paths:
        matches = glob.glob(p)
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(p)
    # Deduplicate while preserving order.
    seen = set()
    ordered: list[str] = []
    for p in expanded:
        if p in seen:
            continue
        seen.add(p)
        ordered.append(p)
    return ordered


def _annotate_board_mm(
    detections: Sequence[Dict[str, Any]],
    calibrator: Optional[Calibrator],
    image_size: tuple[int, int],
    rgb_frame=None,
) -> None:
    """Add `board_xy_mm` to every detection in-place.

    Field shape: {"x": float|None, "y": float|None, "inside_zone": bool, "error"?: str}
    Coordinates are robot-frame mm produced by the saved polynomial fit;
    `inside_zone` is True when the point sits inside the saved work zone.

    When `rgb_frame` is provided, the per-detection (u, v) is refined via
    `refined_detection_center` (sphere-aware silhouette fit). Otherwise it
    falls back to the bbox arithmetic-mean centre.
    """
    if calibrator is None:
        return
    for d in detections:
        if rgb_frame is not None:
            center = refined_detection_center(d, rgb_frame)
        else:
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


def _annotate_quality(
    detections: Sequence[Dict[str, Any]],
    rgb_frame,
) -> None:
    """Add `quality` to every produce detection in-place via fuzzy grading.

    Reuses vision.quality.grade_detection. Catches the data-shape errors a
    bad frame can produce (bbox/crop/HSV) so the live loop never crashes,
    while letting real defects (NameError, AttributeError, ImportError)
    bubble up so they don't hide silently.
    """
    if rgb_frame is None:
        return
    for d in detections:
        if d.get("detection_type") != "produce":
            continue
        try:
            grade_detection(d, rgb_frame)
        except (ValueError, TypeError, IndexError) as exc:
            d["quality"] = {
                "grade": "unknown",
                "error": "grade_failed",
                "error_kind": type(exc).__name__,
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
    confidence_threshold: int = 15,
    model: str = "medium",
    algorithm: str = "yolo",
    skip_display: bool = False,
    debug: bool = False,
    print_coordinates: bool = False,
    calibration_required: bool = True,
    calibration_path: str = DEFAULT_CALIBRATION_PATH,
    imgsz: int = 1280,
    enhance_low_light: bool = False,
    quality_enabled: bool = True,
    person_min_confidence: int = 40,
    tracking_enabled: bool = True,
    tracker_output: str = DEFAULT_TRACKER_SNAPSHOT,
    tracker_events: str = DEFAULT_TRACKER_EVENTS,
    tracker_snapshot_every: int = 10,
    tracker_radius_mm: float = FruitTracker.DEFAULT_MATCH_RADIUS_MM,
    tracker_max_age_frames: int = FruitTracker.DEFAULT_MAX_AGE_FRAMES,
) -> bool:
    """Run live vision loop and optional display.

    Defaults are tuned aggressively for "see small fruit at distance":
      - confidence_threshold=15 (people are gated separately at person_min_confidence)
      - imgsz=1280 for sharper small-object recall (was 832 / 640 / 416 in earlier iterations)
      - enhance_low_light=False (opt in via the --enhance CLI flag)
      - quality_enabled=True attaches a fuzzy quality grade to produce detections

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
            f"Loaded calibration: {'homography' if isinstance(cal.fit, HomographyFit) else 'poly' + str(cal.fit.degree)}, "
            f"image {cal.image_size[0]}x{cal.image_size[1]}, "
            f"RMS {cal.fit.rms_residual_mm:.2f} mm"
        )

    tracker: Optional[FruitTracker] = None
    tracker_snapshot_path: Optional[Path] = None
    tracker_events_path: Optional[Path] = None
    if tracking_enabled:
        tracker = FruitTracker(
            match_radius_mm=tracker_radius_mm,
            max_age_frames=tracker_max_age_frames,
        )
        if tracker_output:
            tracker_snapshot_path = Path(tracker_output)
            tracker_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if tracker_events:
            tracker_events_path = Path(tracker_events)
            tracker_events_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"Initializing vision system... "
        f"(imgsz={imgsz}, conf>={confidence_threshold}%, "
        f"person>={person_min_confidence}%, "
        f"enhance={'on' if enhance_low_light else 'off'}, "
        f"quality={'on' if quality_enabled else 'off'}, "
        f"tracking={'on' if tracking_enabled else 'off'})"
    )
    vision = ImageRecognition(
        confidence=confidence_threshold,
        model=model,
        algorithm=algorithm,
        auto_start=True,
        debug=debug,
        imgsz=imgsz,
        enhance_low_light=enhance_low_light,
        person_min_confidence=person_min_confidence,
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
                    _annotate_board_mm(detections, calibrator, (w_img, h_img), rgb_frame=ref)

            if quality_enabled and detections:
                ref = rgb_frame if rgb_frame is not None else annotated_frame
                if ref is not None:
                    _annotate_quality(detections, ref)

            if tracker is not None and detections:
                frame_index = int(payload.get("frame_index", 0) or 0)
                events = tracker.update(detections, frame_index, time.time())
                if tracker_snapshot_path and frame_index % max(1, tracker_snapshot_every) == 0:
                    tracker.write_snapshot(str(tracker_snapshot_path))
                if tracker_events_path and events:
                    for ev in events:
                        tracker.append_event(str(tracker_events_path), ev)

            if detections:
                stats["frames_with_detections"] += 1
                stats["total_detections"] += len(detections)
                best = max(detections, key=lambda d: d.get("confidence", 0))
                stats["last_best_detection"] = best

                track_suffix = ""
                if best.get("track_id") is not None:
                    track_suffix = f" track #{best['track_id']}"
                print(
                    f"[Frame {payload.get('frame_index', 0)}] "
                    f"{best.get('label', 'unknown')} "
                    f"({best.get('confidence', 0):.2f}%)"
                    f"{track_suffix}"
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
                    quality = best.get("quality") or {}
                    if quality.get("grade"):
                        top_issue = (quality.get("issues") or [None])[0]
                        suffix = f" [{top_issue}]" if top_issue else ""
                        print(
                            f"  quality: {quality['grade']} "
                            f"(defect {quality.get('defect_score', 0.0):.2f}){suffix}"
                        )

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
        image = frame_data.get("annotated_rgb")
        if image is None:
            image = frame_data.get("rgb")
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


def capture_object_snapshots_for_inspection(
    output_dir: str,
    target_count: int = 25,
    max_frames: int = 300,
    confidence_threshold: int = 40,
    model: str = "medium",
    algorithm: str = "yolo",
    debug: bool = False,
) -> int:
    """Capture a dataset of snapshots that contain at least one detected object.

    Saves per sample:
      - <stem>.jpg              raw frame (clean, no overlays — best for re-inference)
      - <stem>_annotated.jpg    annotated frame (boxes + work-zone polygon)
      - <stem>.json             detections + frame metadata
    Returns the number of saved snapshots.
    """
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV not installed. Install with: pip install opencv-python")
        return 0

    target_count = max(1, int(target_count))
    max_frames = max(target_count, int(max_frames))

    base_dir = Path(output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    vision = ImageRecognition(
        confidence=confidence_threshold,
        model=model,
        algorithm=algorithm,
        auto_start=True,
        debug=debug,
    )
    if not vision._zed_enabled:
        print("ERROR: Could not initialize ZED camera")
        return 0

    saved = 0
    seen = 0
    try:
        while saved < target_count and seen < max_frames:
            seen += 1
            frame_data = vision.get_frame()
            if frame_data is None:
                continue

            payload = frame_data.get("payload", {}) or {}
            detections = payload.get("detections", []) or []
            if not detections:
                continue

            raw_image = frame_data.get("rgb")
            annotated_image = frame_data.get("annotated_rgb")
            if raw_image is None and annotated_image is None:
                continue

            stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S_%f")
            stem = f"obj_{saved + 1:04d}_{stamp}"
            image_path = base_dir / f"{stem}.jpg"
            annotated_path = base_dir / f"{stem}_annotated.jpg"
            json_path = base_dir / f"{stem}.json"

            primary = raw_image if raw_image is not None else annotated_image
            if not bool(cv2.imwrite(str(image_path), primary)):
                continue
            if annotated_image is not None and raw_image is not None:
                cv2.imwrite(str(annotated_path), annotated_image)

            snapshot_meta = {
                "saved_at_unix": time.time(),
                "saved_from_frame_index": payload.get("frame_index"),
                "timestamp_unix": payload.get("timestamp_unix"),
                "detection_count": len(detections),
                "detections": detections,
                "image_path": str(image_path),
                "annotated_image_path": (
                    str(annotated_path)
                    if annotated_image is not None and raw_image is not None
                    else None
                ),
            }
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(snapshot_meta, f, indent=2)

            saved += 1
            print(
                f"[{saved}/{target_count}] saved {image_path.name} "
                f"({len(detections)} detections)"
            )
    finally:
        vision.stop()

    print(
        f"Finished dataset capture: saved={saved}, "
        f"frames_seen={seen}, folder={base_dir}"
    )
    return saved


def inspect_snapshot_images(
    image_paths: Iterable[str],
    confidence: int = 35,
    model: str = "medium",
    json_out: str = "",
) -> int:
    """Run snapshot inspector on one or more images."""
    images = [str(Path(p)) for p in _expand_image_inputs(image_paths)]
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


def categorize_snapshot_images(
    image_paths: Iterable[str],
    confidence: int = 35,
    model: str = "medium",
    unclear_confidence_pct: float = 45.0,
    json_out: str = "",
    crops_dir: str = "",
    use_sidecar: bool = True,
) -> int:
    """Categorize snapshot detections into good/bad/unclear/person/other_object.

    By default, when an image was produced by the dataset capture command, its
    sibling `<stem>.json` is used as the source of detections (those benefit
    from the calibrated work-zone crop and tend to find small fruit). Pass
    `use_sidecar=False` to force a fresh full-frame YOLO pass.
    """
    images = [str(Path(p)) for p in _expand_image_inputs(image_paths)]
    missing = [p for p in images if not Path(p).is_file()]
    if missing:
        print("ERROR: file not found:", ", ".join(missing))
        return 1

    inspector = SnapshotProduceInspector(confidence=confidence, model=model)
    report = inspector.categorize(
        images=images,
        unclear_confidence_pct=unclear_confidence_pct,
        prefer_sidecar=use_sidecar,
        crops_dir=crops_dir or None,
    )
    if not report.get("ok"):
        print("ERROR:", report.get("error", "unknown"))
        return 1

    counts = report.get("counts", {}) or {}
    print("Snapshot categorization summary")
    print("  images:", len(images))
    print("  detections:", report.get("item_count", 0))
    print("  good:", counts.get("good", 0))
    print("  bad:", counts.get("bad", 0))
    print("  unclear:", counts.get("unclear", 0))
    print("  person:", counts.get("person", 0))
    print("  other_object:", counts.get("other_object", 0))
    if report.get("crops_dir"):
        print("  crops_dir:", report["crops_dir"])

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
    live.add_argument(
        "--confidence", type=int, default=15,
        help="Min YOLO confidence in %% (default 15; people gated separately at --person-min-confidence)",
    )
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
    live.add_argument(
        "--imgsz", type=int, default=1280,
        help="YOLO inference size in px (default 1280)",
    )
    live.add_argument(
        "--enhance", action="store_true",
        help="Apply CLAHE on the L channel before YOLO for low-light scenes",
    )
    live.add_argument(
        "--no-quality", action="store_true",
        help="Skip per-detection fuzzy quality grading",
    )
    live.add_argument(
        "--person-min-confidence", type=int, default=40,
        help="Drop person detections below this %% (default 40)",
    )
    live.add_argument(
        "--no-tracking", action="store_true",
        help="Skip per-frame ID tracking (no track_id, no outputs/latest_tracks.json)",
    )
    live.add_argument(
        "--tracker-output", default=DEFAULT_TRACKER_SNAPSHOT,
        help=f"Tracker snapshot path (default {DEFAULT_TRACKER_SNAPSHOT}; empty string disables)",
    )
    live.add_argument(
        "--tracker-events", default=DEFAULT_TRACKER_EVENTS,
        help=f"Tracker events JSONL path (default {DEFAULT_TRACKER_EVENTS}; empty string disables)",
    )
    live.add_argument(
        "--tracker-snapshot-every", type=int, default=10,
        help="Write the tracker snapshot every N frames (default 10)",
    )
    live.add_argument(
        "--tracker-radius-mm", type=float,
        default=FruitTracker.DEFAULT_MATCH_RADIUS_MM,
        help=f"Match radius in mm (default {FruitTracker.DEFAULT_MATCH_RADIUS_MM:.0f})",
    )
    live.add_argument(
        "--tracker-max-age-frames", type=int,
        default=FruitTracker.DEFAULT_MAX_AGE_FRAMES,
        help=f"Forget a track after this many unseen frames (default {FruitTracker.DEFAULT_MAX_AGE_FRAMES})",
    )

    snap = sub.add_parser("snapshot", help="Capture and save one frame")
    snap.add_argument("--output", required=True)
    snap.add_argument("--confidence", type=int, default=40)
    snap.add_argument("--model", default="medium")
    snap.add_argument("--algorithm", default="yolo", choices=["yolo", "zed"])
    snap.add_argument("--debug", action="store_true")

    collect = sub.add_parser(
        "snapshot-dataset",
        help="Capture multiple snapshots that contain detected objects",
    )
    collect.add_argument("--output-dir", required=True)
    collect.add_argument("--count", type=int, default=25)
    collect.add_argument("--max-frames", type=int, default=300)
    collect.add_argument("--confidence", type=int, default=40)
    collect.add_argument("--model", default="medium")
    collect.add_argument("--algorithm", default="yolo", choices=["yolo", "zed"])
    collect.add_argument("--debug", action="store_true")

    inspect = sub.add_parser("inspect", help="Run snapshot produce inspection")
    inspect.add_argument("--images", nargs="+", required=True)
    inspect.add_argument("--confidence", type=int, default=35)
    inspect.add_argument("--model", default="medium")
    inspect.add_argument("--json-out", default="")

    categorize = sub.add_parser(
        "categorize",
        help="Categorize detections: good/bad/unclear/person/other_object",
    )
    categorize.add_argument("--images", nargs="+", required=True)
    categorize.add_argument("--confidence", type=int, default=35)
    categorize.add_argument("--model", default="medium")
    categorize.add_argument("--unclear-confidence", type=float, default=45.0)
    categorize.add_argument("--json-out", default="")
    categorize.add_argument(
        "--crops-dir",
        default="",
        help="Save per-detection crops into category subfolders here.",
    )
    categorize.add_argument(
        "--no-sidecar",
        action="store_true",
        help="Ignore <stem>.json sidecars and run YOLO on the full image.",
    )

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
            imgsz=args.imgsz,
            enhance_low_light=args.enhance,
            quality_enabled=not args.no_quality,
            person_min_confidence=args.person_min_confidence,
            tracking_enabled=not args.no_tracking,
            tracker_output=args.tracker_output,
            tracker_events=args.tracker_events,
            tracker_snapshot_every=args.tracker_snapshot_every,
            tracker_radius_mm=args.tracker_radius_mm,
            tracker_max_age_frames=args.tracker_max_age_frames,
        ) else 1
    if args.command == "snapshot":
        return 0 if capture_and_save_snapshot(
            output_path=args.output,
            confidence_threshold=args.confidence,
            model=args.model,
            algorithm=args.algorithm,
            debug=args.debug,
        ) else 1
    if args.command == "snapshot-dataset":
        saved = capture_object_snapshots_for_inspection(
            output_dir=args.output_dir,
            target_count=args.count,
            max_frames=args.max_frames,
            confidence_threshold=args.confidence,
            model=args.model,
            algorithm=args.algorithm,
            debug=args.debug,
        )
        return 0 if saved > 0 else 1
    if args.command == "categorize":
        return categorize_snapshot_images(
            image_paths=args.images,
            confidence=args.confidence,
            model=args.model,
            unclear_confidence_pct=args.unclear_confidence,
            json_out=args.json_out,
            crops_dir=args.crops_dir,
            use_sidecar=not args.no_sidecar,
        )
    return inspect_snapshot_images(
        image_paths=args.images,
        confidence=args.confidence,
        model=args.model,
        json_out=args.json_out,
    )


if __name__ == "__main__":
    raise SystemExit(main())
