"""Math + IO for the pixel -> robot table transform.

Maps camera image pixel (u, v) to robot table coordinate (X_mm, Y_mm) using a
bivariate polynomial fit over N hand-placed marker points. Z is treated as a
fixed pick-height (configured separately).

Pure stdlib + numpy. The interactive click UI lives in vision.calibration.ui
and the result-image rendering lives in vision.calibration.draw.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np


SCHEMA_VERSION = 2
DEFAULT_PICK_HEIGHT_MM = -940.0

# Hardware safe limits from robot/robot_tests/POSITION.md
HARDWARE_LIMITS = {
	"x_min": -280.0,
	"x_max": 280.0,
	"y_min": -280.0,
	"y_max": 280.0,
}


@dataclass(frozen=True)
class CalibrationPoint:
	u: float
	v: float
	x_mm: float
	y_mm: float


@dataclass
class ToolCenterOffset:
	x_mm: float = 0.0
	y_mm: float = 0.0
	source: str = "manual_gripper_reference_point"

	def to_dict(self) -> dict:
		return {
			"x_mm": self.x_mm,
			"y_mm": self.y_mm,
			"source": self.source,
		}

	@classmethod
	def from_dict(cls, d: dict | None) -> "ToolCenterOffset":
		data = d or {}
		return cls(
			x_mm=float(data.get("x_mm", 0.0)),
			y_mm=float(data.get("y_mm", 0.0)),
			source=str(data.get("source", "manual_gripper_reference_point")),
		)


@dataclass
class WorkZone:
	x_min: float
	x_max: float
	y_min: float
	y_max: float

	def contains(self, x: float, y: float) -> bool:
		return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

	def to_dict(self) -> dict:
		return {
			"x_min": self.x_min,
			"x_max": self.x_max,
			"y_min": self.y_min,
			"y_max": self.y_max,
		}


@dataclass
class PolyFit:
	"""Bivariate polynomial fit (degree 1, 2 or 3) for X and Y independently."""

	degree: int
	coeffs_x: np.ndarray
	coeffs_y: np.ndarray
	rms_residual_mm: float

	def apply(self, u: float, v: float) -> tuple[float, float]:
		row = _design_row(u, v, self.degree)
		x = float(row @ self.coeffs_x)
		y = float(row @ self.coeffs_y)
		return x, y

	def to_dict(self) -> dict:
		return {
			"type": f"poly{self.degree}",
			"coeffs_x": self.coeffs_x.tolist(),
			"coeffs_y": self.coeffs_y.tolist(),
			"rms_residual_mm": self.rms_residual_mm,
		}

	@classmethod
	def from_dict(cls, d: dict) -> "PolyFit":
		type_str = d["type"]
		if not type_str.startswith("poly"):
			raise ValueError(f"Unsupported fit type: {type_str}")
		degree = int(type_str[len("poly"):])
		coeffs_x = np.asarray(d["coeffs_x"], dtype=float)
		coeffs_y = np.asarray(d["coeffs_y"], dtype=float)
		expected = _num_terms(degree)
		if coeffs_x.shape != (expected,) or coeffs_y.shape != (expected,):
			raise ValueError(
				f"Coeff shape mismatch for {type_str}: "
				f"expected {expected}, got {coeffs_x.shape}/{coeffs_y.shape}"
			)
		return cls(
			degree=degree,
			coeffs_x=coeffs_x,
			coeffs_y=coeffs_y,
			rms_residual_mm=float(d["rms_residual_mm"]),
		)


@dataclass
class Calibration:
	image_size: tuple[int, int]  # (W, H)
	fit: PolyFit
	points: list[CalibrationPoint]
	work_zone: WorkZone
	active_zone: WorkZone | None = None
	tool_center_offset: ToolCenterOffset = field(default_factory=ToolCenterOffset)
	pick_height_z_mm: float = DEFAULT_PICK_HEIGHT_MM
	notes: str = ""
	created_at: str = field(
		default_factory=lambda: _dt.datetime.now(_dt.timezone.utc)
		.replace(microsecond=0)
		.isoformat()
		.replace("+00:00", "Z")
	)

	def effective_active_zone(self) -> WorkZone:
		return self.active_zone or self.work_zone

	def pixel_to_robot_xy(self, u: float, v: float) -> tuple[float, float]:
		return self.fit.apply(u, v)

	def apply_tool_center_offset(self, x_mm: float, y_mm: float) -> tuple[float, float]:
		return (
			x_mm - self.tool_center_offset.x_mm,
			y_mm - self.tool_center_offset.y_mm,
		)

	def is_inside_zone(self, x: float, y: float) -> bool:
		return self.effective_active_zone().contains(x, y)

	def to_dict(self) -> dict:
		return {
			"schema_version": SCHEMA_VERSION,
			"image_size": [int(self.image_size[0]), int(self.image_size[1])],
			"fit": self.fit.to_dict(),
			"calibration_points": [
				{"u": p.u, "v": p.v, "X_mm": p.x_mm, "Y_mm": p.y_mm}
				for p in self.points
			],
			"work_zone": self.work_zone.to_dict(),
			"active_zone": self.effective_active_zone().to_dict(),
			"tool_center_offset": self.tool_center_offset.to_dict(),
			"pick_height_z_mm": self.pick_height_z_mm,
			"created_at": self.created_at,
			"notes": self.notes,
		}

	@classmethod
	def from_dict(cls, d: dict) -> "Calibration":
		version = d.get("schema_version", 1)
		if version not in (1, SCHEMA_VERSION):
			raise ValueError(
				f"Unsupported calibration schema_version {version}; "
				f"expected 1 or {SCHEMA_VERSION}"
			)
		size = d["image_size"]
		points = [
			CalibrationPoint(
				u=float(p["u"]),
				v=float(p["v"]),
				x_mm=float(p["X_mm"]),
				y_mm=float(p["Y_mm"]),
			)
			for p in d["calibration_points"]
		]
		zone = WorkZone(**d["work_zone"])
		active_zone_data = d.get("active_zone")
		active_zone = WorkZone(**active_zone_data) if active_zone_data else zone
		return cls(
			image_size=(int(size[0]), int(size[1])),
			fit=PolyFit.from_dict(d["fit"]),
			points=points,
			work_zone=zone,
			active_zone=active_zone,
			tool_center_offset=ToolCenterOffset.from_dict(d.get("tool_center_offset")),
			pick_height_z_mm=float(d.get("pick_height_z_mm", DEFAULT_PICK_HEIGHT_MM)),
			notes=str(d.get("notes", "")),
			created_at=str(d.get("created_at", "")),
		)


# ----- polynomial fit -----

def _num_terms(degree: int) -> int:
	return (degree + 1) * (degree + 2) // 2


def _design_row(u: float, v: float, degree: int) -> np.ndarray:
	# Lexicographic bivariate monomials, total degree first, then power of u
	# descending (u-major within each degree):
	#   deg 0:  1
	#   deg 1:  u, v
	#   deg 2:  u^2, u*v, v^2
	#   deg 3:  u^3, u^2*v, u*v^2, v^3
	terms: list[float] = []
	for total in range(degree + 1):
		for j in range(total + 1):
			i = total - j
			terms.append((u ** i) * (v ** j))
	return np.asarray(terms, dtype=float)


def _design_matrix(uv: np.ndarray, degree: int) -> np.ndarray:
	rows = [_design_row(float(u), float(v), degree) for u, v in uv]
	return np.vstack(rows)


def fit_polynomial(points: Sequence[CalibrationPoint], degree: int = 2) -> PolyFit:
	"""Least-squares fit a bivariate polynomial of given total degree.

	With degree=2 there are 6 unknowns per output dimension; N>=6 is required,
	N>=9 is recommended for robustness against click noise.
	"""
	if degree not in (1, 2, 3):
		raise ValueError("degree must be 1, 2, or 3")

	n = len(points)
	needed = _num_terms(degree)
	if n < needed:
		raise ValueError(
			f"Need at least {needed} points for poly degree {degree}, got {n}"
		)

	uv = np.array([[p.u, p.v] for p in points], dtype=float)
	xs = np.array([p.x_mm for p in points], dtype=float)
	ys = np.array([p.y_mm for p in points], dtype=float)

	A = _design_matrix(uv, degree)
	coeffs_x, *_ = np.linalg.lstsq(A, xs, rcond=None)
	coeffs_y, *_ = np.linalg.lstsq(A, ys, rcond=None)

	pred_x = A @ coeffs_x
	pred_y = A @ coeffs_y
	err_sq = (pred_x - xs) ** 2 + (pred_y - ys) ** 2
	rms = float(math.sqrt(np.mean(err_sq))) if n > 0 else 0.0

	return PolyFit(
		degree=degree,
		coeffs_x=coeffs_x,
		coeffs_y=coeffs_y,
		rms_residual_mm=rms,
	)


def auto_select_degree(n_points: int) -> int:
	# Keep the fit solvable for small click sets:
	#   poly1 needs 3 terms, poly2 needs 6, poly3 needs 10.
	if n_points < 6:
		return 1
	if n_points >= 16:
		return 3
	return 2


# ----- work zone -----

def derive_work_zone(
	points: Iterable[CalibrationPoint],
	margin_mm: float = 20.0,
	hardware_limits: dict | None = None,
) -> WorkZone:
	"""Axis-aligned rect inscribed in the calibrated points, inset by margin,
	intersected with the robot's hardware limits."""
	pts = list(points)
	if not pts:
		raise ValueError("derive_work_zone needs at least one point")

	xs = [p.x_mm for p in pts]
	ys = [p.y_mm for p in pts]
	x_min, x_max = min(xs) + margin_mm, max(xs) - margin_mm
	y_min, y_max = min(ys) + margin_mm, max(ys) - margin_mm

	limits = hardware_limits or HARDWARE_LIMITS
	x_min = max(x_min, limits["x_min"])
	x_max = min(x_max, limits["x_max"])
	y_min = max(y_min, limits["y_min"])
	y_max = min(y_max, limits["y_max"])

	if x_min >= x_max or y_min >= y_max:
		raise ValueError(
			"Derived work zone is empty after applying margin and hardware limits. "
			"Place markers wider apart or reduce the margin."
		)

	return WorkZone(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)


