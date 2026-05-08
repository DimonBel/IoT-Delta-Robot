# Calibration markers — printing and placement

Short guide for the physical setup the calibration tool expects.

## What you need

- 9+ visually distinct dots/crosses arranged on a flat sheet.
- The exact spacing in mm is up to you, but the tool defaults assume a regular
  grid (e.g. 3x3 with 100 mm spacing).
- Tape it flat on the workspace under the camera.

## Recommended layout

A 3x3 grid with 100 mm spacing covers 200 x 200 mm centred on the robot origin:

```
   +Y
    |
    .   .   .       row 0  Y = +100
    .   .   .       row 1  Y =    0     ----- +X
    .   .   .       row 2  Y = -100
        c1  c2
   X:  -100   0  +100
```

The default `--grid 3x3 --spacing 100 --center-x 0 --center-y 0` matches this.

## Aligning the grid with the robot frame

The clicking order is **row-major from the top-left of the printed grid**, so
the printed grid's "rightward" direction must match the robot's +X axis, and
"downward on the print" must match the robot's -Y direction. (See diagram
above.)

If you cannot rotate the printout, rotate the targets instead by passing
different `--center-x / --center-y` and reordering the printed grid.

## Origin marker

Place one obvious origin mark at robot (0, 0) so you can centre the printout.
The simplest workflow:

1. Home the robot (`G28`).
2. Jog the end-effector to (0, 0) at some safe Z.
3. Drop a small piece of tape directly below the tool tip.
4. Tape the printed grid so its centre marker sits on that tape.

## After printing

1. Confirm the grid is flat — bumps and curls will cause non-trivial errors.
2. Confirm the spacing on paper with a ruler. Inkjet/laser printers can stretch
   1-2 % in one axis. If yours does, measure the actual mm and pass that to
   `--spacing`.
3. Run the UI:

   ```
   python -m vision.calibration_ui --live --grid 3x3 --spacing 100 \
       --out calibration/calibration.json
   ```

   or, with a saved photo:

   ```
   python -m vision.calibration_ui --image samples/top_down.jpg \
       --grid 3x3 --spacing 100 --out calibration/calibration.json
   ```

4. Click each marker in row-major order. Press `y` to confirm, `n` to redo,
   `q` to abort.

5. Inspect the printed RMS residual. < 3 mm is fine for picking apples.
