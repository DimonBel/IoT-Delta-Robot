# Camera ↔ Robot Calibration

1/6  Corner at (-X, -Y)
2/6  Corner at (-X, +Y)
3/6  Corner at (+X, -Y)
4/6  Helper on the +X edge (between (+X,-Y) and hidden (+X,+Y))
5/6  Helper on the +Y edge (between (-X,+Y) and hidden (+X,+Y))
6/6  ROBOT HOME (gripper position; mm given by --home-x / --home-y)



Maps a **camera image pixel `(u, v)`** to a **robot table coordinate `(X_mm, Y_mm)`** so detections from the ZED can be sent to the Delta robot in its own frame. Z is a fixed pick-height (configured, not calibrated).

Calibration is **once per camera mount**: print a marker grid, run one command, click each marker. Save → reuse.

## Layout

```
vision/calibration/
  __init__.py    public API re-exports
  __main__.py    `python -m vision.calibration` → usage summary
  core.py        math + IO (numpy only — no OpenCV)
  draw.py        annotated result image (cv2, lazy import)
  runtime.py     Calibrator wrapper for the live loop
  ui.py          interactive click UI
  verify.py      CLI sanity-check
calibration/
  markers_template.md   how to print and place the marker grid
  calibration.json      (gitignored — generated per machine)
  *.png                 (gitignored — annotated result images)
tests/
  test_calibration.py   unit tests, no camera/robot/cv2 required
```

`vision/vision.py` (the ZED + YOLO pipeline) and the `robot/` and `main/` packages are not modified by calibration.

## Quick start — 6 clicks, that's it

You need one printed square on the work board (any visible, well-defined square). You also need to know the side length in mm, and you need to know the robot XY of one reference point inside the square (the "home" — wherever the gripper sits when you call it home; can be off-centre).

1. **Print / tape a square** of known side length on the work board (default `--side 200` mm). Three of its corners must be visible in the camera; the fourth can be off-screen or occluded.
2. **Park the robot at home** so you can see where the gripper tip lands in the image.
3. **Run**:
   ```
   python -m vision.calibration.ui --live --side 200 --home-x 0 --home-y 0
   ```
4. **Click 6 points** in this order. Labels are in the **robot frame** (the axes your robot controller reports), NOT image-space "top/bottom":
   1. Corner at **(−X, −Y)**.
   2. Corner at **(−X, +Y)**.
   3. Corner at **(+X, −Y)**.
   4. Any point on the **+X edge** (between (+X, −Y) and the hidden (+X, +Y)).
   5. Any point on the **+Y edge** (between (−X, +Y) and the hidden (+X, +Y)).
   6. The robot **HOME** position (where the gripper sits).
5. Press **Y / Enter / Space** to confirm each click, **N** to redo, **Q / Esc** to abort.
6. **Done.** `calibration/calibration.json` is written + `calibration/calibration_result.png` for eyeballing.

The hidden 4th corner — always the one at **(+X, +Y)** — is inferred by intersecting the lines `((+X,−Y), +X-helper)` and `((−X,+Y), +Y-helper)`. The square is treated as centred at the robot origin (0, 0), so corners sit at `(±side/2, ±side/2)` in robot mm. The home click is one extra labelled data point at the user-supplied `(--home-x, --home-y)` mm. **Orient the printed square so the corner you can't see is the one at (+X, +Y) in your robot frame.**

Static-photo mode (no camera):
```
python -m vision.calibration.ui --image samples/board.jpg --side 200 --home-x 0 --home-y 0
```

That's the whole calibration. There's no "slave grid", no "active zone", no "tool-centre wizard" — just six clicks.

## JSON schema (v2)

