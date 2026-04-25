import time

import serial


# Movement config

# AXIS = "Z"
# FROM_POS = -738.0
# TO_POS = -980.0
# STEP_MM = 1.0

AXIS = "Y"
FROM_POS = -395
TO_POS = 395
STEP_MM = 5.0

# Fixed pose for axes that are not being swept.
INITIAL_POSE = {
    "X": -4.67,
    "Y": -5.81,
    "Z": -854.79, # half of Z limit
    "W": 45.0,
    "U": 45.0,
    "V": 45.0,
}


def read_burst(ser: serial.Serial, wait_s: float) -> list[str]:
    lines: list[str] = []
    deadline = time.monotonic() + wait_s

    while time.monotonic() < deadline:
        raw = ser.readline()
        if raw:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                lines.append(line)
                deadline = time.monotonic() + 0.25
        elif lines:
            break

    return lines


def send_and_print(ser: serial.Serial, cmd: str, wait_s: float = 2.0) -> list[str]:
    ser.write((cmd + "\n").encode("utf-8"))
    ser.flush()

    lines = read_burst(ser, wait_s=wait_s)
    if not lines:
        print(f"{cmd} -> <no response>")
        return lines

    for line in lines:
        print(f"{cmd} -> {line}")
    return lines


def build_positions(start: float, end: float, step_mm: float) -> list[float]:
    if step_mm <= 0:
        raise ValueError("STEP_MM must be greater than 0")

    direction = 1.0 if end >= start else -1.0
    step = step_mm * direction
    positions: list[float] = []
    value = start

    while (direction > 0 and value <= end + 1e-9) or (direction < 0 and value >= end - 1e-9):
        positions.append(round(value, 2))
        value += step

    if abs(positions[-1] - end) > 1e-9:
        positions.append(round(end, 2))

    return positions


def main() -> None:
    axis = AXIS.upper()
    if axis not in INITIAL_POSE:
        raise ValueError("AXIS must be one of X, Y, Z, W, U, V")

    sweep_positions = build_positions(FROM_POS, TO_POS, STEP_MM)

    with serial.Serial(port="COM6", baudrate=115200, timeout=0.3) as ser:
        send_and_print(ser, "IsDelta", wait_s=1.0)
        send_and_print(ser, "G90", wait_s=1.0)
        send_and_print(ser, "G28", wait_s=20.0)

        print(f"Sweeping axis {axis} from {FROM_POS:.2f} to {TO_POS:.2f} in {STEP_MM:.2f} mm steps")
        for pos in sweep_positions:
            pose = dict(INITIAL_POSE)
            pose[axis] = pos
            cmd = (
                f"G01 A500 F250 X{pose['X']:.2f} Y{pose['Y']:.2f} Z{pose['Z']:.2f} "
                f"W{pose['W']:.2f} U{pose['U']:.2f} V{pose['V']:.2f}"
            )
            send_and_print(ser, cmd, wait_s=2.0)
            # time.sleep(0.5)


if __name__ == "__main__":
    main()
