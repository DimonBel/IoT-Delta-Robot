"""Offline / snapshot produce inspection: classify items, grade quality, fuzzy fusion, issue hints."""
from __future__ import annotations

import importlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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

    def _grade_produce(
        self,
        bgr: np.ndarray,
        bbox: Tuple[int, int, int, int],
        src_label: str,
        canonical: Optional[str],
        conf_pct: float,
        unclear_confidence_pct: float,
    ) -> Dict[str, Any]:
        """Run quality analysis on a produce crop and assign category."""
        x1, y1, x2, y2 = bbox
        crop = bgr[y1:y2, x1:x2]
        hsv = _hsv_means_bgr(crop)
        defect, issues = _defect_hints_from_label_and_vision(
            canonical or src_label, conf_pct, hsv
        )
        fuzzy = fuzzy_quality_fusion(defect, conf_pct / 100.0)
        grade = str(fuzzy.get("quality_grade") or "")

        recognised = canonical if canonical in FRUIT_VEGETABLE_CLASSES else None
        if recognised is None:
            alias = PRODUCE_ALIASES.get((src_label or "").lower().strip())
            if alias and alias in FRUIT_VEGETABLE_CLASSES:
                recognised = alias

        if conf_pct < unclear_confidence_pct or recognised is None:
            category = "unclear"
        elif grade in {"poor", "reject"} or any(
            "spoilage" in issue for issue in issues
        ):
            category = "bad"
        else:
            category = "good"

        return {
            "category": category,
            "produce_kind": recognised or "unrecognised_produce",
            "hsv_summary": hsv,
            "defect_score": defect,
            "fuzzy": fuzzy,
            "possible_issues": issues,
        }

    @staticmethod
    def _load_sidecar_detections(image_path: str) -> Optional[List[Dict[str, Any]]]:
        """Return capture-time detections from <stem>.json next to the image."""
        try:
            base = Path(image_path)
            sidecar = base.with_suffix(".json")
            if not sidecar.is_file():
                stem = base.stem
                if stem.endswith("_annotated"):
                    sidecar = base.with_name(stem[: -len("_annotated")] + ".json")
                if not sidecar.is_file():
                    return None
            with sidecar.open("r", encoding="utf-8") as f:
                data = json.load(f)
            detections = data.get("detections")
            if isinstance(detections, list):
                return detections
        except Exception:
            return None
        return None

    @staticmethod
    def _bbox_iou(
        a: Tuple[int, int, int, int],
        b: Tuple[int, int, int, int],
    ) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1, (bx2 - bx1) * (by2 - by1))
        return inter / float(area_a + area_b - inter)

    def _supplement_with_full_frame(
        self,
        bgr: np.ndarray,
        image_path: Optional[str],
        stem: str,
        existing_produce_boxes: List[Tuple[int, int, int, int]],
        crop_root: Optional[Path],
        unclear_confidence_pct: float,
        items: List[Dict[str, Any]],
        counts: Dict[str, int],
        skip_produce: bool = True,
    ) -> None:
        """Run a full-image YOLO pass and append non-produce categories.

        Used after the sidecar pass to surface persons and miscellaneous
        objects that fall outside the calibrated work zone.
        """
        h, w = bgr.shape[:2]
        conf_th = max(0.01, min(0.99, self.confidence / 100.0))
        try:
            results = self._yolo.predict(
                source=bgr,
                conf=conf_th,
                imgsz=self.imgsz,
                device=self._device,
                half=self._half,
                verbose=False,
            )
        except Exception:
            return
        if not results:
            return
        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None:
            return

        existing_idx = len(items)
        for box_idx, box in enumerate(boxes):
            cls_id = int(float(box.cls[0])) if box.cls is not None else -1
            src_label = str(self._class_names.get(cls_id, f"class_{cls_id}"))
            kind, canonical = classify_yolo_label(src_label)
            conf_pct = float(box.conf[0]) * 100.0 if box.conf is not None else 0.0
            xyxy = box.xyxy[0].tolist() if box.xyxy is not None else [0, 0, 0, 0]
            x1, y1, x2, y2 = [int(v) for v in xyxy]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            if skip_produce and kind == "produce":
                continue
            # Avoid double-listing produce that the sidecar already covered.
            if kind == "produce" and any(
                self._bbox_iou((x1, y1, x2, y2), pb) >= 0.4
                for pb in existing_produce_boxes
            ):
                continue

            base_item: Dict[str, Any] = {
                "ok": True,
                "image_path": image_path,
                "source_label": src_label,
                "detection_type": kind,
                "detection_confidence_pct": round(conf_pct, 2),
                "bbox_xyxy": [x1, y1, x2, y2],
                "source": "yolo_full_image",
                "possible_issues": [],
            }

            if kind == "human":
                base_item["category"] = "person"
                counts["person"] += 1
            elif kind == "produce":
                graded = self._grade_produce(
                    bgr,
                    (x1, y1, x2, y2),
                    src_label,
                    canonical,
                    conf_pct,
                    unclear_confidence_pct,
                )
                base_item.update(graded)
                counts[graded["category"]] += 1
            else:
                base_item["category"] = "other_object"
                counts["other_object"] += 1

            crop_path = self._save_crop(
                bgr,
                (x1, y1, x2, y2),
                crop_root,
                base_item["category"],
                stem,
                existing_idx + box_idx,
            )
            if crop_path:
                base_item["crop_path"] = crop_path
            items.append(base_item)

    def _save_crop(
        self,
        bgr: np.ndarray,
        bbox: Tuple[int, int, int, int],
        crop_dir: Optional[Path],
        category: str,
        stem: str,
        index: int,
    ) -> Optional[str]:
        if crop_dir is None or bgr is None:
            return None
        try:
            cv2 = importlib.import_module("cv2")
        except Exception:
            return None
        x1, y1, x2, y2 = bbox
        crop = bgr[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return None
        target_dir = crop_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / f"{stem}_{index:02d}.jpg"
        if not cv2.imwrite(str(out_path), crop):
            return None
        return str(out_path)

    def categorize(
        self,
        images: List[ImageInput],
        unclear_confidence_pct: float = 45.0,
        prefer_sidecar: bool = True,
        crops_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Categorize detections as good/bad/unclear/person/other_object.

        Categories:
          - good: produce with acceptable quality and confidence
          - bad: produce with fuzzy quality poor/reject or spoilage hints
          - unclear: low confidence or unknown produce
          - person: human detection
          - other_object: non-produce/non-person object-like detections

        When `prefer_sidecar=True` (default), the function reads `<image>.json`
        produced by the capture pipeline (which uses the calibrated work-zone
        crop and tends to find small fruit at distance). Each produce detection
        is then quality-graded from the saved image. If no sidecar exists, a
        full-frame YOLO pass is used as a fallback.

        When `crops_dir` is set, each detection's crop is saved into a
        per-category subfolder for fast visual review and dataset prep.
        """
        items: List[Dict[str, Any]] = []
        counts = {
            "good": 0,
            "bad": 0,
            "unclear": 0,
            "person": 0,
            "other_object": 0,
        }

        crop_root: Optional[Path] = None
        if crops_dir:
            crop_root = Path(crops_dir)
            crop_root.mkdir(parents=True, exist_ok=True)

        yolo_ready: Optional[bool] = None

        for img_in in images:
            image_path = (
                os.fspath(img_in) if not isinstance(img_in, np.ndarray) else None
            )
            stem = Path(image_path).stem if image_path else "image"
            bgr = self._load_bgr(img_in)
            if bgr is None:
                items.append(
                    {
                        "ok": False,
                        "error": "could_not_load_image",
                        "image_path": image_path,
                        "category": "unclear",
                    }
                )
                counts["unclear"] += 1
                continue

            h, w = bgr.shape[:2]

            sidecar_dets: Optional[List[Dict[str, Any]]] = None
            if prefer_sidecar and image_path:
                sidecar_dets = self._load_sidecar_detections(image_path)

            sidecar_produce_boxes: List[Tuple[int, int, int, int]] = []
            if sidecar_dets is not None:
                for idx, det in enumerate(sidecar_dets):
                    bbox_raw = det.get("bbox_xyxy") or [0, 0, 0, 0]
                    try:
                        x1, y1, x2, y2 = [int(v) for v in bbox_raw]
                    except (TypeError, ValueError):
                        continue
                    x1 = max(0, min(w - 1, x1))
                    y1 = max(0, min(h - 1, y1))
                    x2 = max(x1 + 1, min(w, x2))
                    y2 = max(y1 + 1, min(h, y2))
                    if x2 <= x1 or y2 <= y1:
                        continue

                    src_label = str(det.get("source_label") or det.get("label") or "")
                    kind = str(det.get("detection_type") or "")
                    if not kind:
                        kind, _ = classify_yolo_label(src_label)
                    canonical_raw = (
                        det.get("produce_kind")
                        or det.get("label")
                        or src_label
                        or ""
                    )
                    canonical = str(canonical_raw).lower().strip() or None
                    conf_pct = float(det.get("confidence") or 0.0)

                    base_item: Dict[str, Any] = {
                        "ok": True,
                        "image_path": image_path,
                        "source_label": src_label,
                        "detection_type": kind,
                        "detection_confidence_pct": round(conf_pct, 2),
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "source": "capture_sidecar",
                        "possible_issues": [],
                    }

                    if kind == "human":
                        base_item["category"] = "person"
                        counts["person"] += 1
                    elif kind == "produce":
                        graded = self._grade_produce(
                            bgr,
                            (x1, y1, x2, y2),
                            src_label,
                            canonical,
                            conf_pct,
                            unclear_confidence_pct,
                        )
                        base_item.update(graded)
                        counts[graded["category"]] += 1
                        sidecar_produce_boxes.append((x1, y1, x2, y2))
                    else:
                        base_item["category"] = "other_object"
                        counts["other_object"] += 1

                    crop_path = self._save_crop(
                        bgr,
                        (x1, y1, x2, y2),
                        crop_root,
                        base_item["category"],
                        stem,
                        idx,
                    )
                    if crop_path:
                        base_item["crop_path"] = crop_path
                    items.append(base_item)

                # Supplement with full-frame YOLO so persons and miscellaneous
                # objects (which the work-zone-cropped capture pass cannot see)
                # still get categorized. Produce is intentionally skipped here
                # so the higher-quality sidecar grading wins.
                if yolo_ready is None:
                    yolo_ready = self._ensure_yolo()
                if yolo_ready:
                    self._supplement_with_full_frame(
                        bgr,
                        image_path,
                        stem,
                        sidecar_produce_boxes,
                        crop_root,
                        unclear_confidence_pct,
                        items,
                        counts,
                        skip_produce=True,
                    )
                continue

            # Fallback: no sidecar — run YOLO on the full image.
            if yolo_ready is None:
                yolo_ready = self._ensure_yolo()
            if not yolo_ready:
                items.append(
                    {
                        "ok": False,
                        "error": "ultralytics_or_torch_unavailable",
                        "image_path": image_path,
                        "category": "unclear",
                    }
                )
                counts["unclear"] += 1
                continue

            conf_th = max(0.01, min(0.99, self.confidence / 100.0))
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
                items.append(
                    {
                        "ok": False,
                        "error": str(e),
                        "image_path": image_path,
                        "category": "unclear",
                    }
                )
                counts["unclear"] += 1
                continue

            if not results:
                continue
            res = results[0]
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue

            for idx, box in enumerate(boxes):
                cls_id = int(float(box.cls[0])) if box.cls is not None else -1
                src_label = str(self._class_names.get(cls_id, f"class_{cls_id}"))
                kind, canonical = classify_yolo_label(src_label)
                conf_pct = float(box.conf[0]) * 100.0 if box.conf is not None else 0.0
                xyxy = box.xyxy[0].tolist() if box.xyxy is not None else [0, 0, 0, 0]
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w - 1, x2), min(h - 1, y2)
                if x2 <= x1 or y2 <= y1:
                    continue

                base_item = {
                    "ok": True,
                    "image_path": image_path,
                    "source_label": src_label,
                    "detection_type": kind,
                    "detection_confidence_pct": round(conf_pct, 2),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "source": "yolo_full_image",
                    "possible_issues": [],
                }

                if kind == "human":
                    base_item["category"] = "person"
                    counts["person"] += 1
                elif kind == "produce":
                    graded = self._grade_produce(
                        bgr,
                        (x1, y1, x2, y2),
                        src_label,
                        canonical,
                        conf_pct,
                        unclear_confidence_pct,
                    )
                    base_item.update(graded)
                    counts[graded["category"]] += 1
                else:
                    base_item["category"] = "other_object"
                    counts["other_object"] += 1

                crop_path = self._save_crop(
                    bgr,
                    (x1, y1, x2, y2),
                    crop_root,
                    base_item["category"],
                    stem,
                    idx,
                )
                if crop_path:
                    base_item["crop_path"] = crop_path
                items.append(base_item)

        return {
            "ok": True,
            "item_count": len(items),
            "counts": counts,
            "items": items,
            "crops_dir": str(crop_root) if crop_root is not None else None,
        }
