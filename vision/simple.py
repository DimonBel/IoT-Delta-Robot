"""Tiny high-level helpers for everyday use.

Two one-liners on top of the YOLO + ZED pipeline:

    from vision import live, snapshot

    live()                # opens a window, shows detections, q to quit
    frame = snapshot()    # returns one frame + its detections

Both use the calibration JSON at calibration/calibration.json (if present)
to crop YOLO inference to the calibrated work square. This produces stronger
recall on small/distant fruit and keeps the loop fast enough for >=30 FPS.

Defaults are tuned for speed: yolov8n (`fast`) at imgsz=416 every frame.
Pass `model="medium"` or `model="accurate"` if you have GPU headroom.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from vision.commands import capture_object_snapshots_for_inspection, run_live_vision
from vision.vision import ImageRecognition


def live(
    duration_seconds: int = 0,
    confidence: int = 30,
    model: str = "fast",
    show: bool = True,
    debug: bool = False,
) -> bool:
    """Run the live ZED + YOLO loop.

    Args:
        duration_seconds: 0 to run until the user presses 'q'.
        confidence: percent threshold (0-100). Lower catches more distant fruit.
        model: "fast" (yolov8n, ~30+ FPS), "medium", "accurate", or path to .pt.
        show: open a window with bounding boxes and the work-zone polygon.
        debug: print verbose ZED/YOLO init info.
    """
    return run_live_vision(
        duration_seconds=duration_seconds,
        confidence_threshold=confidence,
        model=model,
        algorithm="yolo",
        skip_display=not show,
        debug=debug,
        print_coordinates=False,
    )


def snapshot(
    confidence: int = 30,
    model: str = "fast",
    warmup_frames: int = 3,
    debug: bool = False,
) -> Dict[str, Any]:
    """Grab one frame from the ZED with detections.

    Returns a dict with:
        rgb           : raw BGR numpy frame
        annotated_rgb : BGR frame with boxes + work-zone polygon drawn
        detections    : list[dict] (label, confidence, bbox_xyxy, in_work_zone, ...)

    Returns an empty dict on failure (camera not available).
    """
    vision = ImageRecognition(
        confidence=confidence,
        model=model,
        algorithm="yolo",
        auto_start=True,
        debug=debug,
    )
    if not vision._zed_enabled:
        vision.stop()
        return {}

    try:
        frame: Optional[Dict[str, Any]] = None
        for _ in range(max(1, warmup_frames)):
            frame = vision.get_frame()
            if frame is not None:
                break
        if frame is None:
            return {}

        payload = frame.get("payload", {}) or {}
        detections: List[Dict[str, Any]] = payload.get("detections", []) or []
        return {
            "rgb": frame.get("rgb"),
            "annotated_rgb": frame.get("annotated_rgb"),
            "detections": detections,
        }
    finally:
        vision.stop()


def snapshot_dataset(
    output_dir: str = "outputs/snapshot_inspection",
    count: int = 25,
    max_frames: int = 300,
    confidence: int = 30,
    model: str = "fast",
    debug: bool = False,
) -> int:
    """Capture a dataset of snapshots that include detected objects.

    Each saved sample contains:
      - `<name>.jpg` annotated image
      - `<name>.json` detection metadata
    """
    return capture_object_snapshots_for_inspection(
        output_dir=output_dir,
        target_count=count,
        max_frames=max_frames,
        confidence_threshold=confidence,
        model=model,
        algorithm="yolo",
        debug=debug,
    )
