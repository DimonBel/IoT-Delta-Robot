(venv) PS C:\Users\user\Desktop\IoT-Delta-Robot> python -m vision.calibration.ui --live --live-preview --side 920 --home-x 0 --home-y 0
>> 
[2026-05-26 15:20:11 UTC][ZED][INFO] Logging level INFO
[2026-05-26 15:20:14 UTC][ZED][INFO] [Init]  Camera successfully opened.
[2026-05-26 15:20:14 UTC][ZED][INFO] [Init]  Camera FW version: 1523
[2026-05-26 15:20:14 UTC][ZED][INFO] [Init]  Video mode: HD720@30
[2026-05-26 15:20:14 UTC][ZED][INFO] [Init]  Serial Number: S/N 34491368
[2026-05-26 15:20:14 UTC][ZED][WARNING] [Init]  ULTRA is deprecated. Please update your configuration to use NEURAL instead.
Calib camera: aim the board, click the image window, then SPACE or C to capture, Q to abort.
6-click calibration: side=920 mm, home=(0, 0) mm. Square is centred at robot origin (0, 0).
Click each stage in order; press Y/Enter to confirm, N to redo, Q to abort.
  1/6  Corner at (-X, -Y)
  2/6  Corner at (-X, +Y)
  3/6  Corner at (+X, -Y)
  4/6  Helper on the +X edge (between (+X,-Y) and hidden (+X,+Y))
  5/6  Helper on the +Y edge (between (-X,+Y) and hidden (+X,+Y))
  6/6  ROBOT HOME (gripper position; mm given by --home-x / --home-y)
Inferred (+X, +Y) corner pixel: (568.9, 1356.9)
Saved calibration to calibration/calibration.json
  fit: poly1, RMS residual: 186.55 mm
  work zone (mm): X[-280, 280] Y[-280, 280]
  robot home (mm): X=0  Y=0
  result image: C:\Users\user\Desktop\IoT-Delta-Robot\calibration\calibration_result.png
