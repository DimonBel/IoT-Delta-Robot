"""Camera <-> robot table calibration.

Public API. The package is organised as:
    core.py     pure math + IO (numpy, no cv2)
    draw.py     result-image rendering (cv2, lazy import)
    runtime.py  Calibrator + detection helpers (used by the live loop)
    ui.py       interactive click UI    (`python -m vision.calibration.ui`)
    verify.py   CLI sanity-check        (`python -m vision.calibration.verify`)

Existing code that did `from vision.calibration import X` keeps working
because the names below are re-exported here.
"""

from .core import (
    DEFAULT_PICK_HEIGHT_MM,
    HARDWARE_LIMITS,
    SCHEMA_VERSION,
    Calibration,
    CalibrationPoint,
    PolyFit,
    WorkZone,
    auto_select_degree,
    build_square_calibration_points,
    derive_work_zone,
    fit_polynomial,
    generate_grid_targets,
    infer_hidden_corner,
    intersect_infinite_lines_2d,
    load_calibration,
    pixel_to_robot_xy,
    save_calibration,
)
from .draw import draw_result_image, fit_inverse_polynomial
from .runtime import Calibrator, detection_center, refined_detection_center

__all__ = [
    "DEFAULT_PICK_HEIGHT_MM",
    "HARDWARE_LIMITS",
    "SCHEMA_VERSION",
    "Calibration",
    "CalibrationPoint",
    "Calibrator",
    "PolyFit",
    "WorkZone",
    "auto_select_degree",
    "build_square_calibration_points",
    "derive_work_zone",
    "detection_center",
    "draw_result_image",
    "fit_inverse_polynomial",
    "fit_polynomial",
    "generate_grid_targets",
    "infer_hidden_corner",
    "intersect_infinite_lines_2d",
    "load_calibration",
    "pixel_to_robot_xy",
    "refined_detection_center",
    "save_calibration",
]
