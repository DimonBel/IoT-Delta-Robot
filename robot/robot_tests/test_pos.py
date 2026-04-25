import serial
import time


def main() -> None:
    with serial.Serial(port="COM6", baudrate=115200, timeout=2) as ser:
        ser.write(b"Position\n")
        ser.flush()

        response = ser.readline().decode("utf-8", errors="replace").strip()
        print(response)


if __name__ == "__main__":
    main()
