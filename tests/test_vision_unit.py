"""Unit tests for vision.py ImageRecognition class."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import math
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.vision import (
    ImageRecognition,
    center_from_bbox_2d,
    to_builtin_float,
    build_detection_record,
    classify_yolo_label,
    safe_point_at_pixel,
)


class TestHelperFunctions(unittest.TestCase):
    """Test utility functions from vision.py"""

    def test_center_from_bbox_2d(self):
        """Test 2D bounding box center calculation"""
        # Rectangle from (10,20) to (30,40)
        bbox = [[10, 20], [30, 20], [30, 40], [10, 40]]
        cx, cy = center_from_bbox_2d(bbox)
        self.assertEqual(cx, 20)
        self.assertEqual(cy, 30)

    def test_center_from_bbox_2d_single_point(self):
        """Test center calculation with a single point"""
        bbox = [[15, 25]]
        cx, cy = center_from_bbox_2d(bbox)
        self.assertEqual(cx, 15)
        self.assertEqual(cy, 25)

    def test_to_builtin_float_valid(self):
        """Test converting to Python float"""
        self.assertEqual(to_builtin_float(3.14), 3.14)
        self.assertEqual(to_builtin_float(0), 0.0)
        self.assertEqual(to_builtin_float(-5.5), -5.5)

    def test_to_builtin_float_none(self):
        """Test converting None value"""
        self.assertIsNone(to_builtin_float(None))

    def test_build_detection_record(self):
        """Test building detection record from object data"""
        # Mock object
        mock_obj = Mock()
        mock_obj.id = 42
        mock_obj.label = "person"
        mock_obj.confidence = 0.95

        record = build_detection_record(mock_obj, 1.5, 2.0, 0.5, 2.5)

        self.assertEqual(record["id"], 42)
        self.assertEqual(record["label"], "person")
        self.assertEqual(record["confidence"], 0.95)
        self.assertEqual(record["position_m"]["x"], 1.5)
        self.assertEqual(record["position_m"]["y"], 2.0)
        self.assertEqual(record["position_m"]["z"], 0.5)
        self.assertEqual(record["distance_m"], 2.5)

    def test_safe_point_at_pixel_invalid_values(self):
        """Test safe point extraction with invalid (NaN, Inf) values"""
        mock_point_cloud = Mock()
        mock_sl = Mock()
        mock_sl.ERROR_CODE.SUCCESS = 0

        # Return success but with NaN values
        mock_point_cloud.get_value.return_value = (0, [float('nan'), 1.0, 2.0])

        result = safe_point_at_pixel(mock_point_cloud, mock_sl, 10, 20)
        self.assertIsNone(result)

    def test_safe_point_at_pixel_valid_values(self):
        """Test safe point extraction with valid values"""
        mock_point_cloud = Mock()
        mock_sl = Mock()
        mock_sl.ERROR_CODE.SUCCESS = 0

        mock_point_cloud.get_value.return_value = (0, [1.5, 2.0, 0.5])

        result = safe_point_at_pixel(mock_point_cloud, mock_sl, 10, 20)
        self.assertEqual(result, (1.5, 2.0, 0.5))

    def test_classify_yolo_label_produce(self):
        kind, label = classify_yolo_label("Apple")
        self.assertEqual(kind, "produce")
        self.assertEqual(label, "apple")

    def test_classify_yolo_label_people_and_electronics(self):
        person_kind, person_label = classify_yolo_label("person")
        phone_kind, phone_label = classify_yolo_label("cell phone")
        skip_kind, skip_label = classify_yolo_label("chair")

        self.assertEqual(person_kind, "presence")
        self.assertEqual(person_label, "person_presence")
        self.assertEqual(phone_kind, "presence")
        self.assertEqual(phone_label, "electronics_presence")
        self.assertEqual(skip_kind, "skip")
        self.assertIsNone(skip_label)


class TestImageRecognition(unittest.TestCase):
    """Test ImageRecognition class"""

    def setUp(self):
        """Mock ZEDCoordinateVisionPipeline before creating ImageRecognition"""
        self.patcher = patch('vision.vision.ZEDCoordinateVisionPipeline')
        self.mock_pipeline_class = self.patcher.start()
        self.mock_pipeline = MagicMock()
        self.mock_pipeline_class.return_value = self.mock_pipeline
        self.mock_pipeline.open.return_value = True

        self.yolo_patcher = patch('vision.vision.ZEDYoloVisionPipeline')
        self.mock_yolo_class = self.yolo_patcher.start()
        self.mock_yolo_pipeline = MagicMock()
        self.mock_yolo_class.return_value = self.mock_yolo_pipeline
        self.mock_yolo_pipeline.open.return_value = True

    def tearDown(self):
        """Stop mocking"""
        self.patcher.stop()
        self.yolo_patcher.stop()

    def test_initialization_with_auto_start(self):
        """Test ImageRecognition initializes and starts automatically"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        self.assertTrue(recognition._zed_enabled)
        self.mock_pipeline.open.assert_called_once()

    def test_initialization_without_auto_start(self):
        """Test ImageRecognition initializes without starting"""
        recognition = ImageRecognition(algorithm="zed", auto_start=False)
        self.assertFalse(recognition._zed_enabled)
        self.mock_pipeline.open.assert_not_called()

    def test_start_when_already_running(self):
        """Test that start() returns True if already running"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        self.mock_pipeline.open.reset_mock()
        
        result = recognition.start()
        
        self.assertTrue(result)
        self.mock_pipeline.open.assert_not_called()

    def test_stop(self):
        """Test stopping the recognition"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        recognition.stop()
        
        self.assertFalse(recognition._zed_enabled)
        self.mock_pipeline.close.assert_called_once()

    def test_get_frame_when_disabled(self):
        """Test get_frame attempts to start if disabled"""
        self.mock_pipeline.open.return_value = True
        recognition = ImageRecognition(algorithm="zed", auto_start=False)
        
        frame = recognition.get_frame()
        
        # Should attempt to start
        self.mock_pipeline.open.assert_called_once()

    def test_analyze_empty_frame(self):
        """Test analyze handles empty frames"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        
        result = recognition.analyze(None)
        
        self.assertIsNone(result)

    def test_analyze_frame_without_detections(self):
        """Test analyze handles frames with no detections"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        frame = {"payload": {"detections": []}}
        
        result = recognition.analyze(frame)
        
        self.assertIsNone(result)

    def test_analyze_single_detection(self):
        """Test analyze extracts best detection from frame"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        frame = {
            "payload": {
                "detections": [
                    {
                        "label": "person",
                        "confidence": 0.95,
                        "position_m": {"x": 1.5, "y": 2.0, "z": 0.5},
                        "distance_m": 2.5,
                    }
                ]
            }
        }
        
        result = recognition.analyze(frame)
        
        self.assertEqual(result["label"], "person")
        self.assertEqual(result["confidence"], 0.95)
        self.assertEqual(result["x"], 1.5)
        self.assertEqual(result["y"], 2.0)
        self.assertEqual(result["z"], 0.5)
        self.assertEqual(result["distance_m"], 2.5)

    def test_analyze_multiple_detections_picks_best(self):
        """Test analyze picks detection with highest confidence"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        frame = {
            "payload": {
                "detections": [
                    {
                        "label": "person",
                        "confidence": 0.75,
                        "position_m": {"x": 1.0, "y": 1.0, "z": 1.0},
                        "distance_m": 1.73,
                    },
                    {
                        "label": "dog",
                        "confidence": 0.92,
                        "position_m": {"x": 2.0, "y": 2.0, "z": 2.0},
                        "distance_m": 3.46,
                    },
                ]
            }
        }
        
        result = recognition.analyze(frame)
        
        self.assertEqual(result["label"], "dog")
        self.assertEqual(result["confidence"], 0.92)

    def test_get_detection_data(self):
        """Test get_detection_data combines get_frame and analyze"""
        recognition = ImageRecognition(algorithm="zed", auto_start=True)
        frame = {
            "payload": {
                "detections": [
                    {
                        "label": "cat",
                        "confidence": 0.88,
                        "position_m": {"x": 0.5, "y": 0.5, "z": 0.5},
                        "distance_m": 0.87,
                    }
                ]
            }
        }
        self.mock_pipeline.read.return_value = frame
        
        result = recognition.get_detection_data()
        
        self.assertIsNotNone(result)
        self.assertEqual(result["label"], "cat")

    def test_config_parameters(self):
        """Test that configuration parameters are passed correctly"""
        recognition = ImageRecognition(algorithm="zed", 
            confidence=50,
            model="accurate",
            backend_url="http://example.com",
            backend_timeout=2.0,
            backend_every_n_frames=5,
        )
        
        self.assertEqual(recognition._config["confidence"], 50)
        self.assertEqual(recognition._config["model"], "accurate")
        self.assertEqual(recognition._config["backend_url"], "http://example.com")
        self.assertEqual(recognition._config["backend_timeout"], 2.0)
        self.assertEqual(recognition._config["backend_every_n_frames"], 5)

    def test_algorithm_selection_yolo(self):
        recognition = ImageRecognition(algorithm="yolo", auto_start=False)
        self.mock_yolo_class.assert_called_once()
        self.assertIs(recognition._zed_pipeline, self.mock_yolo_pipeline)

    def test_algorithm_selection_zed_default(self):
        recognition = ImageRecognition(algorithm="zed", auto_start=False)
        self.mock_pipeline_class.assert_called_once()
        self.assertIs(recognition._zed_pipeline, self.mock_pipeline)


if __name__ == "__main__":
    unittest.main()
