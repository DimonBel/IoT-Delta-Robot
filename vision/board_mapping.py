"""Homography helpers: map image points into normalized board coordinates (0–1)."""
from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

import math


def bbox_to_quad_xyxy(x1: int, y1: int, x2: int, y2: int) -> Any:
    """Return 4 corners TL, TR, BR, BL as a float32 array for cv2.getPerspectiveTransform."""
    import numpy as np

    return np.array(
        [
            [float(x1), float(y1)],
            [float(x2), float(y1)],
            [float(x2), float(y2)],
            [float(x1), float(y2)],
        ],
        dtype=np.float32,
    )


def build_image_to_board_homography(quad_xy: Any) -> Any:
    """quad_xy: 4x2 in image space (TL, TR, BR, BL). Maps image -> board UV with U,V in [0,1]."""
    import numpy as np
    import cv2

    dst = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(quad_xy, dst)


def image_point_to_board_uv(H: Any, x: float, y: float) -> Tuple[Optional[float], Optional[float]]:
    """Apply homography H (image -> board unit square). Returns (u, v) or (None, None) if degenerate."""
    import numpy as np
    import cv2

    if H is None:
        return None, None
    pts = np.array([[[float(x), float(y)]]], dtype=np.float32)
    try:
        out = cv2.perspectiveTransform(pts, H)
    except cv2.error:
        return None, None
    u, v = float(out[0, 0, 0]), float(out[0, 0, 1])
    if not (math.isfinite(u) and math.isfinite(v)):
        return None, None
    return u, v


def board_payload_from_state(
    initialized: bool,
    quad_xy: Optional[Sequence[Sequence[float]]],
    H: Any,
) -> dict:
    """Serializable board state for frame payloads."""
    return {
        "initialized": bool(initialized),
        "quad_corners_xy": quad_xy,
        "homography_ready": H is not None and initialized,
    }
