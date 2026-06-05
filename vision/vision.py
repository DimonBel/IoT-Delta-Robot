# The logic is lazy-loaded to avoid breaking environments where ZED/OpenCV are not installed yet.
import json
import importlib
import math
import os
import sys
import traceback
import time
import urllib.error
import urllib.request

from vision.board_mapping import (
    bbox_to_quad_xyxy,
    board_payload_from_state,
    build_image_to_board_homography,
    image_point_to_board_uv,
)
from vision.labels import classify_yolo_label
from vision.snapshot_inspection import SnapshotProduceInspector


class ImageRecognition:
    def __init__(
        self,
        confidence: int = 40,
        model: str = "medium",  # Maps to yolov8m.pt by default for better fruit detection, or pass a custom .pt file path
        algorithm: str = "yolo", # Defaulting to yolo for more advanced tracking
        backend_url: str = "",
        backend_timeout: float = 1.5,
        backend_every_n_frames: int = 1,
        auto_start: bool = True,
        debug: bool = False,
        imgsz: int = 832,
        enhance_low_light: bool = False,
        person_min_confidence: int = 40,
    ):
        self._config = {
            "confidence": confidence,
            "model": model,
            "algorithm": algorithm,
            "backend_url": backend_url,
            "backend_timeout": backend_timeout,
            "backend_every_n_frames": backend_every_n_frames,
            "imgsz": imgsz,
            "enhance_low_light": enhance_low_light,
            "person_min_confidence": person_min_confidence,
        }
        self._debug = debug
        pipeline_map = {
            "zed": ZEDCoordinateVisionPipeline,
            "yolo": ZEDYoloVisionPipeline,
        }
        pipeline_cls = pipeline_map.get((algorithm or "zed").lower())
        if pipeline_cls is None:
            raise ValueError("Unsupported algorithm. Use 'zed' or 'yolo'.")

        self._zed_pipeline = pipeline_cls(**self._config)
        self._zed_enabled = False

        if auto_start:
            self.start()

    def start(self) -> bool:
        if self._zed_enabled:
            return True
        self._zed_enabled = self._zed_pipeline.open(verbose=self._debug)
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

def safe_point_at_pixel(point_cloud, sl, x: int, y: int):
    error_code, point = point_cloud.get_value(x, y)
    if error_code != sl.ERROR_CODE.SUCCESS:
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


