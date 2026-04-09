# The logic is lazy-loaded to avoid breaking environments where ZED/OpenCV are not installed yet.
import json
import importlib
import math
import time
import urllib.error
import urllib.request

class ImageRecognition:
    def __init__(
        self,
        confidence: int = 40,
        model: str = "medium",
        backend_url: str = "",
        backend_timeout: float = 1.5,
        backend_every_n_frames: int = 1,
        auto_start: bool = True,
    ):
        self._config = {
            "confidence": confidence,
            "model": model,
            "backend_url": backend_url,
            "backend_timeout": backend_timeout,
            "backend_every_n_frames": backend_every_n_frames,
        }
        self._zed_pipeline = ZEDCoordinateVisionPipeline(**self._config)
        self._zed_enabled = False

        if auto_start:
            self.start()

    def start(self) -> bool:
        if self._zed_enabled:
            return True
        self._zed_enabled = self._zed_pipeline.open()
        return self._zed_enabled

    def stop(self):
        if self._zed_pipeline:
            self._zed_pipeline.close()
        self._zed_enabled = False

    def get_frame(self):
        # Lazy start so app can boot even when camera/SDK is temporarily unavailable.
        if not self._zed_enabled and not self.start():
            return None
        return self._zed_pipeline.read()

    def analyze(self, frame):
        if not frame:
            return None

        payload = frame.get("payload", {})
        detections = payload.get("detections", [])
        if not detections:
            return None

        best = max(detections, key=lambda d: d.get("confidence") or 0.0)
        pos = best.get("position_m", {})
        return {
            "x": pos.get("x"),
            "y": pos.get("y"),
            "z": pos.get("z"),
            "label": best.get("label"),
            "confidence": best.get("confidence"),
            "distance_m": best.get("distance_m"),
        }

    def get_detection_data(self):
        frame = self.get_frame()
        return self.analyze(frame)

def safe_point_at_pixel(point_cloud, x: int, y: int):
    error_code, point = point_cloud.get_value(x, y)
    if error_code != point_cloud._sl.ERROR_CODE.SUCCESS:
        return None

    px, py, pz = point[0], point[1], point[2]
    if not (math.isfinite(px) and math.isfinite(py) and math.isfinite(pz)):
        return None

    return px, py, pz


def center_from_bbox_2d(bbox_2d):
    xs = [int(p[0]) for p in bbox_2d]
    ys = [int(p[1]) for p in bbox_2d]
    return int(sum(xs) / len(xs)), int(sum(ys) / len(ys))


def to_builtin_float(value):
    return float(value) if value is not None else None


def build_detection_record(obj, x, y, z, distance):
    return {
        "id": int(obj.id),
        "label": str(obj.label),
        "confidence": to_builtin_float(obj.confidence),
        "position_m": {
            "x": to_builtin_float(x),
            "y": to_builtin_float(y),
            "z": to_builtin_float(z),
        },
        "distance_m": to_builtin_float(distance),
    }


def send_json_payload(url: str, payload: dict, timeout_sec: float):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return response.status


