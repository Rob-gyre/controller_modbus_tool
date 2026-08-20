import sys
import time

# Verify global dependencies are accessible
try:
    import serial
except ImportError:
    print("Error: 'pyserial' is missing. Run: pip install pyserial")
    sys.exit(1)

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    try:
        # Fallback for older versions of pymodbus
        from pymodbus.client.sync import ModbusSerialClient
    except ImportError:
        print("Error: 'pymodbus' is missing. Run: pip install pymodbus")
        sys.exit(1)

# Protocol Constants for Carel ASCII Engine
STX, ETX, ENQ, ACK, NULL = 0x02, 0x03, 0x05, 0x06, 0x00

# Carel PJEZ Parameters Maps
CAREL_PARAMS = {
    "St": ("S81", 10, True, "Setpoint °C"),
    "rd": ("S91", 10, True, "Differential °C"),
    "AL": ("S71", 10, True, "Low alarm °C"),
    "AH": ("S@1", 10, True, "High alarm °C"),
    "dt": ("S-1", 10, True, "Defrost end temp °C"),
    "c1": ("U<1", 1, False, "Min between starts (min)"),
    "c2": ("U=1", 1, False, "Min OFF time (min)"),
    "c3": ("U>1", 1, False, "Min ON time (min)"),
    "d0": ("UB1", 1, False, "Defrost type"),
    "d1": ("UC1", 1, False, "Defrost interval (hours)"),
    "dP": ("UD1", 1, False, "Max defrost time (min)"),
    "d5": ("UE1", 1, False, "Defrost delay (min)"),
    "dd": ("UF1", 1, False, "Drain time (min)"),
    "d8": ("UG1", 1, False, "Defrost priority"),
    "d4": ("BL1", 1, False, "Defrost at power-on"),
    "d6": ("BM1", 1, False, "Defrost enabled"),
    "d9": ("BN1", 1, False, "Defrost during standby"),
    "dC": ("BO1", 1, False, "Compressor delay after defrost")
}


def carel_hex(s):
    r = 0
    for c in s:
        if '0' <= c <= '9': v = ord(c) - 0x30
        elif 'A' <= c <= 'F': v = ord(c) - 0x37
        elif 'a' <= c <= 'f': v = ord(c) - 0x57
        elif ':' <= c <= '?': v = ord(c) - 0x30
        else: return 0
        r = (r << 4) | (v & 0x0F)
    return r


def bcc(core):
    b = sum(core) & 0xFF
    return bytes([0x30 + ((b >> 4) & 0x0F), 0x30 + (b & 0x0F)])


def build_frame(body):
    core = bytes([STX]) + body.encode("ascii") + bytes([ETX])
    return core + bcc(core)


def run_hardware_test():
    """Tool 1: Verifies OS drivers, USB port availability, and adapter loopback."""
    print("\n=== TOOL 1: HARDWARE & SERIAL PORT LOOPBACK TEST ===")
    port = input("Enter your serial port (e.g., COM3 or /dev/ttyUSB0): ").strip()
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        print(f"[✓] Success: Successfully opened {port}")
        print("\n--- Loopback Verification ---")
        print("To check physical transmission, bridge the TX and RX lines")
        print("(or A+ and B- terminals) on your adapter hardware now.")
        input("Press ENTER when ready to broadcast a test message...")
        test_message = b"PING_TEST"
        ser.write(test_message)
        time.sleep(0.1)
        response = ser.read(len(test_message))
        ser.close()
        if response == test_message:
            print(f"[✓] Loopback Passed! Sent {test_message} and received {response}.")
        else:
            print("[!] Loopback Alert: Port opened but no data echoed back.")
    except Exception as e:
        print(f"[X] Hardware Error: Could not open port {port}.\nDetails: {e}")
    input("\nPress ENTER to return to the main menu...")


