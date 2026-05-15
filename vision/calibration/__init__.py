"""Camera <-> robot table calibration.

Public API. The package is organised as:
    core.py   pure math + IO (numpy, no cv2)
    draw.py   result-image rendering (cv2, lazy import)
    ui.py     interactive click UI            (`python -m vision.calibration.ui`)
    demo.py   one-shot stereo-photo demo      (`python -m vision.calibration.demo`)

Existing code that did `from vision.calibration import X` keeps working because
the names below are re-exported here.
"""

from .core import (
    DEFAULT_PICK_HEIGHT_MM,
    HARDWARE_LIMITS,
    SCHEMA_VERSION,
    Calibration,
    CalibrationPoint,
    PolyFit,
    ToolCenterOffset,
    WorkZone,
    auto_select_degree,
    compute_tool_center_offset,
    default_master_workspace,
    derive_work_zone,
    fit_polynomial,
    generate_grid_targets,
    infer_missing_grid_corner_from_edge_points,
    intersect_infinite_lines_2d,
    load_calibration,
    pixel_to_robot_xy,
    robot_bounds_from_pixel_rect,
    robot_bounds_from_quad_clicks,
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
    "compute_tool_center_offset",
    "PolyFit",
    "ToolCenterOffset",
    "WorkZone",
    "auto_select_degree",
    "infer_missing_grid_corner_from_edge_points",
    "intersect_infinite_lines_2d",
    "default_master_workspace",
    "derive_work_zone",
    "detection_center",
    "draw_result_image",
    "fit_inverse_polynomial",
    "fit_polynomial",
    "generate_grid_targets",
    "load_calibration",
    "pixel_to_robot_xy",
    "refined_detection_center",
    "robot_bounds_from_pixel_rect",
    "robot_bounds_from_quad_clicks",
    "save_calibration",
]
