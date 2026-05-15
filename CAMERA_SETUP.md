# Camera Setup — ZED 2i on Windows

Complete install checklist. Follow the steps **in order** — each step depends on the previous one being correct.

---

## 1. Hardware

| What | Requirement |
|------|-------------|
| Camera | Stereolabs **ZED 2i** |
| USB port | **USB 3.0** (blue port, directly on the motherboard — no hubs) |
| GPU | NVIDIA GPU (GTX 10xx or newer recommended for depth + YOLO) |

---

## 2. NVIDIA GPU Driver

Install or update your GPU driver from [nvidia.com/drivers](https://www.nvidia.com/drivers).  
The driver version must be high enough to support the CUDA version the ZED SDK requires (see step 3).

**Check your current driver:**
```
nvidia-smi
```

---

## 3. CUDA Toolkit

The ZED SDK requires a specific CUDA version. Check the [Stereolabs release page](https://www.stereolabs.com/developers/release/) before installing — the installer page lists the required CUDA version for each SDK release.

Download and install from: [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads)

**Check installed CUDA version:**
```
nvcc --version
```

---

## 4. ZED SDK (Windows installer)

1. Download the installer from: [stereolabs.com/developers/release](https://www.stereolabs.com/developers/release/)
2. Run the `.exe` installer (requires admin).  
   Default install path: `C:\Program Files (x86)\ZED SDK`
3. During install, choose **all components** (SDK + tools + Python wrapper option if shown).

**Verify the SDK works before touching Python:**

- Open **ZED Explorer** from the Start menu.
- You should see a live stereo image from the camera.
- If ZED Explorer fails, fix the SDK/driver first — no Python fix will help.

---

## 5. Python Version

| | Requirement |
|-|-------------|
| Version | **Python 3.10 or 3.11**, 64-bit |
| Avoid | Python 3.12, 3.13 — ZED Python bindings often do not support new releases yet |
| Bitness | Must be **64-bit** (32-bit will fail silently when loading pyzed) |

Check your Python:
```
python --version
python -c "import struct; print(struct.calcsize('P')*8, 'bit')"
```

---

## 6. Virtual Environment

Create and activate a venv from the **repository root**:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell / cmd
```

Upgrade pip first:
```bash
python -m pip install --upgrade pip
```

---

## 7. Python Packages (pip)

Install project dependencies (numpy, opencv-python, ultralytics, FastAPI, etc.):

```bash
pip install -r requirements.txt
```

Key packages this installs relevant to the camera pipeline:

| Package | Why it is needed |
|---------|-----------------|
| `numpy` | Array operations, depth data, calibration math |
| `opencv-python` | Image display, calibration UI, snapshot saving |
| `ultralytics` | YOLO inference (pulls in `torch`) |

> **PyTorch + CUDA:** `ultralytics` pulls in a CPU-only `torch` by default.  
> For GPU inference (strongly recommended for real-time use), install the CUDA build manually **after** `requirements.txt`:
>
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```
>
> Replace `cu121` with the CUDA version you installed in step 3 (e.g. `cu118`, `cu124`).  
> Check available builds at [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/).

---

## 8. ZED Python API (`pyzed`) — CRITICAL

**Do NOT run `pip install pyzed`.** That installs a stub that does not work.

The real `pyzed` is installed by the ZED SDK via a Stereolabs script. With your venv **activated**:

```bash
python "C:\Program Files (x86)\ZED SDK\get_python_api.py"
```

> If the SDK was installed to `C:\Program Files\ZED SDK` (without `(x86)`), adjust the path accordingly.  
> The script detects your Python version and installs the matching `.whl` directly.

If you accidentally installed the stub, remove it first:
```bash
pip uninstall -y pyzed
```
Then re-run `get_python_api.py`.

**Quick check:**
```bash
python -c "import pyzed.sl as sl; print('pyzed OK, SDK version:', sl.Camera().get_sdk_version())"
```

---

## 9. Verification — Full Stack

Run these in order. Fix any failure before moving to the next line.

```bash
# 1. pyzed import
python -c "import pyzed.sl as sl; print('pyzed OK')"

# 2. OpenCV import
python -c "import cv2; print('cv2', cv2.__version__)"

# 3. YOLO / ultralytics import
python -c "from ultralytics import YOLO; print('ultralytics OK')"

# 4. Calibration unit tests (no camera needed)
python -m unittest tests.test_calibration -v

# 5. ZED camera live (opens a window — press Q to quit)
python -m vision.commands live --duration 10 --model medium

# 6. ZED SDK diagnostics (run if step 5 fails)
python -m tests.diagnose_zed
```

---

## 10. Common Errors

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `ModuleNotFoundError: No module named 'pyzed'` | `get_python_api.py` not run for this venv | Re-run with venv active (step 8) |
| `pyzed` imports but camera fails to open | Wrong Python bitness or ZED SDK not installed | Check 64-bit Python (step 5), reinstall SDK (step 4) |
| YOLO runs on CPU only, very slow | CPU-only `torch` installed | Install CUDA build of torch (step 7) |
| `cuda driver version is insufficient` | GPU driver too old for your CUDA | Update driver (step 2) |
| ZED Explorer works, Python fails | Python version mismatch (3.12+) or 32-bit Python | Switch to Python 3.10/3.11 64-bit |
| `cv2.error` during calibration UI | `opencv-python` not installed in active venv | `pip install opencv-python` |
