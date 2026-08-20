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


def run_hardware_test():
    """Tool 1: Verifies OS drivers, USB port availability, and adapter loopback."""
    print("\n=== TOOL 1: HARDWARE & SERIAL PORT LOOPBACK TEST ===")
    port = input("Enter your serial port (e.g., COM3 or /dev/ttyUSB0): ").strip()
    
    try:
        # Open port with a short timeout to prevent infinite freezing
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        print(f"[✓] Success: Successfully opened {port}")
        print("\n--- Loopback Verification ---")
        print("To check physical transmission, bridge the TX and RX lines")
        print("(or A+ and B- terminals) on your adapter hardware now.")
        input("Press ENTER when ready to broadcast a test message...")
        
        test_message = b"PING_TEST"
        ser.write(test_message)
        time.sleep(0.1)  # Allow hardware propagation time
        
        response = ser.read(len(test_message))
        ser.close()
        
        if response == test_message:
            print(f"[✓] Loopback Passed! Sent {test_message} and received {response}.")
            print("    Your USB adapter, drivers, and port are working perfectly.")
        else:
            print("[!] Loopback Alert: Port opened but no data echoed back.")
            print(f"    Sent: {test_message} | Received: {response}")
            print("    Verify your physical jumper wires bridge TX to RX properly.")
            
    except Exception as e:
        print(f"[X] Hardware Error: Could not open port {port}.")
        print(f"    Details: {e}")
    
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
                # Capture all available byte chunks in the hardware buffer
                raw_bytes = ser.read(ser.in_waiting)
                hex_string = " ".join(f"{b:02X}" for b in raw_bytes)
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] RX (Hex): {hex_string}")
            time.sleep(0.05)  # Rest CPU cycles
            
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
    print("2) Carel (Standard Analog maps)")
    print("3) Eliwell (IDNext / Standard maps)")
    print("4) Custom Entry (Full Manual Setup)")
    profile = input("Choice (1-4): ").strip()
    
    # Establish baseline profile defaults
    if profile == "1":
        registers = {"Probe 1 (Room)": 256, "Probe 2 (Evap 1)": 257, "Probe 3 (Evap 2)": 258}
        scale_factor = 10.0
        def_baud, def_parity, def_stop = 9600, 'N', 1
    elif profile == "2":
        registers = {"Analog Input 1": 1, "Analog Input 2": 2, "Analog Input 3": 3}
        scale_factor = 10.0
        def_baud, def_parity, def_stop = 19200, 'E', 1
    elif profile == "3":
        registers = {"Probe 1 (Room)": 100, "Probe 2 (Evap 1)": 101, "Probe 3 (Evap 2)": 102}
        scale_factor = 10.0
        def_baud, def_parity, def_stop = 9600, 'E', 1
    else:
        print("\n--- Custom Parameter Register Settings ---")
        reg_start = int(input("Enter starting Holding Register number: ").strip())
        reg_count = int(input("How many sequential registers to poll?: ").strip())
        registers = {f"Register {reg_start + i}": reg_start + i for i in range(reg_count)}
        scale_factor = float(input("Value Division Scale Factor (e.g., 10.0 or 1.0): ").strip() or "1.0")
        def_baud, def_parity, def_stop = 9600, 'N', 1

    # --- Communication Parameter Overrides Menu ---
    print("\n--- COM Network Settings Overrides ---")
    print(f"Press ENTER to accept the bracketed vendor defaults, or type changes:")
    
    baud_input = input(f"  Baud Rate [{def_baud}]: ").strip()
    baud = int(baud_input) if baud_input else def_baud
    
    parity_input = input(f"  Parity N=None, E=Even, O=Odd [{def_parity}]: ").strip().upper()
    parity = parity_input if parity_input in ['N', 'E', 'O'] else def_parity
    
    stop_input = input(f"  Stop Bits 1 or 2 [{def_stop}]: ").strip()
    stopbits = int(stop_input) if stop_input in ['1', '2'] else def_stop

    # Initialize PyModbus Client with verified inputs
    client = ModbusSerialClient(
        port=port,
        baudrate=baud,
        parity=parity,
        stopbits=stopbits,
        bytesize=8,
        timeout=1.5
    )
    
    if not client.connect():
        print(f"[X] Modbus Connection Error: Could not allocate serial channel {port}.")
        input("\nPress ENTER to return to the main menu...")
        return

    print(f"\n[✓] Connected over {baud} {parity} {stopbits}.")
    print(f"Polling Slave {slave_id} every 2 seconds. Press Ctrl+C to stop.\n")
    
    try:
        while True:
            print(f"--- Poll Cycle: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            for name, reg_address in registers.items():
                try:
                    # Wrapped in try/except to catch older pymodbus fatal IO exceptions
                    response = client.read_holding_registers(address=reg_address, count=1, slave=int(slave_id))
                    
                    if response is None or response.isError():
                        print(f"  {name} (Reg {reg_address}): [X] Read Failed / Timeout")
                    else:
                        raw_val = response.registers[0]
                        # Process two's complement for signed negative temperature integers
                        if raw_val > 32767:
                            raw_val -= 65536
                        
                        final_val = raw_val / scale_factor
                        print(f"  {name} (Reg {reg_address}): {final_val}°C (Raw: {response.registers[0]})")
                        
                except Exception as e:
                    # Catches the raw ModbusIOException cleanly so the loop doesn't break
                    print(f"  {name} (Reg {reg_address}): [X] Communication Error: {e}")
                    
            print("-" * 40)
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print("\n[!] Modbus Polling engine stopped by user.")
    finally:
        client.close()
        
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
        print("4) Exit Program")
        print("="*45)
        
        choice = input("Select an option (1-4): ").strip()
        
        if choice == "1":
            run_hardware_test()
        elif choice == "2":
            run_raw_sniffer()
        elif choice == "3":
            run_modbus_reader()
        elif choice == "4":
            print("\nExiting. Tool closed safely.")
            sys.exit(0)
        else:
            print("\n[!] Invalid Selection. Please type a number from 1 to 4.")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nProgram closed via terminal escape sequence.")
        sys.exit(0)
