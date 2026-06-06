from __future__ import annotations
import sys
import threading
import time
import urllib.request
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_from_directory

from robot_controller import RobotController


project_root = Path(__file__).resolve().parents[2]
frontend_dist = project_root / "front" / "dist"
sys.path.insert(0, str(project_root))

app = Flask(__name__, static_folder=str(frontend_dist), static_url_path="")
rc: RobotController | None = None

# --- Vision / detection streaming ---

# Produce detections stick on the UI for 30 s after the last sighting (FruitTracker
# keeps them alive across brief YOLO misses). Person detections are stripped from
# /detections entirely and surfaced via /person-warning instead.
STICKY_SECONDS = 30.0
PERSON_HOLD_SECONDS = 4.0

_vision = None
_latest_detections: list = []
_detection_lock = threading.Lock()

_latest_frame_jpeg: bytes | None = None
_frame_lock = threading.Lock()

_person_warning = {"active": False, "last_seen_ts": 0.0, "count": 0}
_person_lock = threading.Lock()

try:
    import cv2 as _cv2
except ImportError:
    _cv2 = None  # type: ignore

try:
    from vision.vision import ImageRecognition as _IR  # type: ignore
    _vision = _IR(auto_start=True)
except Exception as _vision_init_err:
    print(f"Camera vision not available: {_vision_init_err}")

# Calibrator: maps image pixels → robot-frame mm (board_xy_mm).
# ZEDYoloVisionPipeline.read() does NOT populate board_xy_mm itself —
# that requires the polynomial fit stored in calibration.json.
_calibrator = None
try:
    from vision.calibration import Calibrator as _Cal  # type: ignore
    from vision.commands import _annotate_board_mm as _annotate_brd  # type: ignore
    _calibrator = _Cal.load(str(project_root / "calibration" / "calibration.json"))
    print(f"Calibration loaded  image_size={_calibrator.image_size}")
except Exception as _cal_err:
    print(f"Calibration not available: {_cal_err}")

# Sticky produce tracker. max_age_frames=200 (~40 s at the 0.2 s loop period) is
# safely larger than STICKY_SECONDS; the time filter below is the contract.
try:
    from vision.tracker import FruitTracker as _FruitTracker  # type: ignore
    _tracker: "_FruitTracker | None" = _FruitTracker(max_age_frames=200)
except Exception as _trk_err:
    _tracker = None
    print(f"Tracker not available: {_trk_err}")


def _vision_loop() -> None:
    while True:
        try:
            if _vision is not None:
                frame = _vision.get_frame()
                if frame:
                    payload = frame.get("payload", {})
                    dets = payload.get("detections", [])

                    # Populate board_xy_mm via the saved polynomial calibration.
                    # Without this call every detection has board_xy_mm = None.
                    if _calibrator is not None and dets:
                        rgb = frame.get("rgb")
                        _annotate_brd(dets, _calibrator, _calibrator.image_size, rgb_frame=rgb)

                    # --- split by detection_type ---
                    now = time.time()
                    frame_index = int(payload.get("frame_index", 0) or 0)
                    produce_dets = [d for d in dets if d.get("detection_type") == "produce"]
                    person_dets = [d for d in dets if d.get("detection_type") == "human"]

                    # Feed produce through the tracker so brief YOLO misses don't
                    # make the icon flicker off the grid.
                    if _tracker is not None:
                        _tracker.update(produce_dets, frame_index, now)

                    # --- detections for the grid ---
                    formatted: list = []

                    # Sticky produce: emit tracks last seen within STICKY_SECONDS.
                    if _tracker is not None:
                        for t in _tracker.tracks.values():
                            if now - t.last_seen_ts > STICKY_SECONDS:
                                continue
                            formatted.append({
                                "id": int(t.track_id),
                                "label": t.label,
                                "x_mm": round(float(t.x_mm), 1),
                                "y_mm": round(float(t.y_mm), 1),
                                "confidence": round(float(t.confidence), 1),
                            })

                    # Non-produce, non-human detections pass through fresh (no
                    # stickiness): base_board, delta_robot, generic object.
                    for d in dets:
                        dtype = d.get("detection_type")
                        if dtype == "produce" or dtype == "human":
                            continue
                        bxy = d.get("board_xy_mm") or {}
                        x = bxy.get("x")
                        y = bxy.get("y")
                        if x is None or y is None:
                            continue
                        formatted.append({
                            "id": int(d.get("id", 0) or 0),
                            "label": d.get("label", "object"),
                            "x_mm": round(float(x), 1),
                            "y_mm": round(float(y), 1),
                            "confidence": round(float(d.get("confidence", 0)), 1),
                        })

                    with _detection_lock:
                        _latest_detections[:] = formatted

                    # --- person warning state (refresh only on positive frames;
                    # the endpoint applies the PERSON_HOLD_SECONDS time gate) ---
                    if person_dets:
                        with _person_lock:
                            _person_warning["active"] = True
                            _person_warning["last_seen_ts"] = now
                            _person_warning["count"] = len(person_dets)

                    # --- camera snapshot (annotated frame with YOLO boxes) ---
                    if _cv2 is not None:
                        img = frame.get("annotated_rgb")
                        if img is None:
                            img = frame.get("rgb")
                        if img is not None:
                            ok, buf = _cv2.imencode(".jpg", img, [_cv2.IMWRITE_JPEG_QUALITY, 75])
                            if ok:
                                with _frame_lock:
                                    _latest_frame_jpeg = buf.tobytes()
        except Exception as _loop_err:
            print(f"vision loop error: {_loop_err}")
        time.sleep(0.2)


