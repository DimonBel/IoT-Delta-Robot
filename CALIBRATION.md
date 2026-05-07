# Camera ↔ Robot Calibration

This package maps a **camera image pixel `(u, v)` → robot table coordinate `(X_mm, Y_mm)`** so that detections from the ZED camera can be sent to the Delta robot in its own frame. Z is treated as a fixed pick-height for now.

Calibration is done **once per camera mount**, saved to `calibration/calibration.json`, and reused at runtime.

## Layout

```
vision/calibration/
  __init__.py    public API re-exports
  __main__.py    `python -m vision.calibration` -> usage summary
  core.py        math + IO  (numpy only — no OpenCV)
  draw.py        result-image rendering  (cv2, lazy import)
  runtime.py     ergonomic Calibrator wrapper for the live loop
  ui.py          interactive click-and-confirm UI
  demo.py        one-shot stereo-photo demo with auto green-marker detection
  verify.py      load saved JSON + map a single pixel from the CLI
calibration/
  markers_template.md   how to print and place the marker grid
  calibration.json      (gitignored — generated per machine)
  *.png                 (gitignored — annotated result/debug images)
tests/
  test_calibration.py   unit tests, no camera/robot/cv2 required
```

`vision/vision.py` (the ZED + YOLO pipeline) and the `robot/` and `main/` packages are **not** modified by calibration.

## Quick start

### 1. Unit tests (no hardware, no cv2)

```
python -m unittest tests.test_calibration -v
```

Expected: 20 tests pass.

### 2. Click UI on a static photo (offline)

```
python -m vision.calibration.ui --image samples/top_down.jpg \
    --grid 3x3 --spacing 100 --out calibration/calibration.json
```

Click each marker in row-major order (top-left first). `y` confirms, `n` redoes, `q` quits. Outputs:

- `calibration/calibration.json` — the saved transform.
- `calibration/calibration_result.png` — annotated verification image.

`--live` swaps the input source to a single ZED frame (requires the ZED SDK).

### 3. One-shot demo on the stereo photo

```
python -m vision.calibration.demo --image PATH/TO/stereo_photo.jpg
```

Auto-splits the stereo image, picks the LEFT view, detects bright-green corner markers, fits an affine transform, and writes:

- `calibration/calibration.json`
- `calibration/calibration_result.png` — clicked markers + work-zone outline.
- `calibration/calibration_debug.png` — every detected blob with the chosen four ringed.
- `calibration/calibration_mask.png` — raw HSV mask, useful when tuning the green range.

## Runtime flow (after calibration is saved)

When the camera films live and YOLO detects an object:

```
                vision/vision.py  (ZED + YOLO)
                       │
                       ▼
            detection.bbox_xyxy  ──►  centre pixel (u, v)
                                          │
                                          ▼
                          load_calibration("calibration/calibration.json")
                                          │
                                          ▼
                          calibration.pixel_to_robot_xy(u, v)
                                          │
                                          ▼
                          (X_mm, Y_mm) in robot frame
                                          │
                                          ▼
                          calibration.is_inside_zone(X, Y) ?  ── no ──► skip
                                          │
                                          ▼
                          Z = calibration.pick_height_z_mm
                                          │
                                          ▼
                          robot.move_to(X, Y, Z) → robot.pick()
```

In code, once `RobotController` exists, the glue inside `main.main.automatic_loop()` collapses to a few lines via the `Calibrator` helper:

```python
from vision.calibration import Calibrator

cal = Calibrator.load()                             # once at startup

# per detection in the loop:
target = cal.transform_detection(detection)        # (X, Y, Z) or None
if target is None:
    continue                                        # missing bbox or outside zone
robot.move_to(*target)
robot.pick()
```

`Calibrator.transform_detection` reads `bbox_xyxy` from the detection dict, transforms the bbox centre, rejects out-of-zone points, and returns `(X_mm, Y_mm, Z_mm)` ready for the robot. The lower-level functions (`pixel_to_robot_xy`, `is_inside_zone`) are still exported if you need them.

That integration step is **not** part of this PR — it waits on a real `RobotController`.

### Quick CLI sanity check

```
python -m vision.calibration                       # usage summary
python -m vision.calibration.verify --summary      # show metadata of saved cal
python -m vision.calibration.verify --pixel 320 240
```

## When to recalibrate

- **Camera physically moves** (the cage was nudged, the mount tightened, etc.).
- **Resolution changes** (HD720 ↔ VGA). The JSON stores `image_size` and `pixel_to_robot_xy` raises if a runtime image size is passed that does not match.
- **Markers were repositioned** on the table.

Anything else (different lighting, different fruit, different time of day) does **not** require recalibration.

## What gets committed

- New: `vision/calibration/{__init__,core,draw,ui,demo}.py`, `tests/test_calibration.py`, `calibration/markers_template.md`, this `CALIBRATION.md`.
- Modified: `.gitignore`.
- Ignored: `calibration/calibration.json`, `calibration/*.png`, `tests/photo_*.jpg`.

## Out of scope (future work)

- Z-axis calibration (currently a configured constant).
- Auto chessboard / ArUco detection (manual click + green-corner demo are enough today).
- `RobotController` and live integration with `main/main.py`.