def run_raw_sniffer():
    """Tool 2: Listens passively to incoming traffic, stripping away Modbus filtering."""
    print("\n=== TOOL 2: RAW BYTE SNIFFER ===")
    port = input("Enter your serial port (e.g., COM3 or /dev/ttyUSB0): ").strip()
    baud = input("Enter baud rate (default 9600): ").strip() or "9600"
    try:
        ser = serial.Serial(port, baudrate=int(baud), timeout=0.5)
        print(f"[✓] Listening passively on {port} at {baud} baud...")
        print("Press Ctrl+C at any time to halt sniffing and return to menu.\n")
        while True:
            if ser.in_waiting > 0:
                raw_bytes = ser.read(ser.in_waiting)
                hex_string = " ".join(f"{b:02X}" for b in raw_bytes)
                print(f"[{time.strftime('%H:%M:%S')}] RX (Hex): {hex_string}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[!] Sniffing halted by user.")
    except Exception as e:
        print(f"[X] Sniffer Error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
    input("\nPress ENTER to return to the main menu...")

def run_modbus_reader():
    """Tool 3: Structured Modbus RTU polling framework with configurable overrides."""
    print("\n=== TOOL 3: STRUCTURED MODBUS RTU POLLER ===")
    port = input("Enter your serial port (e.g., COM3 or /dev/ttyUSB0): ").strip()
    slave_id = input("Enter Slave ID / Controller Address (1-247): ").strip()
    print("\nSelect Controller Profile Map:")
    print("1) Dixell (XR64CX / Standard maps)")
    print("2) Carel Standard Modbus (ir33 Maps)")
    print("3) Eliwell (IDNext / Standard maps)")
    print("4) Custom Entry (Full Manual Setup)")
    profile = input("Choice (1-4): ").strip()

    if profile == "1":
        registers = {"Probe 1 (Room)": 256, "Probe 2 (Evap 1)": 257, "Probe 3 (Evap 2)": 258}
        scale_factor = 10.0
        def_baud, def_parity, def_stop = 9600, 'N', 1
    elif profile == "2":
        registers = {"Probe 1 (Room)": 28, "Probe 2 (Evap)": 29, "Probe 3 (Aux)": 30}
        scale_factor = 10.0
        def_baud, def_parity, def_stop = 19200, 'E', 1
    elif profile == "3":
        registers = {"Probe 1 (Room)": 100, "Probe 2 (Evap 1)": 101, "Probe 3 (Evap 2)": 102}
        scale_factor = 10.0
        def_baud, def_parity, def_stop = 9600, 'E', 1
    else:
        reg_start = int(input("Enter starting Holding Register number: ").strip())
        reg_count = int(input("How many sequential registers to poll?: ").strip())
        registers = {f"Register {reg_start + i}": reg_start + i for i in range(reg_count)}
        scale_factor = float(input("Scale Factor (e.g., 10.0): ").strip() or "1.0")
        def_baud, def_parity, def_stop = 9600, 'N', 1

    baud_input = input(f"  Baud Rate [{def_baud}]: ").strip()
    baud = int(baud_input) if baud_input else def_baud
    parity_input = input(f"  Parity N/E/O [{def_parity}]: ").strip().upper()
    parity = parity_input if parity_input in ['N', 'E', 'O'] else def_parity
    stop_input = input(f"  Stop Bits 1 or 2 [{def_stop}]: ").strip()
    stopbits = int(stop_input) if stop_input in ['1', '2'] else def_stop

    client = ModbusSerialClient(port=port, baudrate=baud, parity=parity, stopbits=stopbits, bytesize=8, timeout=1.5)
    if not client.connect():
        return

    try:
        while True:
            print(f"--- Poll Cycle: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            for name, reg_address in registers.items():
                try:
                    response = client.read_holding_registers(address=reg_address, count=1, slave=int(slave_id))
                    if response is None or response.isError():
                        print(f"  {name} (Reg {reg_address}): [X] Read Failed / Timeout")
                    else:
                        raw_val = response.registers
                        if raw_val > 32767: raw_val -= 65536
                        print(f"  {name} (Reg {reg_address}): {raw_val / scale_factor}°C")
                except Exception as e:
                    print(f"  {name} (Reg {reg_address}): [X] Communication Error: {e}")
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\n[!] Modbus Polling engine stopped.")
    finally:
        client.close()
    input("\nPress ENTER to return to menu...")


def run_carel_pjez_reader():
    """Tool 4: Passive Carel PJEZ ASCII Poller (Listens to automatic cyclic broadcasts)."""
    print("\n=== TOOL 4: PASSIVE CAREL PJEZ ASCII LISTENER ===")
    port = input("Enter your serial port (e.g., /dev/ttyACM0 or COM3): ").strip()

    try:
        ser = serial.Serial(port=port, baudrate=19200, bytesize=8, parity='N', stopbits=2, timeout=0.5)
        print(f"[✓] Opened {port} successfully. Listening for automatic Carel broadcasts...")
        print("Press Ctrl+C at any time to halt listening and return to menu.\n")
    except Exception as e:
        print(f"[X] Connection Error: {e}")
        input("\nPress ENTER to return to menu...")
        return

    def read_frame(timeout=1.5):
        start = time.time()
        while time.time() - start < timeout:
            b = ser.read(1)
            if not b: continue
            if b == NULL: return bytes([NULL])
            if b == STX:
                buf = bytearray([STX])
                while time.time() - start < timeout:
                    c = ser.read(1)
                    if c:
                        buf.append(c)
                        if c == ETX: break
                for _ in range(2):
                    c = ser.read(1)
                    if c: buf.append(c)
                return bytes(buf)
        return None

    try:
        while True:
            frame = read_frame()
            if frame and len(frame) >= 6:
                try:
                    etx_idx = frame.index(ETX)
                    body = frame[1:etx_idx].decode("ascii", errors="ignore")
                    ser.write(bytes([ACK]))

                    # RESTORED: Evaluates only the single leading character block
                    if body[0] in ["S", "U", "B"]:
                        token = f"{body[0]}{body[2:4]}"
                        raw = carel_hex(body[4:]) & 0xFFFF

                        # Simplified key lookup mapping match
                        for mnem, config in CAREL_PARAMS.items():
                            if config[0] == token:
                                scale = config[1]
                                signed = config[2]
                                desc = config[3]
                                
                                if signed and raw >= 0x8000: 
                                    raw -= 0x10000
                                final_val = raw / scale
                                if scale > 1: 
                                    print(f"  {mnem} ({desc}): {final_val:.1f}°C")
                                else: 
                                    print(f"  {mnem} ({desc}): {int(final_val)}")
                except Exception: 
                    pass
    except KeyboardInterrupt:
        print("\n[!] Passive Carel PJEZ listening halted by user.")
    finally:
        ser.close()
    input("\nPress ENTER to return to the main menu...")


def main_menu():
    """Core terminal menu dispatcher loop."""
    while True:
        print("\n" + "="*45)
        print("       HVAC FIELD SERIAL DIAGNOSTIC TOOL     ")
        print("="*45)
        print("1) Run Hardware Loopback Test  (Old: serial_USB_test.py)")
        print("2) Run Raw Byte Sniffer        (Old: ttl_raw_capture.py)")
        print("3) Run Structured Modbus Poll  (Old: read_dixell.py)")
        print("4) Run Native Carel PJEZ Poll  (ASCII Token Engine)")
        print("5) Exit Program")
        print("="*45)

        choice = input("Select an option (1-5): ").strip()
        if choice == "1": run_hardware_test()
        elif choice == "2": run_raw_sniffer()
        elif choice == "3": run_modbus_reader()
        elif choice == "4": run_carel_pjez_reader()
        elif choice == "5":
            print("\nExiting. Tool closed safely.")
            sys.exit(0)
        else:
            print("\n[!] Invalid Selection. Please type 1 to 5.")


if __name__ == "__main__":
    try: main_menu()
    except KeyboardInterrupt: sys.exit(0)