threading.Thread(target=_vision_loop, daemon=True).start()

PORT = "COM11" # windows
# PORT = "/dev/cu.usbmodem153408901" # macos

@app.get("/")
def index():
    return send_from_directory(frontend_dist, "index.html")


@app.get("/<path:path>")
def static_files(path: str):
    return send_from_directory(frontend_dist, path)


@app.post("/move")
def move():
    payload = request.get_json(silent=True) or {}
    axes = ["X", "Y", "Z", "U", "V", "W"]
    raw_values = {axis: float(payload.get(axis, 0)) for axis in axes}
    values = {axis: int(round(raw_values[axis])) for axis in axes}
    move_args = ", ".join(f"{axis}={values[axis]:.0f}" for axis in axes)
    if rc is None:
        return jsonify({"status": "error", "error": "robot not ready"}), 503

    print(f"calling move_to({move_args})", flush=True)

    rc.move_to(
        X=values["X"],
        Y=values["Y"],
        Z=values["Z"],
        U=values["U"],
        V=values["V"],
        W=values["W"],
    )

    return jsonify({"status": "ok", "values": values})


@app.post("/is_delta")
def is_delta():
    if rc is None:
        return jsonify({"status": "error", "error": "robot not ready"}), 503

    result = rc.is_delta()
    print(f"is_delta result: {result}", flush=True)
    return jsonify({"status": "ok", "is_delta": result})


@app.get("/position")
def position():
    if rc is None:
        return jsonify({"status": "error", "error": "robot not ready"}), 503

    axes = ["X", "Y", "Z", "U", "V", "W"]
    values_list = rc.get_position()
    values = {axis: float(values_list[index]) for index, axis in enumerate(axes)}
    print(f"position: {values}", flush=True)
    return jsonify({"status": "ok", "values": values})


@app.post("/home")
def home():
    if rc is None:
        return jsonify({"status": "error", "error": "robot not ready"}), 503

    rc.send_axes_home(X=True, Y=True, Z=True, U=True, V=True, W=True)
    values_list = rc.get_position()
    axes = ["X", "Y", "Z", "U", "V", "W"]
    values = {axis: float(values_list[index]) for index, axis in enumerate(axes)}
    print(f"home: ok ({values})", flush=True)
    return jsonify({"status": "ok", "values": values})


@app.post("/motion")
def motion():
    if rc is None:
        return jsonify({"status": "error", "error": "robot not ready"}), 503

    payload = request.get_json(silent=True) or {}
    speed = payload.get("speed")
    acceleration = payload.get("acceleration")

    rc.set_motion(
        speed=float(speed) if speed is not None else None,
        acceleration=float(acceleration) if acceleration is not None else None,
    )

    return jsonify({"status": "ok", "speed": speed, "acceleration": acceleration})


CAMERA_STREAM_URL = "https://freely-mandolin-ladder.ngrok-free.dev/video"


@app.get("/camera-proxy")
def camera_proxy():
    try:
        upstream = urllib.request.urlopen(
            urllib.request.Request(
                CAMERA_STREAM_URL,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "ngrok-skip-browser-warning": "true",
                },
            ),
            timeout=10,
        )
        content_type = upstream.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame")

        def stream():
            try:
                with upstream:
                    while True:
                        chunk = upstream.read(8192)
                        if not chunk:
                            break
                        yield chunk
            except Exception as e:
                print(f"camera proxy stream ended: {e}")

        return Response(stream(), mimetype=content_type, headers={"Cache-Control": "no-cache"})
    except Exception as e:
        return Response(f"camera unavailable: {e}", status=503)


@app.get("/snapshot")
def snapshot():
    with _frame_lock:
        data = _latest_frame_jpeg
    if data is None:
        return Response(status=204)
    return Response(data, mimetype="image/jpeg", headers={"Cache-Control": "no-cache, no-store"})


@app.get("/debug-detections")
def debug_detections():
    vision_ok = _vision is not None
    raw_dets = []
    if vision_ok:
        try:
            frame = _vision.get_frame()
            if frame:
                raw_dets = frame.get("payload", {}).get("detections", [])
        except Exception as e:
            raw_dets = [{"error": str(e)}]
    with _detection_lock:
        formatted = list(_latest_detections)
    return jsonify({
        "vision_initialized": vision_ok,
        "raw_detection_count": len(raw_dets),
        "raw_detections": raw_dets,
        "formatted_detections": formatted,
    })


@app.get("/detections")
def get_detections():
    with _detection_lock:
        snapshot = list(_latest_detections)
    return jsonify(snapshot)


@app.get("/person-warning")
def person_warning():
    with _person_lock:
        state = dict(_person_warning)
    now = time.time()
    last_seen = float(state.get("last_seen_ts") or 0.0)
    active = bool(state.get("active")) and last_seen > 0.0 and (now - last_seen) <= PERSON_HOLD_SECONDS
    return jsonify({
        "active": active,
        "last_seen_ts": last_seen,
        "seconds_since": round(now - last_seen, 1) if last_seen > 0.0 else None,
        "count": int(state.get("count", 0)) if active else 0,
    })


def main() -> None:
    global rc
    with RobotController(port=PORT) as controller:
        rc = controller
        rc.set_motion(speed=50, acceleration=500)

        try:
            is_delta = rc.is_delta()
            print(f"isdelta resp: {is_delta}")
        except Exception as e:
            print(f"is_delta check failed (continuing): {e}")

        try:
            pos = rc.get_position()
            print(f"pos response: {pos}")
        except Exception as e:
            print(f"get_position check failed (continuing): {e}")

        app.run(host="127.0.0.1", port=8001, debug=True, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
