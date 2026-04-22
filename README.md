## IoT Delta Robot

***

## Vision Coordinates & YOLO Object Detection Logic

The vision module uses the ZED SDK (3D depth mapping) combined with an Ultralytics YOLOv8 backend for advanced object recognition, particularly focused on fresh produce sorting.

### Core Capabilities:

- **AI Object Detection**: Uses YOLOv8 (nano to extreme scales) to classify objects with high accuracy.
- **Produce & Quality Sorting Focus**: Automatically categorizes detected objects into produce (full 3D metrics extracted) vs presence (distance only, for safety like a person or electronics). Supported labels include standard fruits and generic quality-grading keywords (resh, spoiled, good, ad).
- **3D Spatial Mapping**: Extracts real-world coordinates in meters (x, y, z) using the ZED camera's depth point cloud data perfectly matched to YOLO bounding box centers.
- **Custom Model Support**: Easily load your own fine-tuned PyTorch model (e.g., model="best.pt") for precise quality-based fruit/vegetable sorting.
- **Live Annotated Feed**: Real-time rendering of bounding boxes to visually verify algorithms.
- **JSON Telemetry Hook**: Background pipeline to HTTP POST frame data directly to a local sorting server or backend endpoint.

### Payload Schema:

When an object (like an apple) is processed, the backend emits:

`json
{
  "timestamp_unix": 1712581200.123,
  "frame_index": 25,
  "detections": [
    {
      "id": 1,
      "label": "apple",
      "confidence": 92.0,
      "position_m": {
        "x": 0.42,
        "y": -0.1,
        "z": 1.85
      },
      "distance_m": 1.9
    }
  ]
}
`

### Useful Commands

Here are some helpful commands to test and debug the vision system from the terminal:

1. **Run the Live Vision System Test (Visual Output):**
   Runs a live YOLO inference window rendering produce with an accurate (yolov8m) model.
   `shell
   python -m tests.test_vision_live --model medium --confidence 50
   `
   *(To use a specialized sorting model later, run: python -m tests.test_vision_live --model path/to/your/custom_grading_model.pt)*

2. **Run ZED SDK Diagnostics:**
   If your camera stream fails to open or PyZED bindings error out, run this:
   `shell
   python -m tests.diagnose_zed
   `

3. **Run Headless Detection Test:**
   Runs the pipeline for 30 seconds without opening an OpenCV window (good for SSH or automated tests):
   `shell
   python -m tests.test_vision_live --duration 30 --skip-display
   `

4. **Verify Unit Tests:**
   Ensures the classification labels and 3D fallbacks evaluate securely:
   `shell
   python -m unittest tests.test_vision_unit
   `

### Setup Notes

- pyzed is provided exclusively by the physical ZED SDK installer (do NOT pip install pyzed).
- You must install requirements: pip install -r requirements.txt (which brings in ultralytics for YOLO, 
umpy, and opencv-python).
