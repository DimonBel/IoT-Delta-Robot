from __future__ import annotations
from pathlib import Path
from flask import Flask, jsonify, request

from robot_controller import RobotController


templates_dir = Path(__file__).parent
app = Flask(__name__)
rc: RobotController | None = None

PORT = "COM6" # windows
# PORT = "/dev/cu.usbmodem153408901" # macos

@app.get("/")
def index():
    return (templates_dir / "index.html").read_text(encoding="utf-8")


@app.post("/move")
def move():
    payload = request.get_json(silent=True) or {}
    axes = ["X", "Y", "Z", "U", "V", "W"]
    values = {axis: float(payload.get(axis, 0)) for axis in axes}
    values = {axis: int(round(value)) for axis, value in values.items()}
    move_args = ", ".join(f"{axis}={values[axis]:.2f}" for axis in axes)
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
    print("home: ok", flush=True)
    return jsonify({"status": "ok"})


def main() -> None:
    global rc
    with RobotController(port=PORT) as controller:
        rc = controller
        rc.set_motion(speed=50, acceleration=500)
        is_delta = rc.is_delta()
        print(f"isdelta resp: {is_delta}")

        pos = rc.get_position()
        print(f"pos response: {pos}")

        app.run(host="127.0.0.1", port=8001, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
