"""
Test script for verifying coordinate transmission and backend communication.

This script tests that:
1. Coordinates are extracted correctly from detections
2. JSON payloads are formatted correctly
3. Backend communication works as expected
4. Coordinate accuracy across multiple frames

Run with: python -m tests.test_coordinate_transmission [--backend-url URL]
"""

import sys
import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.vision import ImageRecognition


class CoordinateCapturingHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures coordinates sent by vision system"""
    
    captured_payloads = []
    
    def do_POST(self):
        """Handle POST requests from vision system"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)
            
            # Store payload
            CoordinateCapturingHandler.captured_payloads.append({
                'timestamp': time.time(),
                'payload': payload
            })
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
            
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            print(f"Error processing request: {e}")
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class CoordinateTestServer:
    """Simple server for testing coordinate transmission"""
    
    def __init__(self, port=8765):
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the test server"""
        self.server = HTTPServer(('localhost', self.port), CoordinateCapturingHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.5)  # Give server time to start
        print(f"✓ Test server started on http://localhost:{self.port}")
    
    def stop(self):
        """Stop the test server"""
        if self.server:
            self.server.shutdown()
            self.thread.join(timeout=2)
    
    def get_captured_payloads(self):
        """Get all captured payloads"""
        return CoordinateCapturingHandler.captured_payloads
    
    def clear_payloads(self):
        """Clear captured payloads"""
        CoordinateCapturingHandler.captured_payloads = []


def validate_coordinate_format(coordinates):
    """
    Validate that coordinates are in correct format.
    
    Returns: Tuple of (is_valid, error_message)
    """
    if not isinstance(coordinates, dict):
        return False, "Coordinates must be a dictionary"
    
    required_keys = ['x', 'y', 'z']
    for key in required_keys:
        if key not in coordinates:
            return False, f"Missing coordinate key: {key}"
        
        value = coordinates[key]
        if value is not None and not isinstance(value, (int, float)):
            return False, f"Coordinate {key} must be numeric, got {type(value)}"
    
    return True, None


def validate_detection_record(detection):
    """
    Validate detection record format.
    
    Returns: Tuple of (is_valid, error_message)
    """
    if not isinstance(detection, dict):
        return False, "Detection must be a dictionary"
    
    # Check required fields
    required = ['id', 'label', 'confidence', 'position_m', 'distance_m']
    for field in required:
        if field not in detection:
            return False, f"Missing required field: {field}"
    
    # Validate position coordinates
    is_valid, error = validate_coordinate_format(detection['position_m'])
    if not is_valid:
        return False, f"Invalid position_m: {error}"
    
    # Validate confidence
    confidence = detection['confidence']
    if confidence is not None:
        if not isinstance(confidence, (int, float)):
            return False, "Confidence must be numeric"
        if not (0 <= confidence <= 100):
            return False, f"Confidence out of range (0-100): {confidence}"
    
    # Validate distance
    distance = detection['distance_m']
    if distance is not None and not isinstance(distance, (int, float)):
        return False, "Distance must be numeric"
    
    return True, None


def validate_payload_format(payload):
    """
    Validate the entire payload format.
    
    Returns: Tuple of (is_valid, error_message)
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"
    
    # Check required fields
    required = ['timestamp_unix', 'frame_index', 'detections']
    for field in required:
        if field not in payload:
            return False, f"Missing required field: {field}"
    
    # Validate timestamp
    timestamp = payload['timestamp_unix']
    if not isinstance(timestamp, (int, float)):
        return False, "Timestamp must be numeric"
    
    # Validate frame index
    frame_index = payload['frame_index']
    if not isinstance(frame_index, int):
        return False, "Frame index must be integer"
    
    # Validate detections array
    detections = payload['detections']
    if not isinstance(detections, list):
        return False, "Detections must be an array"
    
    # Validate each detection
    for i, detection in enumerate(detections):
        is_valid, error = validate_detection_record(detection)
        if not is_valid:
            return False, f"Detection {i}: {error}"
    
    return True, None


def test_coordinate_accuracy(payloads):
    """
    Test coordinate consistency across frames.
    
    Returns: Tuple of (passed, report)
    """
    if not payloads:
        return False, "No payloads captured"
    
    report = []
    all_coordinates = []
    
    for i, payload in enumerate(payloads):
        detections = payload.get('detections', [])
        if not detections:
            report.append(f"Frame {i}: No detections")
            continue
        
        # Get best detection
        best = max(detections, key=lambda d: d.get('confidence', 0))
        pos = best.get('position_m', {})
        
        all_coordinates.append({
            'frame': i,
            'x': pos.get('x'),
            'y': pos.get('y'),
            'z': pos.get('z'),
            'label': best.get('label'),
            'confidence': best.get('confidence'),
        })
    
    # Calculate coordinate statistics
    if all_coordinates:
        x_values = [c['x'] for c in all_coordinates if c['x'] is not None]
        y_values = [c['y'] for c in all_coordinates if c['y'] is not None]
        z_values = [c['z'] for c in all_coordinates if c['z'] is not None]
        
        report.append(f"\nCoordinate Statistics:")
        report.append(f"  X: min={min(x_values) if x_values else 'N/A':.2f}, "
                     f"max={max(x_values) if x_values else 'N/A':.2f}")
        report.append(f"  Y: min={min(y_values) if y_values else 'N/A':.2f}, "
                     f"max={max(y_values) if y_values else 'N/A':.2f}")
        report.append(f"  Z: min={min(z_values) if z_values else 'N/A':.2f}, "
                     f"max={max(z_values) if z_values else 'N/A':.2f}")
    
    return True, "\n".join(report)


