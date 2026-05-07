"""Compatibility wrapper for reusable live vision command."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.commands import run_live_vision


def run_live_test(
    duration_seconds: int = 60,
    confidence_threshold: int = 40,
    model: str = "medium",
    skip_display: bool = False,
    debug: bool = False,
):
    return run_live_vision(
        duration_seconds=duration_seconds,
        confidence_threshold=confidence_threshold,
        model=model,
        algorithm="yolo",
        skip_display=skip_display,
        debug=debug,
        print_coordinates=False,
    )


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
