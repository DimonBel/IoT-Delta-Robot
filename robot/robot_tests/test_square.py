import serial
import time

# этот код его сломал. почему??? да хрен его знает
def main() -> None:
    with serial.Serial(port="COM6", baudrate=115200, timeout=2) as ser:
        ser.write(b"G28 A1000 F50\n")
        time.sleep(1)
        ser.write(b"G90\n")
        time.sleep(1)
        
        for _ in range(1):
            ser.write(b"G01 X380 Y380 Z-960\n")
            time.sleep(0.5)
            ser.write(b"G01 X380 Y380 Z-750\n")
            time.sleep(0.5)
            ser.write(b"G01 X380 Y380 Z-960\n")
            time.sleep(0.5)
            
            ser.write(b"G01 X-380 Y380 Z-960\n")
            time.sleep(0.5)
            ser.write(b"G01 X-380 Y380 Z-750\n")
            time.sleep(0.5)
            ser.write(b"G01 X-380 Y380 Z-960\n")
            time.sleep(0.5)
            
            ser.write(b"G01 X-380 Y-380 Z-960\n")
            time.sleep(0.5)
            ser.write(b"G01 X-380 Y-380 Z-750\n")
            time.sleep(0.5)
            ser.write(b"G01 X-380 Y-380 Z-960\n")
            time.sleep(0.5)
            
            ser.write(b"G01 X380 Y-380 Z-960\n")
            time.sleep(0.5)
            ser.write(b"G01 X380 Y-380 Z-750\n")
            time.sleep(0.5)
            ser.write(b"G01 X380 Y-380 Z-960\n")
            time.sleep(0.5)
            
        ser.flush()

        response = ser.readline().decode("utf-8", errors="replace").strip()
        print(response)


if __name__ == "__main__":
    main()
