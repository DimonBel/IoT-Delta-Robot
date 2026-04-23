"""
Live visual testing tool for vision.py

This script shows real-time object detection from the camera feed with:
- Live video stream from the ZED camera
- Real-time detection boxes and labels
- Confidence scores and coordinates
- Detection logging to verify correct data transmission

Run with: python -m tests.test_vision_live
"""

import sys
import os
import time
import json
from collections import deque

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.vision import ImageRecognition


def draw_detections_on_frame(frame, detections, cv2=None):
    """
    Draw detection boxes and labels on the frame.
    
    Args:
        frame: RGB frame from camera (numpy array)
        detections: List of detection objects
        cv2: OpenCV module
    
    Returns:
        Frame with drawn detections
    """
    if frame is None or cv2 is None:
        return frame
    
    frame_copy = frame.copy()
    
    for detection in detections:
        label = detection.get("label", "unknown")
        confidence = detection.get("confidence", 0.0)
        
        # Extract 3D position
        pos = detection.get("position_m", {})
        x = pos.get("x", 0)
        y = pos.get("y", 0)
        z = pos.get("z", 0)
        
        # Create text with detection info
        text = f"{label} ({confidence:.2f}) | X:{x:.2f}m Y:{y:.2f}m Z:{z:.2f}m"
        
        # Color based on confidence (green for high, red for low)
        confidence_ratio = confidence / 100.0 if confidence > 1 else confidence
        color = (
            int(255 * (1 - confidence_ratio)),  # Red channel
            int(255 * confidence_ratio),         # Green channel
            0                                    # Blue channel
        )
        
        # Draw text on frame
        try:
            cv2.putText(
                frame_copy,
                text,
                (10, 30 + 25 * detections.index(detection)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )
        except Exception:
            pass
    
    return frame_copy


def log_detection_data(frame_payload, stats):
    """
    Log detection data for verification.
    
    Args:
        frame_payload: Frame data from ZED pipeline
        stats: Statistics dictionary
    """
    detections = frame_payload.get("detections", [])
    timestamp = frame_payload.get("timestamp_unix", 0)
    frame_index = frame_payload.get("frame_index", 0)
    
    stats["total_frames"] += 1
    
    if detections:
        stats["frames_with_detections"] += 1
        stats["total_detections"] += len(detections)
        
        # Find best detection
        best = max(detections, key=lambda d: d.get("confidence", 0))
        stats["last_best_detection"] = {
            "label": best.get("label"),
            "confidence": best.get("confidence"),
            "position_m": best.get("position_m"),
            "distance_m": best.get("distance_m"),
            "frame_index": frame_index,
            "timestamp": timestamp,
        }


def run_live_test(
    duration_seconds: int = 60,
    confidence_threshold: int = 40,
    model: str = "medium",
    skip_display: bool = False,
    debug: bool = False,
):
    """
    Run live visual testing of the vision system.
    
    Args:
        duration_seconds: How long to run the test (0 for continuous)
        confidence_threshold: Minimum confidence for detections
        model: Detection model ('fast', 'medium', 'accurate')
        skip_display: Skip display (useful for headless testing)
        debug: Enable debug output
    """
    # Check dependencies first
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV not installed. Install with: pip install opencv-python")
        return False
    
    print("=" * 70)
    print("Vision System Live Test")
    print("=" * 70)
    print(f"Confidence threshold: {confidence_threshold}%")
    print(f"Detection model: {model}")
    print(f"Duration: {'continuous' if duration_seconds == 0 else f'{duration_seconds}s'}")
    print(f"Debug mode: {'ON' if debug else 'OFF'}")
    print("Press 'q' to quit")
    print("=" * 70)
    
    # Initialize vision system
    print("Initializing vision system...")
    vision = ImageRecognition(
        confidence=confidence_threshold,
        model=model,
        auto_start=True,
        debug=debug,
    )
    
    if not vision._zed_enabled:
        print("\nERROR: Could not initialize ZED camera")
        print("Possible causes:")
        print("  1. Camera is not connected to USB")
        print("  2. Camera firmware needs update")
        print("  3. USB port doesn't have enough power")
        print("  4. Another application is using the camera")
        print("  5. ZED SDK initialization failed (try restarting)")
        print()
        print("Run diagnostics: python -m tests.diagnose_zed")
        return False
    
    print("✓ ZED camera initialized successfully")
    
    # Statistics tracking
    stats = {
        "total_frames": 0,
        "frames_with_detections": 0,
        "total_detections": 0,
        "last_best_detection": None,
        "fps_samples": deque(maxlen=30),
    }
    
    start_time = time.time()
    frame_time = time.time()
    
    try:
        while True:
            # Check duration
            elapsed = time.time() - start_time
            if duration_seconds > 0 and elapsed > duration_seconds:
                print(f"\nTest duration ({duration_seconds}s) completed")
                break
            
            # Capture frame
            frame_data = vision.get_frame()
            if frame_data is None:
                print("No frame data received")
                time.sleep(0.1)
                continue
            
            # Calculate FPS
            current_time = time.time()
            frame_delta = current_time - frame_time
            if frame_delta > 0:
                fps = 1.0 / frame_delta
                stats["fps_samples"].append(fps)
            frame_time = current_time
            
            # Extract frame components
            rgb_frame = frame_data.get("rgb")
            annotated_frame = frame_data.get("annotated_rgb")
            payload = frame_data.get("payload", {})
            detections = payload.get("detections", [])
            
            # Log detection data
            log_detection_data(payload, stats)
            
            # Display frame with detections
            if not skip_display and (annotated_frame is not None or rgb_frame is not None):
                display_frame = annotated_frame if annotated_frame is not None else draw_detections_on_frame(rgb_frame, detections, cv2)
                
                # Add stats to frame
                avg_fps = sum(stats["fps_samples"]) / len(stats["fps_samples"]) if stats["fps_samples"] else 0
                stats_text = f"FPS: {avg_fps:.1f} | Detections: {len(detections)}"
                cv2.putText(
                    display_frame,
                    stats_text,
                    (10, display_frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
                
                cv2.imshow("Vision System Live Test", display_frame)
            
            # Print detection info
            if detections:
                best = max(detections, key=lambda d: d.get("confidence", 0))
                print(
                    f"[Frame {payload.get('frame_index', 0)}] "
                    f"{best.get('label', 'unknown')} "
                    f"({best.get('confidence', 0):.2f}%) "
                    f"@ X:{best.get('position_m', {}).get('x', 0):.2f}m "
                    f"Y:{best.get('position_m', {}).get('y', 0):.2f}m "
                    f"Z:{best.get('position_m', {}).get('z', 0):.2f}m"
                )
            
            # Handle keyboard input
            if not skip_display:
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\nUser quit")
                    break
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    success = True
    # Cleanup
    vision.stop()
    if not skip_display:
        cv2.destroyAllWindows()

    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Total frames captured: {stats['total_frames']}")
    print(f"Frames with detections: {stats['frames_with_detections']}")
    print(f"Total detections: {stats['total_detections']}")
    detection_rate = (
        (stats['frames_with_detections'] / stats['total_frames'] * 100)
        if stats['total_frames']
        else 0.0
    )
    print(f"Detection rate: {detection_rate:.1f}%")

    if stats["fps_samples"]:
        avg_fps = sum(stats["fps_samples"]) / len(stats["fps_samples"])
        print(f"Average FPS: {avg_fps:.1f}")

    if stats["last_best_detection"]:
        detection = stats["last_best_detection"]
        print("\nLast detection:")
        print(f"  Label: {detection['label']}")
        print(f"  Confidence: {detection['confidence']:.2f}")
        print(f"  Position: X={detection['position_m']['x']:.2f}m, "
              f"Y={detection['position_m']['y']:.2f}m, "
              f"Z={detection['position_m']['z']:.2f}m")
        print(f"  Distance: {detection['distance_m']:.2f}m")

    print("=" * 70)

    return success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Live visual test for vision system"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Test duration in seconds (0 for continuous)",
    )
    parser.add_argument(
        "--confidence",
        type=int,
        default=40,
        help="Confidence threshold (0-100)",
    )
    parser.add_argument(
        "--model",
        choices=["fast", "medium", "accurate"],
        default="medium",
        help="Detection model to use",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Run without displaying video (headless mode)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output for troubleshooting",
    )
    
    args = parser.parse_args()
    
    success = run_live_test(
        duration_seconds=args.duration,
        confidence_threshold=args.confidence,
        model=args.model,
        skip_display=args.no_display,
        debug=args.debug,
    )
    
    sys.exit(0 if success else 1)
