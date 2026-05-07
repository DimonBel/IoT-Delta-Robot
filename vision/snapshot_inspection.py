"""Offline / snapshot produce inspection: classify items, grade quality, fuzzy fusion, issue hints."""
from __future__ import annotations

import importlib
import math
import os
from typing import Any, Dict, List, Optional, Union

import numpy as np

from vision.labels import FRUIT_VEGETABLE_CLASSES, PRODUCE_ALIASES, classify_yolo_label


ImageInput = Union[str, np.ndarray, "os.PathLike[str]"]


def _trap_mf(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoid membership on [a,d], flat on [b,c]."""
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a) if b != a else 1.0
    return (d - x) / (d - c) if d != c else 1.0


def _tri_mf(x: float, a: float, b: float, c: float) -> float:
    """Triangle peak at b."""
    if x <= a or x >= c:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


def fuzzy_quality_fusion(
    defect_score: float,
    conf_norm: float,
) -> Dict[str, Any]:
    """
    Combine defect hint (0=perfect, 1=worst) and normalized confidence (0–1) into fuzzy grades.
    Returns memberships and a defuzzified label.
    """
    d = max(0.0, min(1.0, defect_score))
    cn = max(0.0, min(1.0, conf_norm))

    excellent = _trap_mf(d, -0.01, 0.0, 0.12, 0.22) * _trap_mf(cn, 0.35, 0.55, 1.0, 1.01)
    good = _tri_mf(d, 0.1, 0.25, 0.45) * _trap_mf(cn, 0.25, 0.4, 1.0, 1.01)
    fair = _tri_mf(d, 0.3, 0.5, 0.68)
    poor = _tri_mf(d, 0.55, 0.72, 0.88)
    reject = _trap_mf(d, 0.78, 0.88, 1.0, 1.01)

    memberships = {
        "excellent": float(excellent),
        "good": float(good),
        "fair": float(fair),
        "poor": float(poor),
        "reject": float(reject),
    }
    best = max(memberships, key=memberships.get)
    return {
        "quality_grade": best,
        "memberships": memberships,
        "defect_score": d,
        "confidence_norm": cn,
    }


def _hsv_means_bgr(bgr: np.ndarray) -> Optional[Dict[str, float]]:
    try:
        cv2 = importlib.import_module("cv2")
    except Exception:
        return None
    if bgr is None or bgr.size == 0:
        return None
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    m = hsv.reshape(-1, 3).mean(axis=0)
    return {"mean_h": float(m[0]), "mean_s": float(m[1]), "mean_v": float(m[2])}


def _defect_hints_from_label_and_vision(
    label: str,
    conf_pct: float,
    hsv: Optional[Dict[str, float]],
) -> tuple[float, List[str]]:
    """Heuristic defect score 0–1 and human-readable AI-style issue strings."""
    n = (label or "").lower()
    defect = 0.0
    issues: List[str] = []

    spoil_kw = ("rotten", "spoiled", "bad", "mold", "damage", "bruise")
    if any(k in n for k in spoil_kw):
        defect += 0.75
        issues.append("model_or_label_suggests_spoilage_keyword")

    fresh_kw = ("fresh", "good")
    if any(k in n for k in fresh_kw):
        defect = max(0.0, defect - 0.25)
        issues.append("positive_freshness_keyword")

    if conf_pct < 35.0:
        defect += 0.15
        issues.append("low_detection_confidence")

    if hsv is not None:
        if hsv["mean_v"] < 70.0:
            defect += 0.12
            issues.append("low_brightness_may_indicate_decay_or_shadow")
        if hsv["mean_s"] < 40.0:
            defect += 0.08
            issues.append("low_saturation_may_indicate_dullness")

    defect = max(0.0, min(1.0, defect))
    return defect, issues


class SnapshotProduceInspector:
    """
    Runs YOLO on one or more still images, keeps only produce-like detections,
    and grades them with fuzzy fusion plus lightweight vision cues.
    """

    def __init__(
        self,
        confidence: int = 35,
        model: str = "medium",
        imgsz: int = 640,
    ):
        self.confidence = confidence
        self.model = model
        self.imgsz = imgsz
        self._yolo = None
        self._class_names: Dict[int, str] = {}
        self._device: Any = "cpu"
        self._half = False

    def _ensure_yolo(self) -> bool:
        if self._yolo is not None:
            return True
        try:
            yolo_cls = importlib.import_module("ultralytics").YOLO
            torch_mod = importlib.import_module("torch")
            presets = {
                "fast": "yolov8n.pt",
                "medium": "yolov8m.pt",
                "accurate": "yolov8l.pt",
                "extreme": "yolov8x.pt",
            }
            weights = presets.get(self.model, self.model)
            self._yolo = yolo_cls(weights)
            self._class_names = getattr(self._yolo, "names", {}) or {}
            cuda_ok = bool(torch_mod.cuda.is_available())
            self._device = 0 if cuda_ok else "cpu"
            self._half = cuda_ok
            return True
        except Exception:
            return False

    @staticmethod
    def _load_bgr(image: ImageInput) -> Optional[np.ndarray]:
        if isinstance(image, np.ndarray):
            return image
        try:
            cv2 = importlib.import_module("cv2")
            path = os.fspath(image)
            arr = cv2.imread(path)
            return arr
        except Exception:
            return None

    def inspect(self, images: List[ImageInput]) -> Dict[str, Any]:
        if not self._ensure_yolo():
            return {"ok": False, "error": "ultralytics_or_torch_unavailable", "items": []}

        conf_th = max(0.01, min(0.99, self.confidence / 100.0))
        items: List[Dict[str, Any]] = []

        for img_in in images:
            bgr = self._load_bgr(img_in)
            if bgr is None:
                items.append({"ok": False, "error": "could_not_load_image"})
                continue

            try:
                results = self._yolo.predict(
                    source=bgr,
                    conf=conf_th,
                    imgsz=self.imgsz,
                    device=self._device,
                    half=self._half,
                    verbose=False,
                )
            except Exception as e:
                items.append({"ok": False, "error": str(e)})
                continue

            if not results:
                continue
            res = results[0]
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue

            h, w = bgr.shape[:2]
            for box in boxes:
                cls_id = int(float(box.cls[0])) if box.cls is not None else -1
                src_label = str(self._class_names.get(cls_id, f"class_{cls_id}"))
                kind, canonical = classify_yolo_label(src_label)
                if kind != "produce":
                    continue
                conf_pct = float(box.conf[0]) * 100.0 if box.conf is not None else 0.0
                xyxy = box.xyxy[0].tolist() if box.xyxy is not None else [0, 0, 0, 0]
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w - 1, x2), min(h - 1, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                crop = bgr[y1:y2, x1:x2]
                hsv = _hsv_means_bgr(crop)
                defect, issues = _defect_hints_from_label_and_vision(
                    canonical or src_label, conf_pct, hsv
                )
                fuzzy = fuzzy_quality_fusion(defect, conf_pct / 100.0)

                recognized = canonical if canonical in FRUIT_VEGETABLE_CLASSES else None
                if recognized is None and kind == "produce":
                    recognized = PRODUCE_ALIASES.get(src_label.lower().strip()) or (
                        src_label.lower().strip()
                        if src_label.lower().strip() in FRUIT_VEGETABLE_CLASSES
                        else None
                    )

                items.append(
                    {
                        "ok": True,
                        "source_label": src_label,
                        "produce_kind": recognized or "unrecognised_produce",
                        "detection_confidence_pct": round(conf_pct, 2),
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "hsv_summary": hsv,
                        "defect_score": defect,
                        "fuzzy": fuzzy,
                        "possible_issues": issues,
                    }
                )

        return {"ok": True, "item_count": len(items), "items": items}