# ----- IO -----

def save_calibration(path: str, calibration: Calibration) -> None:
	os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(calibration.to_dict(), f, indent=2)


def load_calibration(path: str) -> Calibration:
	with open(path, "r", encoding="utf-8") as f:
		data = json.load(f)
	return Calibration.from_dict(data)


# ----- helpers for grid generation -----

def generate_grid_targets(
	rows: int,
	cols: int,
	spacing_mm: float,
	center_x_mm: float = 0.0,
	center_y_mm: float = 0.0,
) -> list[tuple[float, float]]:
	"""Build a list of (X_mm, Y_mm) target positions for a printed grid.

	Origin (0, 0) is the centre of the grid; spacing_mm is the distance between
	adjacent markers. Useful for the click UI to pre-fill the known coordinates
	the operator must click."""
	if rows < 1 or cols < 1:
		raise ValueError("rows and cols must be >= 1")

	targets: list[tuple[float, float]] = []
	half_w = (cols - 1) * spacing_mm / 2.0
	half_h = (rows - 1) * spacing_mm / 2.0
	for r in range(rows):
		for c in range(cols):
			x = center_x_mm - half_w + c * spacing_mm
			y = center_y_mm - half_h + r * spacing_mm
			targets.append((x, y))
	return targets


# ----- runtime convenience -----

def pixel_to_robot_xy(
	calibration: Calibration,
	u: float,
	v: float,
	image_size: tuple[int, int] | None = None,
) -> tuple[float, float]:
	"""Apply the saved transform. If image_size is given and differs from the
	calibrated size, raise so the caller knows to recalibrate."""
	if image_size is not None and tuple(image_size) != tuple(calibration.image_size):
		raise ValueError(
			f"Image size mismatch: calibration is for {calibration.image_size}, "
			f"got {image_size}. Recalibrate at the new resolution."
		)
	return calibration.pixel_to_robot_xy(u, v)