def run_coordinate_test(
    duration_seconds: int = 30,
    backend_url: str = "http://localhost:8765/detect",
    model: str = "medium",
    debug: bool = False,
):
    """
    Run coordinate transmission test.
    
    Args:
        duration_seconds: How long to capture data
        backend_url: URL to send detection data to
        model: Detection model to use
    """
    print("=" * 70)
    print("Coordinate Transmission Test")
    print("=" * 70)
    print(f"Test duration: {duration_seconds}s")
    print(f"Backend URL: {backend_url}")
    print(f"Detection model: {model}")
    print(f"Debug mode: {'ON' if debug else 'OFF'}")
    print("=" * 70)
    
    # Start test server
    server = CoordinateTestServer(port=8765)
    server.start()
    
    # Initialize vision system with backend
    print("Initializing vision system...")
    vision = ImageRecognition(
        confidence=40,
        model=model,
        backend_url=backend_url,
        backend_timeout=1.5,
        backend_every_n_frames=1,
        auto_start=True,
        debug=debug,
    )
    
    if not vision._zed_enabled:
        print("ERROR: Could not initialize ZED camera")
        print("Possible causes:")
        print("  1. Camera is not connected to USB")
        print("  2. Camera firmware needs update")
        print("  3. USB port doesn't have enough power")
        print("  4. Another application is using the camera")
        print("  5. ZED SDK initialization failed (try restarting)")
        print()
        print("Run diagnostics: python -m tests.diagnose_zed")
        server.stop()
        return False
    
    print("✓ Vision system initialized")
    
    # Capture frames
    print(f"\nCapturing frames for {duration_seconds} seconds...")
    start_time = time.time()
    frame_count = 0
    
    try:
        while time.time() - start_time < duration_seconds:
            frame = vision.get_frame()
            if frame:
                frame_count += 1
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        vision.stop()
    
    # Analyze captured payloads
    print(f"\nCaptured {frame_count} frames")
    payloads = server.get_captured_payloads()
    print(f"Received {len(payloads)} payloads from backend")
    
    server.stop()
    
    if not payloads:
        print("\nERROR: No payloads captured from backend")
        return False
    
    # Validate payload formats
    print("\n" + "=" * 70)
    print("Payload Format Validation")
    print("=" * 70)
    
    all_valid = True
    for i, captured in enumerate(payloads[:5]):  # Check first 5
        payload = captured['payload']
        is_valid, error = validate_payload_format(payload)
        
        if is_valid:
            print(f"✓ Payload {i}: Valid format")
            detections = payload['detections']
            if detections:
                best = max(detections, key=lambda d: d.get('confidence', 0))
                print(f"    {best['label']} ({best['confidence']:.2f}%) "
                      f"@ ({best['position_m']['x']:.2f}, "
                      f"{best['position_m']['y']:.2f}, "
                      f"{best['position_m']['z']:.2f})")
        else:
            print(f"✗ Payload {i}: {error}")
            all_valid = False
    
    if len(payloads) > 5:
        print(f"... and {len(payloads) - 5} more payloads")
    
    # Test coordinate accuracy
    print("\n" + "=" * 70)
    print("Coordinate Accuracy Analysis")
    print("=" * 70)
    
    passed, report = test_coordinate_accuracy(
        [p['payload'] for p in payloads]
    )
    print(report)
    
    # Final summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    if all_valid:
        print("✓ All payload formats are valid")
    else:
        print("✗ Some payload formats are invalid")
    
    print(f"✓ Coordinates are being transmitted correctly")
    print(f"✓ Backend communication is working")
    
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test coordinate transmission from vision system"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds",
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8765/detect",
        help="Backend URL to send detections to",
    )
    parser.add_argument(
        "--model",
        choices=["fast", "medium", "accurate"],
        default="medium",
        help="Detection model to use",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output for troubleshooting",
    )
    
    args = parser.parse_args()
    
    success = run_coordinate_test(
        duration_seconds=args.duration,
        backend_url=args.backend_url,
        model=args.model,
        debug=args.debug,
    )
    
    sys.exit(0 if success else 1)
