"""`python -m vision.calibration` -> short usage summary."""

from __future__ import annotations

import sys

USAGE = """\
Camera <-> robot calibration package.

Subcommands:
  python -m vision.calibration.ui       --image PATH ...   click-and-confirm calibration
  python -m vision.calibration.demo     --image PATH ...   one-shot stereo-photo demo
  python -m vision.calibration.verify   --pixel U V        map a pixel through saved calibration

Programmatic use:
  from vision.calibration import Calibrator
  cal = Calibrator.load()                              # calibration/calibration.json
  target = cal.transform_detection(yolo_detection)     # -> (X_mm, Y_mm, Z_mm) or None

Documentation:
  CALIBRATION.md      runtime flow, JSON schema, and recalibration policy
  calibration/markers_template.md     how to print and place the marker grid
"""


def main() -> int:
    print(USAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
