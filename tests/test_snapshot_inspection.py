"""
Run snapshot (still image) produce inspection — quality / classification without the ZED camera.

Compare with live vision: live uses the same YOLO weights but adds depth + board (U,V) mapping.

Usage (from repo root):
  python -m tests.test_snapshot_inspection --images path/to/a.jpg path/to/b.jpg
  python -m tests.test_snapshot_inspection --images samples/*.jpg --json-out report.json
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.commands import inspect_snapshot_images


def main():
    parser = argparse.ArgumentParser(description="Snapshot produce inspection (YOLO + fuzzy grading)")
    parser.add_argument(
        "--images",
        nargs="+",
        required=True,
        help="One or more image paths (JPEG/PNG, BGR as saved by OpenCV)",
    )
    parser.add_argument("--confidence", type=int, default=35, help="YOLO confidence 0-100")
    parser.add_argument(
        "--model",
        default="medium",
        help="yolov8 preset: fast, medium, accurate, extreme, or a .pt path",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="If set, write full report JSON to this file",
    )
    args = parser.parse_args()
    return inspect_snapshot_images(
        image_paths=args.images,
        confidence=args.confidence,
        model=args.model,
        json_out=args.json_out,
    )


if __name__ == "__main__":
    sys.exit(main())
