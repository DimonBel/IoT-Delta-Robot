"""Sanity-check a saved calibration without OpenCV or the camera.

Loads `calibration/calibration.json` (or any path), maps a single pixel
through the saved transform, and prints the resulting robot XY plus the
work-zone verdict. Useful when you want to confirm a calibration is still
loadable and producing reasonable numbers.

Usage:
    python -m vision.calibration.verify --pixel 320 240
    python -m vision.calibration.verify --pixel 100 50 --calibration path/to/cal.json
    python -m vision.calibration.verify --summary
"""

from __future__ import annotations

import argparse
import sys

from .runtime import Calibrator


def _print_summary(cal: Calibrator) -> None:
    c = cal.calibration
    z = c.effective_active_zone()
    m = c.master_workspace
    print(f"calibration: {c.notes or '(no notes)'}")
    print(f"  created_at        : {c.created_at}")
    print(f"  image_size        : {c.image_size[0]} x {c.image_size[1]}")
    print(f"  fit               : poly{c.fit.degree}  RMS {c.fit.rms_residual_mm:.2f} mm")
    print(f"  N points          : {len(c.points)}")
    print(
        f"  master workspace  : X[{m.x_min:.0f}, {m.x_max:.0f}]  "
        f"Y[{m.y_min:.0f}, {m.y_max:.0f}]"
    )
    print(f"  work_zone (mm)    : X[{c.work_zone.x_min:.0f}, {c.work_zone.x_max:.0f}]  "
          f"Y[{c.work_zone.y_min:.0f}, {c.work_zone.y_max:.0f}]")
    print(f"  active zone (mm)  : X[{z.x_min:.0f}, {z.x_max:.0f}]  "
          f"Y[{z.y_min:.0f}, {z.y_max:.0f}]")
    print(f"  tool offset       : X{c.tool_center_offset.x_mm:+.2f}  "
          f"Y{c.tool_center_offset.y_mm:+.2f} mm")
    print(f"  pick height Z     : {c.pick_height_z_mm:.0f} mm")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--calibration",
        default=Calibrator.DEFAULT_PATH,
        help=f"Calibration JSON path (default {Calibrator.DEFAULT_PATH})",
    )
    p.add_argument(
        "--pixel",
        nargs=2,
        type=float,
        metavar=("U", "V"),
        help="Image pixel to map through the calibration",
    )
    p.add_argument(
        "--summary",
        action="store_true",
        help="Print the calibration metadata only",
    )
    args = p.parse_args(argv)

    try:
        cal = Calibrator.load(args.calibration)
    except FileNotFoundError:
        print(f"ERROR: calibration not found at {args.calibration}", file=sys.stderr)
        print("Run `python -m vision.calibration.ui --image PATH ...` first.")
        return 2

    _print_summary(cal)

    if args.pixel is not None:
        u, v = args.pixel
        x_mm, y_mm = cal.transform_pixel(u, v)
        inside = cal.is_inside_zone(x_mm, y_mm)
        print()
        print(f"pixel ({u:.0f}, {v:.0f}) -> robot ({x_mm:+.2f}, {y_mm:+.2f}) mm")
        print(f"  inside work zone: {inside}")
        print(f"  would target Z  : {cal.pick_height_z_mm:.0f} mm")
        return 0 if inside else 1

    if not args.summary:
        print()
        print("Tip: pass --pixel U V to map a specific pixel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