def _value_or_sequence_to_list(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [to_builtin_float(v) for v in value]
    if hasattr(value, "tolist"):
        try:
            sequence = value.tolist()
            if isinstance(sequence, list):
                return [to_builtin_float(v) for v in sequence]
        except Exception:
            return None
    return None


def extract_plane_data(plane):
    if plane is None:
        return None

    normal = None
    center = None
    extents = None
    bounds = None
    plane_type = None

    for getter_name, target in (
        ("get_normal", "normal"),
        ("get_center", "center"),
        ("get_extents", "extents"),
        ("get_bounds", "bounds"),
    ):
        try:
            value = getattr(plane, getter_name)()
            parsed = _value_or_sequence_to_list(value)
            if target == "normal":
                normal = parsed
            elif target == "center":
                center = parsed
            elif target == "extents":
                extents = parsed
            elif target == "bounds":
                bounds = parsed
        except Exception:
            continue

    try:
        plane_type = str(getattr(plane, "type", None))
    except Exception:
        plane_type = None

    return {
        "type": plane_type,
        "normal": normal,
        "center": center,
        "extents": extents,
        "bounds": bounds,
    }


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
        algorithm: str = "zed",
        backend_url: str = "",
        backend_timeout: float = 1.5,
        backend_every_n_frames: int = 1,
        imgsz: int = 640,                  # accepted but unused at this layer
        enhance_low_light: bool = False,   # idem
        person_min_confidence: int = 40,   # idem
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

    def _configure_windows_zed_runtime(self, verbose: bool = False):
        if sys.platform != "win32":
            return

        candidate_roots = [
            os.environ.get("ZED_SDK_ROOT_DIR", ""),
            r"C:\Program Files\ZED SDK",
            r"C:\Program Files (x86)\ZED SDK",
        ]
        candidate_roots = [p for p in candidate_roots if p and os.path.isdir(p)]

        search_dirs = []
        for root in candidate_roots:
            search_dirs.extend(
                [
                    root,
                    os.path.join(root, "bin"),
                    os.path.join(root, "lib"),
                    os.path.join(root, "python"),
                    os.path.join(root, "python_api"),
                ]
            )

        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            if d not in sys.path:
                sys.path.insert(0, d)
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass

            pyzed_pkg = os.path.join(d, "pyzed")
            if os.path.isdir(pyzed_pkg) and d not in sys.path:
                sys.path.insert(0, d)

        if verbose:
            print("[DEBUG] Probed Windows ZED SDK paths for pyzed and DLLs")

    def _try_import_dependencies(self, verbose: bool = False):
        pyzed_error = None
        try:
            sl = importlib.import_module("pyzed.sl")
        except ImportError as e:
            pyzed_error = e
            self._configure_windows_zed_runtime(verbose=verbose)
            try:
                sl = importlib.import_module("pyzed.sl")
            except ImportError:
                if verbose:
                    print(f"[DEBUG] Import error: {pyzed_error}")
                    try:
                        pyzed_mod = importlib.import_module("pyzed")
                        pyzed_origin = getattr(pyzed_mod, "__file__", "<unknown>")
                        print(f"[DEBUG] Found 'pyzed' module at: {pyzed_origin}")
                    except Exception:
                        pass

                    major, minor = sys.version_info.major, sys.version_info.minor
                    if major == 3 and minor >= 13:
                        print("[DEBUG] Python 3.13+ detected. ZED Python bindings are often unavailable for this version.")
                        print("[DEBUG] Recommended: use Python 3.10 or 3.11 (64-bit) in a virtual environment.")

                    print("[DEBUG] If you installed 'pip install pyzed', uninstall it. It is not the official Stereolabs binding.")
                    print("[DEBUG] Run: python -m pip uninstall -y pyzed")
                    print("[DEBUG] Then run: C:\\Program Files (x86)\\ZED SDK\\get_python_api.py")
                return None, None, None
            except Exception as inner_e:
                if verbose:
                    print(f"[DEBUG] Unexpected import error: {inner_e}")
                    print(traceback.format_exc())
                return None, None, None
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Unexpected import error: {e}")
                print(traceback.format_exc())
            return None, None, None

        cv2 = None
        np = None
        try:
            cv2 = importlib.import_module("cv2")
        except Exception:
            if verbose:
                print("[DEBUG] OpenCV import failed; RGB/depth visualization will be disabled")

        try:
            np = importlib.import_module("numpy")
        except Exception:
            if verbose:
                print("[DEBUG] NumPy import failed; depth colormap visualization will be disabled")

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

    def open(self, verbose: bool = False):
        if verbose:
            print("[DEBUG] Opening ZED camera...")

        sl, _cv2, _np = self._try_import_dependencies(verbose=verbose)
        if not sl:
            if verbose:
                print("[DEBUG] Failed to import dependencies")
            return False

        self._sl = sl
        self._zed = sl.Camera()
        if verbose:
            print("[DEBUG] Camera object created, attempting to open...")

        if not self._try_open_camera_with_fallbacks():
            if verbose:
                print("[DEBUG] Failed to open camera with fallback attempts")
            return False

        if verbose:
            print("[DEBUG] Camera opened, enabling positional tracking...")

        tracking_params = sl.PositionalTrackingParameters()
        status = self._zed.enable_positional_tracking(tracking_params)
        if status != sl.ERROR_CODE.SUCCESS:
            if verbose:
                print(f"[DEBUG] Failed to enable positional tracking: {status}")
            self.close()
            return False

        if verbose:
            print("[DEBUG] Positional tracking enabled, enabling object detection...")

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
            if verbose:
                print(f"[DEBUG] Failed to enable object detection: {status}")
            self.close()
            return False

        self._runtime_params = sl.RuntimeParameters()
        self._detection_runtime = sl.ObjectDetectionRuntimeParameters()
        self._detection_runtime.detection_confidence_threshold = self.confidence

        self._objects = sl.Objects()
        self._point_cloud = sl.Mat()
        self._left_image = sl.Mat()
        self._depth_map = sl.Mat()

        if verbose:
            print("[DEBUG] ZED camera fully initialized")

        return True

    def _zed_rgba_to_bgr(self, image_mat):
        _sl, cv2, _np = self._try_import_dependencies(verbose=False)
        if cv2 is None:
            return None
        rgba = image_mat.get_data()
        return cv2.cvtColor(rgba, cv2.COLOR_BGRA2BGR)

    def _depth_to_colormap(self, depth_mat, max_depth_m=8.0):
        _sl, cv2, np = self._try_import_dependencies(verbose=False)
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
                fallback = safe_point_at_pixel(self._point_cloud, sl, cx, cy)
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


class ZEDYoloVisionPipeline(ZEDCoordinateVisionPipeline):
    def __init__(
        self,
        confidence: int = 40,
        model: str = "medium",
        algorithm: str = "yolo",
        backend_url: str = "",
        backend_timeout: float = 1.5,
        backend_every_n_frames: int = 1,
        imgsz: int = 832,
        enhance_low_light: bool = False,
        person_min_confidence: int = 40,
    ):
        super().__init__(
            confidence=confidence,
            model=model,
            algorithm=algorithm,
            backend_url=backend_url,
            backend_timeout=backend_timeout,
            backend_every_n_frames=backend_every_n_frames,
        )
        self._yolo = None
        self._class_names = {}
        self._cv2 = None
        self._np = None
        self._support_plane_mode = "hit"
        self._last_floor_plane = None
        self._last_floor_plane_ts = 0.0
        # YOLO runs every frame. Default imgsz is 640 to recover small/distant
        # produce — that's a recall-vs-latency trade vs the older 416 default.
        # On CPU you may drop below 30 FPS; pass `imgsz=416` (or smaller) to
        # restore the previous budget. Bump to 832/1280 when GPU has headroom.
        self._yolo_inference_every_n_frames = 1
        self._yolo_image_size = max(96, int(imgsz))
        self._enhance_low_light = bool(enhance_low_light)
        self._person_min_confidence = max(0, min(100, int(person_min_confidence)))
        self._enable_depth_preview = False
        self._enable_support_plane = False
        self._last_detections = []
        self._yolo_device = None
        self._yolo_half = False
        # Board "map" coordinates (0–1) from an angled view via homography on the detected base.
        self._board_homography = None
        self._board_initialized = False
        self._board_quad_corners = None
        self._board_lock_min_confidence = 45.0
        # Calibration ROI: if a calibration JSON is found, YOLO inference is
        # restricted to the polygon clicked by the operator (the work square).
        # This both improves recall on small/distant objects inside the work
        # zone (the model sees that area at a higher effective resolution) and
        # speeds up inference (less pixels to process).
        self._calibration_path = "calibration/calibration.json"
        self._calib_polygon_xy = None
        self._calib_crop_xyxy = None
        self._calib_padding_px = 24

    def _resolve_yolo_model_name(self):
        # By default, use heavier models for better fruit recognition if predefined alias is used,
        # but allow passing a custom '.pt' file path directly (e.g., 'best.pt' for a trained model).
        presets = {
            "fast": "yolov8n.pt",
            "medium": "yolov8m.pt",
            "accurate": "yolov8l.pt",
            "extreme": "yolov8x.pt"
        }
        return presets.get(self.model, self.model)

    def _yolo_preprocess(self, image_bgr):
        """Optional CLAHE on the L channel for low-light scenes. Off by default.

        Cheap (~2-5 ms on a HD frame) and meaningfully improves YOLO recall when
        the produce sits in shadow. Enable with `enhance_low_light=True` (which
        the CLI exposes as `--enhance`).
        """
        if not self._enhance_low_light or self._cv2 is None or image_bgr is None:
            return image_bgr
        try:
            lab = self._cv2.cvtColor(image_bgr, self._cv2.COLOR_BGR2LAB)
            l, a, b = self._cv2.split(lab)
            clahe = self._cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            l = clahe.apply(l)
            return self._cv2.cvtColor(self._cv2.merge((l, a, b)), self._cv2.COLOR_LAB2BGR)
        except getattr(self._cv2, "error", Exception):
            # cv2 itself raised on a malformed frame (wrong dtype/shape).
            # Skip preprocessing and continue rather than crash the loop.
            return image_bgr

    def _try_import_yolo_dependencies(self, verbose: bool = False):
        sl, cv2, np = self._try_import_dependencies(verbose=verbose)
        if not sl or np is None:
            return None, None, None, None

        try:
            yolo_cls = importlib.import_module("ultralytics").YOLO
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Failed to import ultralytics YOLO: {e}")
                print("[DEBUG] Install with: python -m pip install ultralytics")
            return None, None, None, None

        return sl, cv2, np, yolo_cls

    def _rgba_to_bgr(self, rgba_frame):
        # Prefer OpenCV conversion when available, otherwise use NumPy channel flip.
        if self._cv2 is not None:
            return self._cv2.cvtColor(rgba_frame, self._cv2.COLOR_BGRA2BGR)
        return rgba_frame[:, :, :3][:, :, ::-1]

    _OVERLAY_COLORS_BGR = {
        "produce": (0, 220, 0),
        "human": (220, 120, 0),
        "base_board": (220, 220, 0),
        "delta_robot": (220, 0, 220),
        "object": (180, 180, 180),
    }

    def _draw_yolo_overlay(self, frame, detections):
        if frame is None or self._cv2 is None:
            return frame

        overlay = frame.copy()
        for detection in detections:
            bbox = detection.get("bbox_xyxy")
            if not bbox:
                continue

            dtype = detection.get("detection_type", "produce")
            color = self._OVERLAY_COLORS_BGR.get(dtype, (200, 200, 200))

            x1, y1, x2, y2 = [int(v) for v in bbox]
            label = detection.get("label", dtype)
            confidence = detection.get("confidence", 0.0)
            distance = detection.get("distance_m")
            bm = detection.get("board_map") or {}

            if bm.get("valid"):
                caption = (
                    f"{label} {confidence:.1f}% "
                    f"map U:{bm.get('u', 0):.2f} V:{bm.get('v', 0):.2f}"
                )
            elif distance is None:
                caption = f"{label} {confidence:.1f}%"
            else:
                caption = f"{label} {confidence:.1f}% {distance:.2f}m"

            self._cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            text_y = max(20, y1 - 8)
            self._cv2.putText(
                overlay,
                caption,
                (x1, text_y),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

            # Centre marker: the actual (u, v) used to produce board_xy_mm.
            # Uses refined_detection_center's output when present, else the
            # bbox arithmetic-mean centre. Red so it's unmistakable against
            # the type-coloured bbox; the white halo keeps it visible on red
            # backgrounds (e.g. an apple).
            center_uv = detection.get("center_uv")
            if center_uv is None or len(center_uv) < 2:
                cx = int(round((x1 + x2) / 2.0))
                cy = int(round((y1 + y2) / 2.0))
            else:
                try:
                    cx = int(round(float(center_uv[0])))
                    cy = int(round(float(center_uv[1])))
                except (TypeError, ValueError):
                    cx = int(round((x1 + x2) / 2.0))
                    cy = int(round((y1 + y2) / 2.0))
            red = (0, 0, 255)
            self._cv2.circle(overlay, (cx, cy), 6, (255, 255, 255), -1)
            self._cv2.circle(overlay, (cx, cy), 4, red, -1)
            self._cv2.drawMarker(
                overlay, (cx, cy), red,
                self._cv2.MARKER_CROSS, 14, 2,
            )

            # Coordinate label next to the dot: board mm + track id.
            bxy = detection.get("board_xy_mm") or {}
            coord_bits: list[str] = []
            track_id = detection.get("track_id")
            if track_id is not None:
                coord_bits.append(f"#{int(track_id)}")
            if bxy.get("x") is not None and bxy.get("y") is not None:
                coord_bits.append(f"X:{bxy['x']:+.0f} Y:{bxy['y']:+.0f} mm")
            if coord_bits:
                coord_text = "  ".join(coord_bits)
                text_org = (cx + 10, cy + 18)
                # Black halo for readability over any background.
                self._cv2.putText(
                    overlay, coord_text, text_org,
                    self._cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 0, 0), 3, self._cv2.LINE_AA,
                )
                self._cv2.putText(
                    overlay, coord_text, text_org,
                    self._cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    red, 1, self._cv2.LINE_AA,
                )

        if self._board_initialized and self._board_quad_corners is not None and self._np is not None:
            pts = self._board_quad_corners.reshape(-1, 1, 2).astype(int)
            self._cv2.polylines(overlay, [pts], isClosed=True, color=(0, 255, 255), thickness=2)

        return overlay

    def _sync_board_state(self, detections):
        candidates = [d for d in detections if d.get("detection_type") == "base_board"]
        if not candidates:
            return
        best = max(candidates, key=lambda d: d.get("confidence") or 0.0)
        if (best.get("confidence") or 0.0) < self._board_lock_min_confidence:
            return
        bbox = best.get("bbox_xyxy")
        if not bbox:
            return
        x1, y1, x2, y2 = [int(v) for v in bbox]
        quad = bbox_to_quad_xyxy(x1, y1, x2, y2)
        self._board_homography = build_image_to_board_homography(quad)
        self._board_initialized = True
        self._board_quad_corners = quad

    def _apply_board_maps(self, detections):
        H = self._board_homography
        for d in detections:
            d["board_map"] = {"valid": False, "u": None, "v": None}
            if d.get("detection_type") == "base_board":
                continue
            if not self._board_initialized or H is None:
                continue
            bbox = d.get("bbox_xyxy")
            if not bbox:
                continue
            x1, y1, x2, y2 = [int(v) for v in bbox]
            fx = int((x1 + x2) / 2)
            fy = int(y2)
            u, v = image_point_to_board_uv(H, float(fx), float(fy))
            if u is None or v is None:
                continue
            d["board_map"] = {
                "valid": True,
                "u": max(0.0, min(1.0, u)),
                "v": max(0.0, min(1.0, v)),
                "image_foot_xy": [fx, fy],
            }

    def open(self, verbose: bool = False):
        if verbose:
            print("[DEBUG] Opening ZED camera for YOLO pipeline...")

        sl, cv2, np, yolo_cls = self._try_import_yolo_dependencies(verbose=verbose)
        if not sl or yolo_cls is None:
            if verbose:
                print("[DEBUG] Missing dependencies for YOLO pipeline")
            return False

        self._sl = sl
        self._cv2 = cv2
        self._np = np

        try:
            self._yolo = yolo_cls(self._resolve_yolo_model_name())
            try:
                torch_mod = importlib.import_module("torch")
                cuda_available = bool(torch_mod.cuda.is_available())
            except Exception:
                cuda_available = False
            self._yolo_device = 0 if cuda_available else "cpu"
            self._yolo_half = cuda_available
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Failed to initialize YOLO model: {e}")
            return False

        self._class_names = getattr(self._yolo, "names", {}) or {}
        self._zed = sl.Camera()
        if not self._try_open_camera_with_fallbacks():
            if verbose:
                print("[DEBUG] Failed to open camera with fallback attempts")
            return False

        tracking_params = sl.PositionalTrackingParameters()
        tracking_params.set_floor_as_origin = False
        status = self._zed.enable_positional_tracking(tracking_params)
        if status != sl.ERROR_CODE.SUCCESS:
            if verbose:
                print(f"[DEBUG] Failed to enable positional tracking for plane detection: {status}")
            self.close()
            return False

        self._runtime_params = sl.RuntimeParameters()
        self._point_cloud = sl.Mat()
        self._left_image = sl.Mat()
        self._depth_map = sl.Mat()

        self._load_calibration_roi(verbose=verbose)

        if verbose:
            print("[DEBUG] YOLO + ZED pipeline initialized")

        return True

    def _load_calibration_roi(self, verbose: bool = False):
        """Load saved calibration and turn the clicked points into an ROI.

        Sets:
            self._calib_polygon_xy : numpy (N, 2) float polygon in image space.
            self._calib_crop_xyxy  : (x1, y1, x2, y2) crop bbox with padding.
        """
        if self._np is None:
            return
        try:
            from vision.calibration import load_calibration
        except Exception:
            return
        path = self._calibration_path
        if not path or not os.path.isfile(path):
            if verbose:
                print(f"[DEBUG] No calibration at {path}; using full frame")
            return
        try:
            cal = load_calibration(path)
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Failed to load calibration: {e}")
            return

        pts = [(float(p.u), float(p.v)) for p in cal.points]
        if len(pts) < 3:
            return

        polygon = self._np.array(pts, dtype=self._np.float32)
        # Order points around the convex hull so cv2.pointPolygonTest gets a
        # well-formed polygon (operator click order may not be CCW/CW).
        if self._cv2 is not None:
            try:
                hull = self._cv2.convexHull(polygon)
                polygon = hull.reshape(-1, 2).astype(self._np.float32)
            except Exception:
                pass

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        pad = int(self._calib_padding_px)
        x1 = max(0, int(min(xs)) - pad)
        y1 = max(0, int(min(ys)) - pad)
        x2 = int(max(xs)) + pad
        y2 = int(max(ys)) + pad

        self._calib_polygon_xy = polygon
        self._calib_crop_xyxy = (x1, y1, x2, y2)
        if verbose:
            print(
                f"[DEBUG] Calibration ROI loaded: crop=({x1},{y1})->({x2},{y2}) "
                f"pts={len(pts)}"
            )

    def _crop_to_calibration_roi(self, frame):
        """Return (yolo_input, x_off, y_off). If no ROI, return original frame."""
        if self._calib_crop_xyxy is None:
            return frame, 0, 0
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = self._calib_crop_xyxy
        x1 = max(0, min(w - 1, int(x1)))
        y1 = max(0, min(h - 1, int(y1)))
        x2 = max(x1 + 1, min(w, int(x2)))
        y2 = max(y1 + 1, min(h, int(y2)))
        if x2 - x1 < 64 or y2 - y1 < 64:
            return frame, 0, 0
        return frame[y1:y2, x1:x2], x1, y1

    def _bbox_in_calibration_polygon(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Return True if the bbox center sits inside the calibration polygon.

        When no calibration is loaded, every detection counts as in zone.
        """
        if self._calib_polygon_xy is None or self._cv2 is None:
            return True
        cx = float((x1 + x2) / 2)
        cy = float((y1 + y2) / 2)
        try:
            return self._cv2.pointPolygonTest(
                self._calib_polygon_xy, (cx, cy), False
            ) >= 0
        except Exception:
            return True

    def _detect_support_plane(self, sl, pixel_x, pixel_y):
        # Prefer local plane at hit point under the detected object.
        plane = sl.Plane()
        if self._support_plane_mode == "floor":
            transform = sl.Transform()
            status = self._zed.find_floor_plane(plane, transform)
            if status != sl.ERROR_CODE.SUCCESS:
                return self._last_floor_plane
            plane_data = extract_plane_data(plane)
            self._last_floor_plane = plane_data
            self._last_floor_plane_ts = time.time()
            return plane_data

        try:
            hit = sl.uint2()
            hit[0] = int(pixel_x)
            hit[1] = int(pixel_y)
            status = self._zed.find_plane_at_hit(hit, plane)
            if status == sl.ERROR_CODE.SUCCESS:
                return extract_plane_data(plane)
        except Exception:
            return None
        return None

    def read(self):
        if not self._zed or not self._yolo:
            return None

        sl = self._sl
        if self._zed.grab(self._runtime_params) != sl.ERROR_CODE.SUCCESS:
            return None

        self._frame_index += 1

        self._zed.retrieve_image(self._left_image, sl.VIEW.LEFT, sl.MEM.CPU)

        rgba_frame = self._left_image.get_data()
        if rgba_frame is None:
            return None

        rgb_frame = self._rgba_to_bgr(rgba_frame)
        depth_frame = None
        if self._enable_depth_preview:
            self._zed.retrieve_measure(self._depth_map, sl.MEASURE.DEPTH, sl.MEM.CPU)
            depth_frame = self._depth_to_colormap(self._depth_map)

        should_run_yolo = (
            self._frame_index == 1
            or (self._frame_index % self._yolo_inference_every_n_frames == 0)
        )

        yolo_results = []
        crop_off_x, crop_off_y = 0, 0
        if should_run_yolo:
            self._zed.retrieve_measure(self._point_cloud, sl.MEASURE.XYZRGBA, sl.MEM.CPU)
            yolo_input, crop_off_x, crop_off_y = self._crop_to_calibration_roi(rgb_frame)
            yolo_input = self._yolo_preprocess(yolo_input)
            try:
                yolo_results = self._yolo.predict(
                    source=yolo_input,
                    conf=max(0.01, min(0.99, self.confidence / 100.0)),
                    imgsz=self._yolo_image_size,
                    device=self._yolo_device,
                    half=self._yolo_half,
                    verbose=False,
                )
            except Exception:
                yolo_results = []

        frame_payload = {
            "timestamp_unix": time.time(),
            "frame_index": self._frame_index,
            "detections": [],
        }

        overlay_detections = []
        overlay_types = frozenset({"produce", "human"})

        if should_run_yolo and yolo_results:
            result = yolo_results[0]
            boxes = getattr(result, "boxes", None)
            if boxes is not None:
                top_produce_idx = None
                top_produce_conf = -1.0
                for idx, box in enumerate(boxes):
                    cls_raw = float(box.cls[0]) if box.cls is not None else -1
                    cls_id = int(cls_raw)
                    source_label = str(self._class_names.get(cls_id, f"class_{cls_id}"))
                    detection_type, final_label = classify_yolo_label(source_label)
                    if detection_type == "skip":
                        continue

                    conf = float(box.conf[0]) * 100.0 if box.conf is not None else 0.0
                    # Per-class threshold: people are easy to spot at low conf
                    # which floods the overlay; gate them at a higher cutoff
                    # while letting weaker produce signals through.
                    if detection_type == "human" and conf < self._person_min_confidence:
                        continue
                    xyxy = box.xyxy[0].tolist() if box.xyxy is not None else [0, 0, 0, 0]
                    x1, y1, x2, y2 = [int(v) for v in xyxy]
                    # Remap from cropped ROI back to full-frame coordinates.
                    x1 += crop_off_x
                    x2 += crop_off_x
                    y1 += crop_off_y
                    y2 += crop_off_y
                    foot_x = int((x1 + x2) / 2)
                    foot_y = int(y2)

                    in_zone = self._bbox_in_calibration_polygon(x1, y1, x2, y2)
                    # Drop produce/object detections outside the work zone so the
                    # robot ignores random items in the room. Humans always pass
                    # through for safety overlay.
                    if not in_zone and detection_type not in ("human",):
                        continue

                    fallback = safe_point_at_pixel(self._point_cloud, sl, foot_x, foot_y)
                    if fallback is None:
                        px = py = pz = None
                        distance = None
                    else:
                        px, py, pz = fallback
                        distance = math.sqrt(px * px + py * py + pz * pz)

                    support_plane = None
                    if self._enable_support_plane and detection_type == "produce" and conf > top_produce_conf:
                        top_produce_conf = conf
                        top_produce_idx = idx

                    detection_record = {
                        "id": idx,
                        "label": final_label,
                        "source_label": source_label,
                        "detection_type": detection_type,
                        "confidence": to_builtin_float(conf),
                        "position_m": {
                            "x": to_builtin_float(px),
                            "y": to_builtin_float(py),
                            "z": to_builtin_float(pz),
                        },
                        "distance_m": to_builtin_float(distance),
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "in_work_zone": bool(in_zone),
                        "produce_kind": final_label if detection_type == "produce" else None,
                        "support_plane": support_plane,
                    }

                    frame_payload["detections"].append(detection_record)
                    if detection_type in overlay_types:
                        overlay_detections.append(detection_record)
                if self._enable_support_plane and top_produce_idx is not None:
                    for detection in frame_payload["detections"]:
                        if detection.get("id") != top_produce_idx:
                            continue
                        x1, y1, x2, y2 = detection.get("bbox_xyxy", [0, 0, 0, 0])
                        cx = int((x1 + x2) / 2)
                        detection["support_plane"] = self._detect_support_plane(sl, cx, int(y2))
                        break
            self._sync_board_state(frame_payload["detections"])
            self._apply_board_maps(frame_payload["detections"])
            self._last_detections = [dict(d) for d in frame_payload["detections"]]
        elif not should_run_yolo:
            frame_payload["detections"] = [dict(d) for d in self._last_detections]
            self._apply_board_maps(frame_payload["detections"])
            overlay_detections = [
                d for d in frame_payload["detections"] if d.get("detection_type") in overlay_types
            ]
        elif should_run_yolo:
            # Inference failed or returned nothing — keep prior detections so board mapping stays stable.
            frame_payload["detections"] = [dict(d) for d in self._last_detections]
            self._apply_board_maps(frame_payload["detections"])
            overlay_detections = [
                d for d in frame_payload["detections"] if d.get("detection_type") in overlay_types
            ]

        quad_serial = None
        if self._board_quad_corners is not None and self._np is not None:
            quad_serial = self._board_quad_corners.tolist()
        frame_payload["board"] = board_payload_from_state(
            self._board_initialized,
            quad_serial,
            self._board_homography,
        )

        annotated_frame = self._draw_yolo_overlay(rgb_frame, overlay_detections)

        if self.backend_url and (self._frame_index % self.backend_every_n_frames == 0):
            try:
                send_json_payload(self.backend_url, frame_payload, self.backend_timeout)
            except (urllib.error.URLError, TimeoutError, ValueError):
                now = time.time()
                if now - self._last_backend_error_ts > 2.0:
                    self._last_backend_error_ts = now

        return {
            "rgb": rgb_frame,
            "annotated_rgb": annotated_frame,
            "depth": depth_frame,
            "payload": frame_payload,
        }


