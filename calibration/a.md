(venv) PS C:\Users\user\Desktop\IoT-Delta-Robot> ^C
(venv) PS C:\Users\user\Desktop\IoT-Delta-Robot> python -m vision.commands live --print-coordinates
<frozen runpy>:128: RuntimeWarning: 'vision.commands' found in sys.modules after import of package 'vision', but prior to execution of 'vision.commands'; this may result in unpredictable behaviour
Loaded calibration: poly1, image 1280x720, RMS 200.90 mm
Initializing vision system... (imgsz=832, conf>=25%, person>=40%, enhance=off, quality=on, tracking=on)
[2026-05-26 14:14:14 UTC][ZED][INFO] Logging level INFO
[2026-05-26 14:14:16 UTC][ZED][INFO] [Init]  Camera successfully opened.
[2026-05-26 14:14:16 UTC][ZED][INFO] [Init]  Camera FW version: 1523
[2026-05-26 14:14:16 UTC][ZED][INFO] [Init]  Video mode: HD720@30
[2026-05-26 14:14:16 UTC][ZED][INFO] [Init]  Serial Number: S/N 34491368
[2026-05-26 14:14:16 UTC][ZED][WARNING] [Init]  ULTRA is deprecated. Please update your configuration to use NEURAL instead.
[Frame 1] person (81.05%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-573.8 Y:+175.0 (outside)
[Frame 2] apple (79.32%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-20.8 Y:-103.6 (inside)
  quality: excellent (defect 0.00)
[Frame 3] apple (81.38%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-20.2 Y:-103.7 (inside)
  quality: excellent (defect 0.00)
[Frame 4] apple (81.57%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-24.6 Y:-99.9 (inside)
  quality: excellent (defect 0.00)
[Frame 5] apple (80.98%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-21.3 Y:-101.9 (inside)
  quality: excellent (defect 0.00)
[Frame 6] apple (77.18%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-24.8 Y:-99.5 (inside)
  quality: excellent (defect 0.00)
[Frame 7] person (87.29%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-574.4 Y:+175.6 (outside)
[Frame 8] person (85.81%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-574.4 Y:+175.6 (outside)
[Frame 9] person (84.87%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-573.9 Y:+176.4 (outside)
[Frame 10] apple (83.41%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-24.5 Y:-100.1 (inside)
  quality: excellent (defect 0.00)
[Frame 11] apple (80.43%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-20.2 Y:-103.9 (inside)
  quality: excellent (defect 0.00)
[Frame 12] person (86.58%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-491.2 Y:+201.8 (outside)
[Frame 13] apple (82.08%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-22.6 Y:-104.1 (inside)
  quality: excellent (defect 0.00)
[Frame 14] person (84.08%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-575.1 Y:+176.1 (outside)
[Frame 15] apple (80.64%) track #1
  X:-0.05m Y:-0.31m Z:-0.70m
  board (mm) X:-20.6 Y:-103.7 (inside)
  quality: excellent (defect 0.00)
[Frame 16] apple (78.94%) track #1
  X:-0.05m Y:-0.31m Z:-0.70m
  board (mm) X:-19.5 Y:-104.1 (inside)
  quality: excellent (defect 0.00)
[Frame 17] apple (78.97%) track #1
  X:-0.05m Y:-0.31m Z:-0.70m
  board (mm) X:-19.9 Y:-104.6 (inside)
  quality: excellent (defect 0.00)
[Frame 18] apple (81.26%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-23.6 Y:-101.4 (inside)
  quality: excellent (defect 0.00)
[Frame 19] apple (80.77%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-18.9 Y:-103.4 (inside)
  quality: excellent (defect 0.00)
[Frame 20] person (84.17%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-554.9 Y:+143.1 (outside)
[Frame 21] person (82.72%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-554.6 Y:+143.6 (outside)
[Frame 22] apple (77.23%) track #1
  X:-0.05m Y:-0.31m Z:-0.69m
  board (mm) X:-21.1 Y:-103.4 (inside)
  quality: excellent (defect 0.00)
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\user\Desktop\IoT-Delta-Robot\vision\commands.py", line 764, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "C:\Users\user\Desktop\IoT-Delta-Robot\vision\commands.py", line 705, in main
    return 0 if run_live_vision(
                ~~~~~~~~~~~~~~~^
        duration_seconds=args.duration,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<17 lines>...
        tracker_max_age_frames=args.tracker_max_age_frames,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ) else 1
    ^
  File "C:\Users\user\Desktop\IoT-Delta-Robot\vision\commands.py", line 340, in run_live_vision
    vision.stop()
    ~~~~~~~~~~~^^
  File "C:\Users\user\Desktop\IoT-Delta-Robot\vision\vision.py", line 71, in stop
    self._zed_pipeline.close()
    ~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "C:\Users\user\Desktop\IoT-Delta-Robot\vision\vision.py", line 518, in close
    self._zed.close()
    ~~~~~~~~~~~~~~~^^
KeyboardInterrupt
(venv) PS C:\Users\user\Desktop\IoT-Delta-Robot> python -m vision.calibration.ui --live --live-preview --side 980
[2026-05-26 14:18:25 UTC][ZED][INFO] Logging level INFO
[2026-05-26 14:18:27 UTC][ZED][INFO] [Init]  Camera successfully opened.
[2026-05-26 14:18:27 UTC][ZED][INFO] [Init]  Camera FW version: 1523
[2026-05-26 14:18:27 UTC][ZED][INFO] [Init]  Video mode: HD720@30
[2026-05-26 14:18:27 UTC][ZED][INFO] [Init]  Serial Number: S/N 34491368
[2026-05-26 14:18:27 UTC][ZED][WARNING] [Init]  ULTRA is deprecated. Please update your configuration to use NEURAL instead.
Calib camera: aim the board, click the image window, then SPACE or C to capture, Q to abort.
6-click calibration: side=980 mm, home=(0, 0) mm. Square is centred at robot origin (0, 0).
Click each stage in order; press Y/Enter to confirm, N to redo, Q to abort.
  1/6  Corner at (-X, -Y)
  2/6  Corner at (-X, +Y)
  3/6  Corner at (+X, -Y)
  4/6  Helper on the +X edge (between (+X,-Y) and hidden (+X,+Y))
  5/6  Helper on the +Y edge (between (-X,+Y) and hidden (+X,+Y))
  6/6  ROBOT HOME (gripper position; mm given by --home-x / --home-y)
Inferred (+X, +Y) corner pixel: (540.3, 1442.3)
Saved calibration to calibration/calibration.json
  fit: poly1, RMS residual: 201.78 mm
  work zone (mm): X[-280, 280] Y[-280, 280]
  robot home (mm): X=0  Y=0
  result image: C:\Users\user\Desktop\IoT-Delta-Robot\calibration\calibration_result.png