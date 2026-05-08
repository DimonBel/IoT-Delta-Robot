# Vision Module (ZED2i + YOLO)

This folder contains reusable runtime commands for:
- live ZED2i vision
- one-shot snapshot capture
- offline snapshot inspection

## 1) Turning the camera on (ZED2i): what to install

Follow this order so the camera works in Windows apps first, then in Python.

### 1.1 Hardware

- **Camera**: Stereolabs **ZED 2i** (this repo targets ZED SDK features, not generic USB webcams).
- **USB**: Use a **USB 3.0** (blue) port on the PC; avoid hubs if you see disconnects or “camera busy” errors.
- **GPU (recommended)**: NVIDIA GPU with a driver that matches what the **ZED SDK** you install expects. Depth and object detection are heavy without a decent GPU.

### 1.2 PC software from Stereolabs

1. **NVIDIA GPU driver**  
   Install or update from NVIDIA so CUDA-enabled tools can run.

2. **CUDA** (usually required by the ZED SDK installer)  
   Install the **CUDA toolkit version** that your **ZED SDK release** lists in Stereolabs’ release notes / installer checklist. Mismatch here is a common reason the SDK or samples fail to start.

3. **ZED SDK** (Windows)  
   - Download from [Stereolabs — ZED SDK](https://www.stereolabs.com/developers/release/).  
   - Run the installer; typical install path: `C:\Program Files (x86)\ZED SDK` (may vary).  
   - The SDK ships **ZED Explorer** and other tools—use them to confirm the camera opens before Python.

4. **Optional but useful**  
   - **ZED Explorer**: live left/right, depth sanity check.  
   - **ZED Depth Viewer**: depth visualization.  
   If the camera works here but not in code, the problem is usually Python bindings or PATH, not the device.

### 1.3 Python: versions and virtual environment

- **Supported for ZED Python API**: use **64-bit Python 3.10 or 3.11** in a venv.  
  **Avoid Python 3.13+** for ZED unless Stereolabs documents support for your SDK version; bindings often lag new Python releases.
- Create and activate a venv from the repo root, then install project deps:

```bash
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 1.4 Python libraries used by this vision stack

| Role | Package | Notes |
|------|---------|--------|
| ZED camera | **`pyzed`** | **Not** `pip install pyzed`. Install via Stereolabs script (next step). |
| Arrays / depth helpers | **`numpy`** | In `requirements.txt`. |
| Images / saving snapshots | **`opencv-python`** | In `requirements.txt`. |
| YOLO inference | **`ultralytics`** | In `requirements.txt`; pulls **PyTorch** (`torch`). GPU needs a CUDA build of PyTorch matching your setup. |
| Web stack (rest of repo) | FastAPI, etc. | In `requirements.txt`; not required only to open the camera, but fine to install together. |

### 1.5 Official ZED Python API (`pyzed`)

After the ZED SDK is installed:

1. Run Stereolabs’ installer script **with the same Python** you use for this project (venv activated):

```bash
python "C:\Program Files (x86)\ZED SDK\get_python_api.py"
```

(If your SDK is under `C:\Program Files\ZED SDK`, use that path instead.)

2. Remove wrong packages if someone ran pip by mistake:

```bash
python -m pip uninstall -y pyzed
```

3. Quick check:

```bash
python -c "import pyzed.sl as sl; print('pyzed OK')"
```

This repo also probes common SDK folders on Windows when importing `pyzed.sl`, but the **correct** fix is SDK + `get_python_api.py` for your Python.

### 1.6 Verify the camera before `vision.commands`

1. Open **ZED Explorer** (from the Start menu or SDK bin folder) and confirm a live image.  
2. In your venv, run:

```bash
python -m vision.commands live --duration 5 --model medium
```

If Explorer works but Python fails, recheck Python **bitness** (64-bit), **version** (3.10/3.11), and that `get_python_api.py` was run for **that** interpreter.

## 2) Reusable commands

Run from repository root.

### Live stream

- Command:
  - `python -m vision.commands live --model medium --confidence 40`
- Optional:
  - `--duration 30` (seconds)
  - `--no-display` (headless)
  - `--algorithm yolo` or `--algorithm zed`
  - `--print-coordinates` (re-enable coordinate printing in terminal output)

### Capture one snapshot and save it

- Command:
  - `python -m vision.commands snapshot --output outputs/snapshots/frame_001.jpg --model medium --confidence 40`

### Capture a snapshot dataset (only frames with detected objects)

- Command:
  - `python -m vision.commands snapshot-dataset --output-dir outputs/snapshot_inspection --count 50 --max-frames 600 --model medium --confidence 35`
- Output per sample:
  - `<name>.jpg` (annotated frame)
  - `<name>.json` (detections + frame metadata)

### Inspect existing still images

- Command:
  - `python -m vision.commands inspect --images samples/a.jpg samples/b.jpg --model medium --confidence 35 --json-out outputs/reports/inspection.json`

### Categorize objects in snapshots (good/bad/unclear/person/other_object)

- Command:
  - `python -m vision.commands categorize --images outputs/snapshot_inspection/*.jpg --model medium --confidence 35 --unclear-confidence 45 --crops-dir outputs/snapshot_inspection/crops --json-out outputs/reports/categorization.json`
- Categories:
  - `good`: produce likely acceptable
  - `bad`: produce likely poor quality/spoilage
  - `unclear`: low confidence or unknown produce kind
  - `person`: human detection
  - `other_object`: non-produce objects (robot, board, misc objects)
- Behaviour:
  - When the dataset capture wrote a `<stem>.json` sidecar next to the image, those detections (already vetted by the calibrated work-zone YOLO pass) are used. Pass `--no-sidecar` to force a fresh full-frame inference.
  - `--crops-dir DIR` saves per-detection crops into `DIR/<category>/...jpg` for fast visual review and dataset prep.

## 3) Backward-compatible test wrappers

These wrappers now call reusable command functions:
- `python -m tests.test_vision_live`
- `python -m tests.test_snapshot_inspection --images <paths...>`

## 4) How coordinates are computed

There are two coordinate outputs in the pipeline:

1. **3D camera coordinates (`position_m`)**
   - For each detection, the system tries object position from ZED tracking first.
   - If the returned values are invalid (`NaN`/`Inf`), it falls back to the point cloud at the object foot/center pixel.
   - Distance is computed as Euclidean norm:
     - `distance_m = sqrt(x^2 + y^2 + z^2)`

2. **Board-relative coordinates (`board_map.u`, `board_map.v`)**
   - When a board-like object is detected, its image corners are used to build a homography from image space to normalized board space.
   - For each non-board object, the image foot point is projected by that homography.
   - `u` and `v` are clamped into `[0, 1]`.

### Temporary behavior

Coordinate logic is still active in payload generation and mapping, but terminal coordinate printing is temporarily muted by default in `live` mode.  
Use `--print-coordinates` to display them while this temporary state is in place.

### 4.1 Board-frame millimetres (`board_xy_mm`)

When a saved calibration is loaded (default behaviour of `live`), each detection also gets `board_xy_mm: {x, y, inside_zone}` in millimetres relative to the centre of the calibrated work area. This is independent of `board_map` (which stays in `[0..1]`) and of `position_m` (3D camera frame). See [CALIBRATION.md](../CALIBRATION.md) for the full schema, the `--no-calibration` escape hatch, and how the resolution-mismatch error surfaces. Robot integration consumes this field — that part is intentionally not wired in this PR.
