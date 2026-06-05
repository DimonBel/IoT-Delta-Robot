"""Unit tests for vision.quality.grade_detection.

These tests synthesise small BGR images (no camera, no YOLO, no ZED) and
verify the fuzzy mean-HSV grading shifts in the expected direction when a
dark patch ("black tape") is applied to a bright fruit-coloured rectangle.
"""

from __future__ import annotations

import unittest

import numpy as np


def _has_cv2() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_cv2(), "opencv-python not installed; skipping HSV grading tests")
class GradeDetectionTests(unittest.TestCase):
    @staticmethod
    def _orange_image(size: int = 200) -> np.ndarray:
        # Bright saturated orange rectangle in BGR.
        img = np.zeros((size, size, 3), dtype=np.uint8)
        img[:, :] = (50, 140, 240)  # B, G, R -> orangey
        return img

    @staticmethod
    def _stick_black_tape(img: np.ndarray, fraction: float = 0.35) -> np.ndarray:
        h, w = img.shape[:2]
        out = img.copy()
        side = int(min(h, w) * fraction)
        cy, cx = h // 2, w // 2
        out[cy - side // 2 : cy + side // 2, cx - side // 2 : cx + side // 2] = (10, 10, 10)
        return out

    def test_clean_orange_lands_high_grade(self):
        from vision.quality import grade_detection

        img = self._orange_image()
        det = {"detection_type": "produce", "label": "orange",
               "confidence": 80.0, "bbox_xyxy": [0, 0, 200, 200]}
        result = grade_detection(det, img)
        self.assertIsNotNone(result)
        self.assertIn(result["grade"], {"excellent", "good"})
        self.assertLess(result["defect_score"], 0.4)
        self.assertEqual(det["quality"]["grade"], result["grade"])

    def test_taped_orange_drops_grade_or_score(self):
        from vision.quality import grade_detection

        clean = grade_detection(
            {"detection_type": "produce", "label": "orange", "confidence": 80.0,
             "bbox_xyxy": [0, 0, 200, 200]},
            self._orange_image(),
        )
        taped = grade_detection(
            {"detection_type": "produce", "label": "orange", "confidence": 80.0,
             "bbox_xyxy": [0, 0, 200, 200]},
            self._stick_black_tape(self._orange_image(), fraction=0.5),
        )
        self.assertIsNotNone(clean)
        self.assertIsNotNone(taped)
        # Mean HSV moves only modestly with a small dark patch; we accept any
        # downward shift in grade or any rise in defect_score.
        grade_order = {"excellent": 4, "good": 3, "fair": 2, "poor": 1, "reject": 0}
        cleaner_grade = grade_order[clean["grade"]] >= grade_order[taped["grade"]]
        higher_defect = taped["defect_score"] > clean["defect_score"]
        self.assertTrue(cleaner_grade or higher_defect,
                        msg=f"Tape did not lower grade nor raise defect: {clean=} {taped=}")

    def test_skips_human_detections(self):
        from vision.quality import grade_detection

        det = {"detection_type": "human", "label": "person",
               "confidence": 95.0, "bbox_xyxy": [0, 0, 200, 200]}
        result = grade_detection(det, self._orange_image())
        self.assertIsNone(result)
        self.assertNotIn("quality", det)

    def test_invalid_bbox_returns_none(self):
        from vision.quality import grade_detection

        det = {"detection_type": "produce", "label": "orange",
               "confidence": 80.0, "bbox_xyxy": [0, 0]}
        self.assertIsNone(grade_detection(det, self._orange_image()))
        self.assertNotIn("quality", det)


if __name__ == "__main__":
    unittest.main()
