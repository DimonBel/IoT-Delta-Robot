import serial

def main() -> None:
    with serial.Serial(port="COM6", baudrate=115200, timeout=2) as ser:
        ser.write(b"G28\n")
        ser.flush()

        response = ser.readline().decode("utf-8", errors="replace").strip()
        print(response)


if __name__ == "__main__":
    main()