```json
{
  "schema_version": 2,
  "image_size": [W, H],
  "fit": {
    "type": "poly2",
    "coeffs_x": [a0, a1, a2, a3, a4, a5],
    "coeffs_y": [b0, b1, b2, b3, b4, b5],
    "rms_residual_mm": 1.8
  },
  "calibration_points": [
    { "u": 312, "v": 248, "X_mm": -100, "Y_mm": -100 }
  ],
  "work_zone": { "x_min": -180, "x_max": 180, "y_min": -180, "y_max": 180 },
  "robot_home_mm": { "x": 0.0, "y": 0.0 },
  "pick_height_z_mm": -940,
  "created_at": "2026-05-15T12:34:56Z",
  "notes": ""
}
```

**Old v1 JSONs are refused.** If you have one, the next live run will print a clear "please re-run calibration" error. Re-running step 3 above regenerates the file in v2.

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--image PATH` / `--live` | (mutex, required) | Source of the frame. |
| `--live-preview` | off | Live window to aim before grabbing (live only). |
| `--live-warmup-frames N` | 5 | Discard N frames before grabbing (live, no preview). |
| `--save-camera-frame PATH` | off | Save the captured frame for the record. |
| `--side FLOAT` | 200 | Side length of the printed square in mm. |
| `--home-x FLOAT` | 0 | Robot X of the home pixel (mm). |
| `--home-y FLOAT` | 0 | Robot Y of the home pixel (mm). |
| `--out PATH` | `calibration/calibration.json` | Saved JSON. |
| `--pick-height-z FLOAT` | -940 | Robot Z used at runtime. |
| `--degree {1,2,3}` | auto | Polynomial degree override (default: 1, the 5 points pick an affine fit). |
| `--result-image PATH` | (next to --out) | Annotated PNG; `""` disables. |
| `--notes STR` | "" | Free-text note in JSON. |

## Runtime flow (live loop)

Saved calibration is loaded **once** at startup, then each detection gets a `board_xy_mm: {x, y, inside_zone}` field:

```python
from vision.calibration import Calibrator

cal = Calibrator.load()                             # once at startup

# per detection in the loop:
target = cal.transform_detection(detection)        # (X_mm, Y_mm, Z_mm) or None
if target is None:
    continue                                        # missing bbox or outside zone
robot.move_to(*target)
robot.pick()
```

`Calibrator.transform_detection` returns `None` when the bbox is missing or the predicted point falls outside the saved work zone. Robot-side picks up `board_xy_mm.x` / `.y` straight off the detection — that wiring is intentionally not part of this package.

### Quick CLI sanity check

```
python -m vision.calibration                       # usage summary
python -m vision.calibration.verify --summary      # metadata of saved cal
python -m vision.calibration.verify --pixel 320 240
```

## Live integration (camera side)

`python -m vision.commands live` loads the saved calibration and annotates every detection with **board-frame mm**:

```json
"board_xy_mm": {"x": 12.3, "y": -45.0, "inside_zone": true}
```

Edge cases handled in-place:

- **No bbox on a detection** → `board_xy_mm: {"x": null, "y": null, "inside_zone": false}`.
- **Image size mismatch** (live frame vs calibrated resolution) → adds `"error": "image_size_mismatch"`. Recalibrate at the new resolution.
- **Missing calibration JSON** → clean error, prompts you to run the calibration UI; or pass `--no-calibration` to run uncalibrated.

## When to recalibrate

- The camera physically moves.
- Resolution changes (HD720 ↔ VGA). `image_size` is stored; runtime raises on mismatch.
- Markers were repositioned on the table.

Lighting, different fruit, different time of day do **not** require recalibration.

## Related: live quality grading, ID tracking, detection-range flags

Each produce detection in `live` also carries a fuzzy `quality` field and a stable `track_id` from a centroid tracker in board mm. Output files land in `outputs/` (gitignored): `latest_tracks.json` (overwritten every 10 frames by default) and `track_events.jsonl` (append-only audit). Live defaults (`--confidence 25`, `--imgsz 832`, `--person-min-confidence 40`) and the `--enhance / --no-quality / --no-tracking / --tracker-*` flags are documented in [vision/README.md §4.2 / §4.3 / §4.4](vision/README.md).
