"""Sanity-check a saved calibration without OpenCV or the camera.

Loads `calibration/calibration.json` (or any path), maps a single pixel
through the saved transform, and prints the resulting robot XY plus the
work-zone verdict. Useful when you want to confirm a calibration is still
loadable and producing reasonable numbers.

Usage:
    python -m vision.calibration.verify --pixel 320 240
    python -m vision.calibration.verify --pixel 100 50 --calibration path/to/cal.json
    python -m vision.calibration.verify --summary
    python -m vision.calibration.verify --retune
"""

from __future__ import annotations

import argparse
import math
import sys

from .core import HomographyFit, fit_homography, save_calibration
from .runtime import Calibrator


def _print_summary(cal: Calibrator) -> None:
    c = cal.calibration
    z = c.work_zone
    home = c.robot_home_mm
    print(f"calibration: {c.notes or '(no notes)'}")
    print(f"  created_at      : {c.created_at}")
    print(f"  image_size      : {c.image_size[0]} x {c.image_size[1]}")
    fit_label = "homography" if isinstance(c.fit, HomographyFit) else f"poly{c.fit.degree}"
    tps_tag = ""
    if isinstance(c.fit, HomographyFit) and c.fit.tps_src is not None:
        tps_tag = " + TPS"
    print(f"  fit             : {fit_label}{tps_tag}  RMS {c.fit.rms_residual_mm:.2f} mm")
    print(f"  N points        : {len(c.points)}")
    print(
        f"  work zone (mm)  : X[{z.x_min:.0f}, {z.x_max:.0f}]  "
        f"Y[{z.y_min:.0f}, {z.y_max:.0f}]"
    )
    print(f"  robot home (mm) : X={home[0]:+.1f}  Y={home[1]:+.1f}")
    print(f"  pick height Z   : {c.pick_height_z_mm:.0f} mm")


def _print_residuals(cal: Calibrator) -> None:
    """Print per-point prediction error for every stored calibration point."""
    c = cal.calibration
    print("\nPer-point residuals:")
    print(f"  {'#':>3}  {'robot target':>18}  {'predicted':>18}  {'err X':>7}  {'err Y':>7}  {'|err|':>7}")
    worst = 0.0
    for i, pt in enumerate(c.points):
        px, py = c.fit.apply(pt.u, pt.v)
        dx = pt.x_mm - px
        dy = pt.y_mm - py
        err = math.sqrt(dx * dx + dy * dy)
        worst = max(worst, err)
        print(f"  {i+1:>3}  ({pt.x_mm:+8.1f},{pt.y_mm:+8.1f})  "
              f"({px:+8.1f},{py:+8.1f})  {dx:+7.1f}  {dy:+7.1f}  {err:7.1f} mm")
    print(f"  worst: {worst:.1f} mm")


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
    p.add_argument(
        "--residuals",
        action="store_true",
        help="Print per-point prediction error for every stored calibration point",
    )
    p.add_argument(
        "--retune",
        action="store_true",
        help=(
            "Refit the TPS correction from stored calibration points and save "
            "back to the JSON.  Improves accuracy without re-clicking."
        ),
    )
    args = p.parse_args(argv)

    try:
        cal = Calibrator.load(args.calibration)
    except FileNotFoundError:
        print(f"ERROR: calibration not found at {args.calibration}", file=sys.stderr)
        print("Run `python -m vision.calibration.ui --image PATH ...` first.")
        return 2

    _print_summary(cal)

    if args.retune:
        c = cal.calibration
        if not isinstance(c.fit, HomographyFit):
            print("ERROR: --retune only works with homography calibrations.", file=sys.stderr)
            return 2
        if not c.points:
            print("ERROR: no stored calibration points to retune from.", file=sys.stderr)
            return 2

        print(f"\nRetuning from {len(c.points)} stored points ...")
        print("\nBefore TPS:")
        _print_residuals(cal)

        new_fit = fit_homography(c.points, verbose=False)
        c.fit = new_fit
        save_calibration(args.calibration, c)

        print("\nAfter TPS (errors driven to ~0 at calibration points):")
        _print_residuals(cal)
        print(f"\nSaved updated calibration to {args.calibration}")
        return 0

    if args.residuals:
        _print_residuals(cal)

    if args.pixel is not None:
        u, v = args.pixel
        x_mm, y_mm = cal.transform_pixel(u, v)
        inside = cal.is_inside_zone(x_mm, y_mm)
        print()
        print(f"pixel ({u:.0f}, {v:.0f}) -> robot ({x_mm:+.2f}, {y_mm:+.2f}) mm")
        print(f"  inside work zone: {inside}")
        print(f"  would target Z  : {cal.pick_height_z_mm:.0f} mm")
        return 0 if inside else 1

    if not args.summary and not args.residuals and not args.retune:
        print()
        print("Tip: pass --pixel U V  |  --residuals  |  --retune")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
