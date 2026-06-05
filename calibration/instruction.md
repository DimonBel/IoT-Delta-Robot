# 0) close ZED Explorer + anything else that holds the camera, replug USB 3.0

cd C:\Users\user\Desktop\IoT-Delta-Robot
.\venv\Scripts\activate

# 1) pull the new branch
git fetch origin
git checkout checkpoint-tracking
git pull

# 2) sanity tests (no camera)
python -m unittest tests.test_calibration tests.test_quality tests.test_tracker
#    expect: Ran 54 tests ... OK

# 3) confirm camera + SDK work
python -m tests.diagnose_zed

# 4) place the marker grid (3x3, 100 mm) on the board, centre marker at robot (0,0)
#    then calibrate (one ZED frame, click 9 markers, press y each time)
python -m vision.calibration.ui --live --grid 3x3 --spacing 100

# 5) verify calibration without the camera
python -m vision.calibration.verify --summary

# 6) run live with everything on
python -m vision.commands live --duration 30 --print-coordinates
While it runs:

Watch the OpenCV window. Each fruit gets a red dot + red cross at its centre, with #N X:+.. Y:+.. mm written next to it in red.
Watch the terminal. Per detected fruit: track id, 3D, board mm, quality grade.
In a second PowerShell, peek at the saved file:

type outputs\latest_tracks.json
It updates every 10 frames.
Press q in the OpenCV window to exit.

Useful one-off variants

# more aggressive small-fruit recall (slower)
python -m vision.commands live --imgsz 1024 --confidence 20 --print-coordinates

# tighter ID matching (fruits won't get reassigned if they wiggle)
python -m vision.commands live --tracker-radius-mm 25

# disable tracker entirely (no track_id, no outputs/ files)
python -m vision.commands live --no-tracking

# faster snapshot updates if the robot side polls often
python -m vision.commands live --tracker-snapshot-every 3

# the opposite: only write every 30 frames (= ~1 Hz at 30 fps)
python -m vision.commands live --tracker-snapshot-every 30
If the red dot isn't on the fruit middle
That means refined_detection_center's silhouette fit fell back (low saturation / weird lighting). Two levers, in order:

--enhance — turn on CLAHE so saturation is stronger.
Tighten the refined_detection_center thresholds (HSV-S Otsu) — needs a code tweak; ping me with a photo and I'll dial it in.