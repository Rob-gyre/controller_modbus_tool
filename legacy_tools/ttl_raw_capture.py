import serial
import time

print("=== Standalone Raw Byte Sniffer Script ===")
port = input("Enter serial port to sniff (e.g. /dev/ttyUSB0): ").strip()
baud = int(input("Enter Baud Rate (e.g. 9600): ").strip() or "9600")

try:
    ser = serial.Serial(port, baudrate=baud, timeout=0.5)
    print(f"[✓] Sniffing active on {port}. Press Ctrl+C to exit.\n")
    while True:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            hex_out = " ".join(f"{b:02X}" for b in data)
            print(f"[{time.strftime('%H:%M:%S')}] {hex_out}")
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nStopped by user.")
except Exception as e:
    print(f"Error: {e}")
