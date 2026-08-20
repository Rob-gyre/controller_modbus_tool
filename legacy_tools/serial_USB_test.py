import serial
import time

print("=== Standalone Hardware Loopback Script ===")
port = input("Enter serial port to test (e.g. COM3): ").strip()

try:
    ser = serial.Serial(port, baudrate=9600, timeout=1)
    print(f"[✓] Opened {port}. Connect TX to RX jumper wire.")
    input("Press Enter to send test payload...")
    
    payload = b"LOOPBACK_TEST_DATA"
    ser.write(payload)
    time.sleep(0.1)
    
    result = ser.read(len(payload))
    ser.close()
    
    if result == payload:
        print(f"[✓] Success! Match confirmed: {result}")
    else:
        print(f"[X] Fail. Sent: {payload} | Recv: {result}")
except Exception as e:
    print(f"[X] Error opening port: {e}")