(venv) PS C:\Users\user\Desktop\IoT-Delta-Robot> python -m vision.commands live --print-coordinates                                    
<frozen runpy>:128: RuntimeWarning: 'vision.commands' found in sys.modules after import of package 'vision', but prior to execution of 'vision.commands'; this may result in unpredictable behaviour
Loaded calibration: poly1, image 1280x720, RMS 186.55 mm
Initializing vision system... (imgsz=832, conf>=25%, person>=40%, enhance=off, quality=on, tracking=on)
[2026-05-26 15:21:01 UTC][ZED][INFO] Logging level INFO
[2026-05-26 15:21:04 UTC][ZED][INFO] [Init]  Camera successfully opened.
[2026-05-26 15:21:04 UTC][ZED][INFO] [Init]  Camera FW version: 1523
[2026-05-26 15:21:04 UTC][ZED][INFO] [Init]  Video mode: HD720@30
[2026-05-26 15:21:04 UTC][ZED][INFO] [Init]  Serial Number: S/N 34491368
[2026-05-26 15:21:04 UTC][ZED][WARNING] [Init]  ULTRA is deprecated. Please update your configuration to use NEURAL instead.
[Frame 1] person (67.12%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-631.7 Y:+235.6 (outside)
[Frame 2] person (47.01%)
  X:-0.13m Y:-0.16m Z:-0.93m
  board (mm) X:-72.8 Y:-282.1 (outside)
[Frame 3] person (50.67%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-541.2 Y:+131.0 (outside)
[Frame 4] person (55.41%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-646.8 Y:+242.6 (outside)
[Frame 5] person (43.68%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-560.5 Y:+109.9 (outside)
[Frame 6] person (65.50%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-545.0 Y:+132.4 (outside)
[Frame 7] person (71.43%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-652.3 Y:+243.0 (outside)
[Frame 8] person (68.51%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-656.5 Y:+242.4 (outside)
[Frame 9] person (60.20%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-530.9 Y:+123.9 (outside)
[Frame 10] person (61.38%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-531.0 Y:+124.0 (outside)
[Frame 11] person (67.24%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-529.5 Y:+125.4 (outside)
[Frame 12] person (64.80%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-646.2 Y:+243.4 (outside)
[Frame 13] person (64.92%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-646.2 Y:+242.1 (outside)
[Frame 14] person (70.95%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-644.7 Y:+242.9 (outside)
[Frame 15] person (70.53%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-552.1 Y:+100.5 (outside)
[Frame 16] person (68.63%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-648.4 Y:+244.5 (outside)
[Frame 17] person (70.92%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-648.6 Y:+244.0 (outside)
[Frame 18] person (58.29%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-524.6 Y:+122.4 (outside)
[Frame 19] person (59.77%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-647.1 Y:+243.5 (outside)
[Frame 20] person (68.01%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-646.8 Y:+242.9 (outside)
[Frame 21] person (68.29%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-646.0 Y:+245.2 (outside)
[Frame 22] person (73.63%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-525.8 Y:+127.1 (outside)
[Frame 23] person (71.18%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-563.4 Y:+111.4 (outside)
[Frame 24] person (70.21%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-647.8 Y:+245.3 (outside)
[Frame 25] person (74.59%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-648.6 Y:+244.0 (outside)
[Frame 26] person (65.78%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-557.9 Y:+113.0 (outside)
[Frame 27] person (78.19%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-543.0 Y:+123.9 (outside)
[Frame 28] person (72.65%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-562.6 Y:+110.3 (outside)
[Frame 29] person (75.58%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-649.9 Y:+245.0 (outside)
[Frame 30] person (77.49%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-561.1 Y:+117.0 (outside)
[Frame 31] person (62.95%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-642.9 Y:+244.1 (outside)
[Frame 32] person (56.09%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-565.6 Y:+114.1 (outside)
[Frame 33] person (56.46%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-563.0 Y:+119.0 (outside)
[Frame 34] person (57.58%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-560.4 Y:+109.5 (outside)
[Frame 36] person (46.30%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-592.6 Y:+134.0 (outside)
[Frame 37] person (45.63%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-165.7 Y:-148.5 (inside)
[Frame 38] person (51.00%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-643.8 Y:+244.1 (outside)
[Frame 39] person (57.73%)
  X:0.20m Y:-0.10m Z:-0.94m
  board (mm) X:-399.9 Y:-65.3 (outside)
[Frame 40] person (54.99%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-645.3 Y:+243.3 (outside)
[Frame 41] person (54.55%)
  X:3.58m Y:-1.41m Z:-5.56m
  board (mm) X:-645.0 Y:+243.8 (outside)
[Frame 42] person (51.79%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-647.6 Y:+243.3 (outside)
[Frame 43] person (43.49%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-645.0 Y:+243.8 (outside)
[Frame 44] person (55.99%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-645.3 Y:+243.3 (outside)
[Frame 45] person (50.02%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-559.1 Y:+100.5 (outside)
[Frame 46] person (67.09%)
  X:-0.12m Y:-0.24m Z:-0.80m
  board (mm) X:-14.2 Y:-273.6 (inside)
[Frame 47] person (53.64%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-525.5 Y:+123.0 (outside)
[Frame 48] person (80.22%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-387.1 Y:-75.6 (outside)
[Frame 49] person (83.67%)
  X:-0.16m Y:-0.26m Z:-0.75m
  board (mm) X:+86.5 Y:-475.3 (outside)
[Frame 50] person (92.33%)
  X:-0.20m Y:-0.25m Z:-0.72m
  board (mm) X:+121.4 Y:-500.0 (outside)
[Frame 51] person (90.13%)
  X:-0.23m Y:-0.25m Z:-0.71m
  board (mm) X:+132.2 Y:-507.9 (outside)
[Frame 52] person (91.73%)
  X:-0.24m Y:-0.25m Z:-0.71m
  board (mm) X:+133.8 Y:-508.5 (outside)
[Frame 53] person (92.58%)
  X:-0.24m Y:-0.25m Z:-0.71m
  board (mm) X:+135.0 Y:-509.4 (outside)
[Frame 54] person (90.85%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:+135.0 Y:-509.4 (outside)
[Frame 55] person (90.98%)
  X:-0.24m Y:-0.27m Z:-0.67m
  board (mm) X:+128.4 Y:-502.3 (outside)
[Frame 56] person (92.60%)
  X:-0.22m Y:-0.29m Z:-0.65m
  board (mm) X:+124.5 Y:-501.1 (outside)
[Frame 57] person (92.37%)
  X:-0.22m Y:-0.29m Z:-0.65m
  board (mm) X:+123.8 Y:-500.6 (outside)
[Frame 58] person (91.65%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:+129.4 Y:-505.1 (outside)
[Frame 59] apple (68.17%) track #4
  X:-0.06m Y:-0.31m Z:-0.70m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 60] apple (65.94%) track #4
  X:-0.06m Y:-0.31m Z:-0.70m
  board (mm) X:+6.2 Y:-90.6 (inside)
  quality: excellent (defect 0.00)
[Frame 61] apple (66.34%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 62] apple (68.79%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 63] apple (71.87%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 64] apple (70.52%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 65] apple (73.77%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 66] apple (74.96%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 67] apple (72.21%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 68] apple (72.93%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 69] apple (72.45%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 70] apple (70.95%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 71] apple (70.62%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 72] person (75.24%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:+60.0 Y:-432.6 (outside)
[Frame 73] person (81.26%)
  X:-0.17m Y:-0.20m Z:-0.86m
  board (mm) X:-69.4 Y:-349.2 (outside)
[Frame 74] apple (70.52%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 75] apple (72.82%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 76] apple (71.79%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 77] apple (71.64%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 78] apple (70.09%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 79] person (78.19%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-539.4 Y:+134.9 (outside)
[Frame 80] apple (74.78%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 81] apple (72.99%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 82] apple (68.77%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 83] apple (72.02%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 84] person (77.54%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-528.7 Y:+114.0 (outside)
[Frame 85] person (72.65%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-566.3 Y:+170.8 (outside)
[Frame 86] person (78.27%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-565.8 Y:+177.2 (outside)
[Frame 87] person (78.75%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-603.0 Y:+170.2 (outside)
[Frame 88] person (74.17%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-603.8 Y:+177.3 (outside)
[Frame 89] person (80.90%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-603.0 Y:+186.8 (outside)
[Frame 90] person (77.09%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-546.3 Y:+110.4 (outside)
[Frame 91] person (74.55%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-538.6 Y:+127.4 (outside)
[Frame 92] apple (69.55%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 93] person (77.78%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-531.8 Y:+117.0 (outside)
[Frame 94] person (78.03%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-557.2 Y:+106.8 (outside)
[Frame 95] person (75.53%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-582.8 Y:+157.9 (outside)
[Frame 96] person (76.08%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-553.3 Y:+97.1 (outside)
[Frame 97] person (77.91%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-528.3 Y:+114.6 (outside)
[Frame 98] person (78.58%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-532.2 Y:+117.8 (outside)
[Frame 99] person (80.92%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-545.9 Y:+105.2 (outside)
[Frame 100] person (74.04%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-526.3 Y:+111.1 (outside)
[Frame 101] person (78.28%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-528.7 Y:+116.3 (outside)
[Frame 102] apple (68.30%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 103] person (79.82%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-576.9 Y:+179.6 (outside)
[Frame 104] person (71.40%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-540.4 Y:+123.9 (outside)
[Frame 105] apple (73.95%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 106] person (79.18%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-553.3 Y:+121.3 (outside)
[Frame 107] person (77.75%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-560.2 Y:+107.8 (outside)
[Frame 108] person (74.53%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-557.5 Y:+105.0 (outside)
[Frame 109] apple (70.86%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 110] apple (73.04%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.3 Y:-94.3 (inside)
  quality: excellent (defect 0.00)
[Frame 111] apple (64.89%) track #4
  X:-0.06m Y:-0.31m Z:-0.69m
  board (mm) X:-1.9 Y:-93.8 (inside)
  quality: excellent (defect 0.00)
[Frame 112] person (76.91%)
  X:n/a Y:n/a Z:n/a
  board (mm) X:-536.1 Y:+112.3 (outside)