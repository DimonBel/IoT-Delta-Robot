"""
Diagnostic script to check ZED SDK installation and camera connectivity.

Run with: python -m tests.diagnose_zed
"""

import sys
import os
import importlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_import(module_name: str, description: str) -> bool:
    """Check if a module can be imported."""
    try:
        mod = importlib.import_module(module_name)
        print(f"✓ {description}: {module_name}")
        if hasattr(mod, '__version__'):
            print(f"  Version: {mod.__version__}")
        return True
    except ImportError as e:
        print(f"✗ {description}: {module_name}")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"✗ {description}: {module_name}")
        print(f"  Unexpected error: {e}")
        return False


def detect_wrong_pyzed_package() -> bool:
    """Detect a non-Stereolabs 'pyzed' pip package shadowing the official bindings."""
    try:
        pyzed = importlib.import_module("pyzed")
    except Exception:
        return False

    has_sl_attr = hasattr(pyzed, "sl")
    pyzed_file = getattr(pyzed, "__file__", "") or ""
    lowered = pyzed_file.lower()

    # If pyzed imports but pyzed.sl does not, this is usually the wrong pip package.
    try:
        importlib.import_module("pyzed.sl")
        return False
    except Exception:
        pass

    if not has_sl_attr:
        print("! Detected a non-official 'pyzed' Python package.")
        print(f"  Loaded from: {pyzed_file or '<unknown>'}")
        if "site-packages" in lowered:
            print("  This often comes from 'pip install pyzed', which is NOT Stereolabs SDK bindings.")
        return True

    return False


def python_version_supported_hint():
    major, minor = sys.version_info.major, sys.version_info.minor
    print(f"Python version: {major}.{minor}.{sys.version_info.micro}")
    if major == 3 and minor >= 13:
        print("! Python 3.13+ detected.")
        print("  ZED Python bindings are frequently unavailable for this version.")
        print("  Recommended: install Python 3.10 or 3.11 (64-bit) and create a fresh venv.")


def extract_camera_resolution(cam_info):
    """Return (width, height) from camera info across SDK versions."""
    # Older/other bindings may expose this directly.
    direct_res = getattr(cam_info, "camera_resolution", None)
    if direct_res is not None:
        w = getattr(direct_res, "width", None)
        h = getattr(direct_res, "height", None)
        if w is not None and h is not None:
            return w, h

    # Newer bindings commonly expose camera_configuration.resolution.
    cam_cfg = getattr(cam_info, "camera_configuration", None)
    if cam_cfg is not None:
        cfg_res = getattr(cam_cfg, "resolution", None)
        if cfg_res is not None:
            w = getattr(cfg_res, "width", None)
            h = getattr(cfg_res, "height", None)
            if w is not None and h is not None:
                return w, h

    return None, None


def test_zed_sdk():
    """Test ZED SDK installation and camera connection."""
    print("=" * 70)
    print("ZED SDK & Camera Diagnostic")
    print("=" * 70)
    print()
    
    print("Step 1: Checking Python Package Imports")
    print("-" * 70)

    python_version_supported_hint()
    
    cv2_ok = check_import("cv2", "OpenCV")
    numpy_ok = check_import("numpy", "NumPy")
    pyzed_ok = check_import("pyzed.sl", "ZED SDK (pyzed.sl)")
    
    print()
    print("Step 2: Summary of Imports")
    print("-" * 70)
    
    if not pyzed_ok:
        wrong_pkg = detect_wrong_pyzed_package()
        print("✗ ZED SDK (pyzed) not found")
        print()
        print("  Fix steps:")
        if wrong_pkg:
            print("  1. Remove the wrong pyzed package:")
            print("     python -m pip uninstall -y pyzed")
            print("  2. Install official ZED Python API from your SDK:")
            print("     C:\\Program Files (x86)\\ZED SDK\\get_python_api.py")
            print("  3. If that still fails, switch to Python 3.10/3.11 (64-bit) and retry.")
        else:
            print("  1. Install ZED SDK from: https://www.stereolabs.com/developers/release/")
            print("  2. Install official Python API from the SDK install:")
            print("     C:\\Program Files (x86)\\ZED SDK\\get_python_api.py")
            print("  3. If using Python 3.13+, use Python 3.10/3.11 instead.")
        print()
        return False
    
    print("✓ All required packages found")
    print()
    
    # Try to use ZED SDK
    print("Step 3: Testing ZED Camera Connection")
    print("-" * 70)
    
    try:
        import pyzed.sl as sl
        
        # Create camera object
        zed = sl.Camera()
        print("✓ ZED Camera object created")
        
        # Try to open camera
        init_params = sl.InitParameters()
        init_params.depth_mode = sl.DEPTH_MODE.PERFORMANCE
        init_params.coordinate_units = sl.UNIT.METER
        
        status = zed.open(init_params)
        
        if status == sl.ERROR_CODE.SUCCESS:
            print("✓ Camera opened successfully")
            
            # Get camera info
            cam_info = zed.get_camera_information()
            print(f"  Model: {cam_info.camera_model}")
            width, height = extract_camera_resolution(cam_info)
            if width is not None and height is not None:
                print(f"  Resolution: {width}x{height}")
            else:
                print("  Resolution: unavailable in this binding version")
            print(f"  Serial: {cam_info.serial_number}")
            
            # Try to grab a frame
            runtime_params = sl.RuntimeParameters()
            if zed.grab(runtime_params) == sl.ERROR_CODE.SUCCESS:
                print("✓ Successfully grabbed frame from camera")
            else:
                print("✗ Could not grab frame from camera")
            
            zed.close()
            print("✓ Camera closed")
            print()
            print("✓ All checks passed! Camera is working correctly.")
            return True
        else:
            print(f"✗ Failed to open camera")
            print(f"  Error code: {status}")
            print()
            print("  Possible causes:")
            print("  1. Camera is not connected")
            print("  2. Camera is in use by another application")
            print("  3. USB power is insufficient")
            print("  4. Camera firmware needs update")
            print("  5. USB permission issue (on Linux, may need sudo)")
            return False
    
    except Exception as e:
        print(f"✗ Error testing camera: {e}")
        print()
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        print()
        print("  This might indicate:")
        print("  1. ZED SDK is not properly installed")
        print("  2. Missing ZED SDK dependencies")
        print("  3. CUDA/GPU driver issues (if using GPU acceleration)")
        print("  4. Python binding/API version mismatch")
        return False


def main():
    """Run all diagnostics."""
    success = test_zed_sdk()
    
    print()
    print("=" * 70)
    
    if success:
        print("Next steps:")
        print("1. Run: python -m tests.test_vision_live --duration 30")
        print("2. Check if objects are detected in the live video")
        print("3. Review the console output for any detected objects")
    else:
        print("Please fix the issues above before running the vision tests.")
    
    print("=" * 70)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
