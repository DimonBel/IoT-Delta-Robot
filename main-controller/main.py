import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from vision import ImageRecognition
from robot import RobotController


app = FastAPI()
templates = Jinja2Templates(directory="templates")

vision = ImageRecognition()
robot = RobotController()

auto_running = False
auto_thread = None


def automatic_loop():
    global auto_running

    print("Automatic loop started")

    while auto_running:
        try:
            frame = vision.get_frame()
            detection = vision.analyze(frame)

            if detection:
                robot.move_to(
                    detection["x"],
                    detection["y"],
                    detection["z"]
                )
                robot.pick()

        except Exception as e:
            print("Loop error:", e)

        time.sleep(0.1)

    print("Automatic loop stopped")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.post("/start")
def start_auto():
    global auto_running, auto_thread

    if auto_running:
        return {"status": "already running"}

    auto_running = True
    auto_thread = threading.Thread(
        target=automatic_loop,
        daemon=True
    )
    auto_thread.start()

    return {"status": "started"}


@app.post("/stop")
def stop_auto():
    global auto_running
    auto_running = False
    return {"status": "stopping"}


@app.get("/status")
def status():
    return JSONResponse({
        "status": "running" if auto_running else "idle"
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)