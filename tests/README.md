# Vision System Tests

This folder contains comprehensive tests for the vision.py module. It includes unit tests, live visual testing, coordinate transmission verification, and diagnostic tools.

## Quick Start - Troubleshooting ZED Camera Issues

If you're getting "Could not initialize ZED camera" errors, run the diagnostic tool first:

```bash
python -m tests.diagnose_zed
```

This will check:
- ✓ ZED SDK installation
- ✓ Python package imports
- ✓ Camera hardware connection
- ✓ Camera firmware
- ✓ USB connectivity

---

## Test Files

### 1. `test_vision_unit.py` - Unit Tests
Tests the core functionality of the ImageRecognition class and helper functions.

**What it tests:**
- Helper function correctness (bbox centers, float conversion, detection records)
- ImageRecognition initialization with/without auto-start
- Frame capture and analysis
- Detection filtering (picking the best detection by confidence)
- Configuration parameter passing

**Run tests:**
```bash
python -m pytest tests/test_vision_unit.py -v
# or
python -m unittest tests.test_vision_unit
```

**Features:**
- No camera/ZED SDK required (uses mocking)
- Fast execution (~1 second)
- Tests ~15 different scenarios

---

### 2. `test_vision_live.py` - Live Visual Testing
Real-time visualization of object detection with live camera footage.

**What it tests:**
- Camera initialization and frame capture
- Real-time object detection
- Coordinate accuracy in real-world conditions
- FPS and performance
- Detection consistency

**Run live test:**
```bash
python -m tests.test_vision_live
```

**Command-line options:**
```bash
# Run for 30 seconds
python -m tests.test_vision_live --duration 30

# Use 'accurate' model instead of 'medium'
python -m tests.test_vision_live --model accurate

# Adjust confidence threshold
python -m tests.test_vision_live --confidence 50

# Run without display (headless mode)
python -m tests.test_vision_live --no-display

# Enable debug output for troubleshooting
python -m tests.test_vision_live --debug

# Combined example
python -m tests.test_vision_live --duration 60 --confidence 30 --model accurate --debug
```

**Output:**
- Live video window showing detections with boxes and labels
- Real-time detection data (coordinates, confidence, distance)
- FPS counter
- Summary statistics at end:
  - Total frames captured
  - Detection rate
  - Average FPS
  - Last detection details

**Controls:**
- Press 'q' to quit
- Ctrl+C to interrupt

**Requirements:**
- ZED camera connected
- ZED SDK installed
- OpenCV (`opencv-python`)

### 3. `test_coordinate_transmission.py` - Coordinate Verification
Tests that coordinates are extracted correctly and transmitted to backend.

**What it tests:**
- Coordinate extraction accuracy
- JSON payload format validation
- Backend communication
- Coordinate consistency across frames

**Run coordinate test:**
```bash
python -m tests.test_coordinate_transmission
```

**Command-line options:**
```bash
# Run for 60 seconds
python -m tests.test_coordinate_transmission --duration 60

# Use specific model
python -m tests.test_coordinate_transmission --model accurate

# Custom backend URL
python -m tests.test_coordinate_transmission --backend-url http://your-server:8765/detect

# Enable debug output
python -m tests.test_coordinate_transmission --debug
```

**Output:**
- Starts built-in test server to capture transmission data
- Validates format of all payloads sent
- Shows coordinate statistics (min/max x, y, z)
- Reports detection accuracy

**Features:**
- Built-in HTTP server for testing (no external server needed)
- Validates JSON structure
- Checks coordinate ranges and types
- Analyzes coordinate consistency

**Requirements:**
- ZED camera connected
- ZED SDK installed

---

### 4. `diagnose_zed.py` - Diagnostic Tool

Complete diagnostic tool to verify ZED SDK installation and camera connectivity.

**What it checks:**
- ✓ Python package imports (cv2, numpy, pyzed.sl)
- ✓ ZED SDK version
- ✓ Camera hardware detection
- ✓ Camera connection status
- ✓ Frame capture capability
- ✓ Camera firmware

**Run diagnostics:**
```bash
python -m tests.diagnose_zed
```

**Output:**
Detailed step-by-step report showing:
- Which packages are installed
- Whether camera is connected
- Camera model and specifications
- What's failing (with solutions)

**Use when:**
- Getting "Could not initialize ZED camera" errors
- Camera was working but now isn't
- After installing/updating ZED SDK
- Troubleshooting connection issues

---

## Running All Tests

### Quick Test (No Camera)
```bash
# Run unit tests only (no hardware needed)
python -m pytest tests/test_vision_unit.py -v
```

### Full Integration Test with Diagnostics
```bash
# 1. Check that everything is installed and working
python -m tests.diagnose_zed

# 2. Unit tests
python -m pytest tests/test_vision_unit.py -v

# 3. Live visual test (30 seconds)
python -m tests.test_vision_live --duration 30

# 4. Coordinate transmission test (30 seconds)
python -m tests.test_coordinate_transmission --duration 30
```

---

## Troubleshooting

### "ERROR: Could not initialize ZED camera"

**First step - run diagnostics:**
```bash
python -m tests.diagnose_zed
```

This will tell you exactly what's wrong. Common fixes:

**If import fails:**
```bash
# Reinstall ZED SDK from: https://www.stereolabs.com/developers/release/
# After installation, run:
cd /path/to/ZED_SDK/build
python -m pip install .
```

**If camera connection fails:**
- Ensure ZED camera is connected to USB 3.0+ port
- Try a different USB port
- Check USB cable is not damaged
- Restart the computer
- Unplug any other USB devices to free up bandwidth
- Update camera firmware from https://www.stereolabs.com/developers/

**If you get permission errors (Linux):**
```bash
sudo usermod -a -G video $USER
sudo reboot
```

### "ModuleNotFoundError: No module named 'cv2'"
```bash
pip install opencv-python
```

### Camera was working but now shows import errors
- Restart your Python environment
- Try: `python -m tests.diagnose_zed --verbose`
- Check if ZED SDK had an update that broke compatibility

### No detections appearing in live test
- Lower confidence threshold: `--confidence 20`
- Try different model: `--model fast` or `--model accurate`
- Ensure good lighting conditions
- Make sure objects are in view and at reasonable distance

### Backend test shows no payloads received
- Ensure backend_url is correct
- Check if firewall is blocking localhost:8765
- Verify vision system is actually detecting objects
- Run live test first to confirm detections are working

---

## Test Results Interpretation

### Live Test Summary
```
Total frames captured: 300
Frames with detections: 285
Detection rate: 95.0%
Average FPS: 15.2
```
- **Detection rate > 80%**: Good ✓
- **Detection rate 50-80%**: Objects may not always be visible
- **Detection rate < 50%**: Might need to adjust confidence or model

### Coordinate Test
```
Coordinate Statistics:
  X: min=-0.50, max=2.50
  Y: min=-1.00, max=1.00
  Z: min=0.30, max=3.50
```
- Coordinates should be **consistent** across frames
- **X, Y range**: Depends on camera position
- **Z range**: Depth (distance from camera)
- Watch for **sudden jumps** in coordinates (indicates noise)

---

## Next Steps

After confirming tests pass:
1. Integrate with robot controller (robot.py)
2. Test automated picking sequence
3. Verify coordinate system alignment with robot
4. Fine-tune detection model and confidence for your use case