class ZEDCoordinateVisionPipeline:
    def __init__(
        self,
        confidence: int = 40,
        model: str = "medium",
        backend_url: str = "",
        backend_timeout: float = 1.5,
        backend_every_n_frames: int = 1,
    ):
        self.confidence = confidence
        self.model = model
        self.backend_url = backend_url
        self.backend_timeout = backend_timeout
        self.backend_every_n_frames = max(1, int(backend_every_n_frames))

        self._sl = None
        self._zed = None
        self._runtime_params = None
        self._detection_runtime = None
        self._objects = None
        self._point_cloud = None
        self._left_image = None
        self._depth_map = None
        self._frame_index = 0
        self._last_backend_error_ts = 0.0

    def _try_import_dependencies(self):
        try:
            sl = importlib.import_module("pyzed.sl")
            cv2 = importlib.import_module("cv2")
            np = importlib.import_module("numpy")
        except Exception:
            return None, None, None
        return sl, cv2, np

    def _try_open_camera_with_fallbacks(self):
        sl = self._sl
        attempts = [
            ("HD720@30 ULTRA", sl.RESOLUTION.HD720, 30, sl.DEPTH_MODE.ULTRA),
            ("HD720@15 PERFORMANCE", sl.RESOLUTION.HD720, 15, sl.DEPTH_MODE.PERFORMANCE),
            ("VGA@30 PERFORMANCE", sl.RESOLUTION.VGA, 30, sl.DEPTH_MODE.PERFORMANCE),
            ("VGA@15 PERFORMANCE", sl.RESOLUTION.VGA, 15, sl.DEPTH_MODE.PERFORMANCE),
        ]

        for _label, resolution, fps, depth_mode in attempts:
            init_params = sl.InitParameters()
            init_params.depth_mode = depth_mode
            init_params.coordinate_units = sl.UNIT.METER
            init_params.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Y_UP
            init_params.camera_resolution = resolution
            init_params.camera_fps = fps
            init_params.camera_disable_self_calib = True
            init_params.enable_image_enhancement = True
            init_params.sdk_verbose = 1

            status = self._zed.open(init_params)
            if status == sl.ERROR_CODE.SUCCESS:
                return True

            time.sleep(0.5)

        return False

    def open(self):
        sl, _cv2, _np = self._try_import_dependencies()
        if not sl:
            return False

        self._sl = sl
        self._zed = sl.Camera()
        if not self._try_open_camera_with_fallbacks():
            return False

        tracking_params = sl.PositionalTrackingParameters()
        status = self._zed.enable_positional_tracking(tracking_params)
        if status != sl.ERROR_CODE.SUCCESS:
            self.close()
            return False

        detection_model_map = {
            "fast": sl.OBJECT_DETECTION_MODEL.MULTI_CLASS_BOX_FAST,
            "medium": sl.OBJECT_DETECTION_MODEL.MULTI_CLASS_BOX_MEDIUM,
            "accurate": sl.OBJECT_DETECTION_MODEL.MULTI_CLASS_BOX_ACCURATE,
        }

        detection_params = sl.ObjectDetectionParameters()
        detection_params.enable_tracking = True
        detection_params.enable_segmentation = False
        detection_params.detection_model = detection_model_map.get(
            self.model, sl.OBJECT_DETECTION_MODEL.MULTI_CLASS_BOX_MEDIUM
        )

        status = self._zed.enable_object_detection(detection_params)
        if status != sl.ERROR_CODE.SUCCESS:
            self.close()
            return False

        self._runtime_params = sl.RuntimeParameters()
        self._detection_runtime = sl.ObjectDetectionRuntimeParameters()
        self._detection_runtime.detection_confidence_threshold = self.confidence

        self._objects = sl.Objects()
        self._point_cloud = sl.Mat()
        self._point_cloud._sl = sl
        self._left_image = sl.Mat()
        self._depth_map = sl.Mat()
        return True

    def _zed_rgba_to_bgr(self, image_mat):
        _sl, cv2, _np = self._try_import_dependencies()
        if cv2 is None:
            return None
        rgba = image_mat.get_data()
        return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)

    def _depth_to_colormap(self, depth_mat, max_depth_m=8.0):
        _sl, cv2, np = self._try_import_dependencies()
        if cv2 is None or np is None:
            return None
        depth = depth_mat.get_data()
        depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
        depth = np.clip(depth, 0.0, max_depth_m)
        depth_8u = np.uint8((depth / max_depth_m) * 255.0)
        return cv2.applyColorMap(depth_8u, cv2.COLORMAP_TURBO)

    def read(self):
        if not self._zed:
            return None

        sl = self._sl
        if self._zed.grab(self._runtime_params) != sl.ERROR_CODE.SUCCESS:
            return None

        self._frame_index += 1

        self._zed.retrieve_objects(self._objects, self._detection_runtime)
        self._zed.retrieve_measure(self._point_cloud, sl.MEASURE.XYZRGBA, sl.MEM.CPU)
        self._zed.retrieve_image(self._left_image, sl.VIEW.LEFT, sl.MEM.CPU)
        self._zed.retrieve_measure(self._depth_map, sl.MEASURE.DEPTH, sl.MEM.CPU)

        rgb_frame = self._zed_rgba_to_bgr(self._left_image)
        depth_frame = self._depth_to_colormap(self._depth_map)

        frame_payload = {
            "timestamp_unix": time.time(),
            "frame_index": self._frame_index,
            "detections": [],
        }

        for obj in self._objects.object_list:
            position = obj.position
            x, y, z = float(position[0]), float(position[1]), float(position[2])

            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                cx, cy = center_from_bbox_2d(obj.bounding_box_2d)
                fallback = safe_point_at_pixel(self._point_cloud, cx, cy)
                if fallback is not None:
                    x, y, z = fallback
                else:
                    continue

            distance = math.sqrt(x * x + y * y + z * z)
            detection_record = build_detection_record(obj, x, y, z, distance)
            frame_payload["detections"].append(detection_record)

        if self.backend_url and (self._frame_index % self.backend_every_n_frames == 0):
            try:
                send_json_payload(self.backend_url, frame_payload, self.backend_timeout)
            except (urllib.error.URLError, TimeoutError, ValueError):
                now = time.time()
                if now - self._last_backend_error_ts > 2.0:
                    self._last_backend_error_ts = now

        return {
            "rgb": rgb_frame,
            "depth": depth_frame,
            "payload": frame_payload,
        }

    def close(self):
        if not self._zed:
            return

        try:
            self._zed.disable_object_detection()
        except Exception:
            pass
        try:
            self._zed.disable_positional_tracking()
        except Exception:
            pass
        try:
            self._zed.close()
        except Exception:
            pass


