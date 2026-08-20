import time
from pymodbus.client import ModbusSerialClient

print("=== Standalone Dixell Modbus Poller ===")
port = input("Enter serial port (e.g. COM3): ").strip()
slave = int(input("Enter Slave Address: ").strip())

client = ModbusSerialClient(port=port, baudrate=9600, parity='N', stopbits=1, bytesize=8, timeout=1.5)

if client.connect():
    print(f"[✓] Polling Dixell Slave {slave} (Ctrl+C to quit)...\n")
    try:
        while True:
            for label, addr in [("Room", 256), ("Evap 1", 257), ("Evap 2", 258)]:
                res = client.read_holding_registers(address=addr, count=1, slave=slave)
                if not res.isError():
                    val = res.registers[0]
                    if val > 32767:
                        val -= 65536
                    print(f"{label}: {val / 10.0}°C")
                else:
                    print(f"{label}: Error / Timeout")
            print("-" * 20)
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        client.close()
else:
    print("[X] Connection failed.")
