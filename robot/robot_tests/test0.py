import serial
import time

# работает как надо, идёт спокойно по треугольнику
def main() -> None:
    with serial.Serial(port="COM6", baudrate=115200, timeout=2) as ser:
        # ser.write(b"G28\n")
        time.sleep(1)
        
        for _ in range(5):
            ser.write(b"G01 A1000 F100 X-100 Y-100 Z-850\n")
            time.sleep(0.5)
            ser.write(b"G01 A1000 F100 X100 Y100 Z-860\n")
            time.sleep(0.5)
            ser.write(b"G01 A1000 F100 X-50 Y-50 Z-750\n")
            time.sleep(0.5)
            ser.write(b"G01 A1000 F100 X-300 Y300 Z-850\n")
            time.sleep(0.5)
            
        ser.flush()

        response = ser.readline().decode("utf-8", errors="replace").strip()
        print(response)


if __name__ == "__main__":
    main()
