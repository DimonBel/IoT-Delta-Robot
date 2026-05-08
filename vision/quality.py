"""Live-loop quality grading for produce detections.

Reuses the colleague's offline fuzzy grading helpers from
vision.snapshot_inspection without copying their code. Apply this to one
detection at a time inside the live loop:

    from vision.quality import grade_detection

    for d in detections:
        grade_detection(d, rgb_frame)
        # d["quality"] is now set if d is produce-like, otherwise unchanged.

The grade is mean-HSV based, so it shifts gradually as fruit darkens or
loses saturation. Tiny dark spots on a bright fruit move the mean only
slightly; if you need stronger small-defect signal, add a pixel-level
dark-blob check on top (out of scope for this PR).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from vision.snapshot_inspection import (
    _defect_hints_from_label_and_vision,
    _hsv_means_bgr,
    fuzzy_quality_fusion,
)


def _bbox_crop(rgb_frame, bbox_xyxy):
    """Return the BGR crop inside the bbox, or None if invalid/empty."""
    if rgb_frame is None or bbox_xyxy is None:
        return None
    if len(bbox_xyxy) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(round(float(v))) for v in bbox_xyxy)
    except (TypeError, ValueError):
        return None

    h, w = rgb_frame.shape[:2]
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(0, min(w, x2))
    y2 = max(0, min(h, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = rgb_frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def grade_detection(
    detection: Mapping[str, Any],
    rgb_frame,
) -> Optional[dict]:
    """Compute a fuzzy quality grade for one produce detection in-place.

    Modifies `detection` to add:
        detection["quality"] = {
            "grade":        "excellent" | "good" | "fair" | "poor" | "reject",
            "defect_score": float in [0, 1],
            "issues":       [str, ...],
            "memberships":  {grade -> float},
            "hsv":          {"mean_h", "mean_s", "mean_v"} | None,
        }

    Returns the same dict, or None for non-produce detections / missing
    bbox / empty crop.
    """
    if not isinstance(detection, Mapping):
        return None
    if detection.get("detection_type") not in ("produce", None):
        # Only grade things classified as produce. Untyped detections
        # (e.g. raw YOLO output not yet classified) are graded leniently.
        if detection.get("detection_type") is not None:
            return None

    bbox = detection.get("bbox_xyxy")
    if not isinstance(bbox, Sequence):
        return None
    crop = _bbox_crop(rgb_frame, bbox)
    if crop is None:
        return None

    label = str(detection.get("label") or "")
    confidence = float(detection.get("confidence") or 0.0)

    hsv = _hsv_means_bgr(crop)
    defect_score, issues = _defect_hints_from_label_and_vision(
        label, confidence, hsv
    )
    fuzzy = fuzzy_quality_fusion(defect_score, max(0.0, min(1.0, confidence / 100.0)))

    quality = {
        "grade": fuzzy["quality_grade"],
        "defect_score": float(defect_score),
        "issues": list(issues),
        "memberships": fuzzy["memberships"],
        "hsv": hsv,
    }
    # Type the cast through dict() so callers can rely on plain dict semantics.
    if not isinstance(detection, dict):
        return quality
    detection["quality"] = quality
    return quality
