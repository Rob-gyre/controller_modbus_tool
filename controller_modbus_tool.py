#!/usr/bin/env python3
"""
CONTROLLER SERIAL DIAGNOSTIC SUITE (Optimised for Dixell XR77U Custom OEM)
Architecture: Auto-Detect Hardware Interface First | Locked Modbus RTU Address 1 Mapping
"""

import sys
import time

# Verify global dependencies are accessible
try:
    import serial
    import serial.tools.list_ports  # System USB device scanner
except ImportError:
    print("Error: 'pyserial' is missing. Run: pip install pyserial")
    sys.exit(1)

try:
    import minimalmodbus
except ImportError:
    print("Error: 'minimalmodbus' is missing. Run: pip install minimalmodbus")
    sys.exit(1)


def calculate_modbus_crc(data: bytes) -> bytes:
    """Calculates standard Modbus RTU CRC16 for packet stream analysis."""
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')


def scan_and_select_port():
    """Scans the operating system and provides a clean selection grid of active USB/Serial adapters."""
    print("\n[1/2] SCANNING COMPUTER FOR SERIAL INTERFACES...")
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("\n[!] ALERT: No active hardware COM ports or USB serial adapters detected.")
        print("    Ensure your USB-to-TTL or USB-to-RS485 cable is fully plugged in.")
        manual = input("    Would you like to manually force a port name? (y/n): ").strip().lower()
        if manual == 'y':
            return input("    Enter port name (e.g., COM3, /dev/ttyUSB0): ").strip()
        return None

    print("\n--- FOUND CONNECTED USB / SERIAL DEVICES ---")
    for idx, p in enumerate(ports, 1):
        print(f"  {idx}) {p.device} [{p.description}]")
    print("--------------------------------------------")
        
    while True:
        choice = input(f"Select the number corresponding to your adapter (1-{len(ports)}): ").strip()
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(ports):
                selected_port = ports[choice_idx].device
                print(f"[✓] Interface target assigned to: {selected_port}")
                return selected_port
            print(f"[!] Selection out of bounds. Enter 1 to {len(ports)}.")
        except ValueError:
            print("[!] Invalid entry. You must input a number.")


def select_hardware_topology():
    """Captures structural wiring configuration to adapt runtime timings and test filters."""
    print("\n[2/2] SELECT PHYSICAL HARDWARE WIRING TOPOLOGY...")
    print("  1) Method A: Direct USB-to-TTL Adapter to Controller")
    print("     (Connecting directly to the 5V micro-bus HotKey port layout)")
    print("  2) Method B: Controller -> XJ485CX Adapter -> USB-to-RS485 Converter")
    print("     (Standard industrial differential loop layout)")
    print("---------------------------------------------------------------------")
    
    choice = ""
    while choice not in ["1", "2"]:
        choice = input("Select Setup Option (1 or 2): ").strip()
        if choice not in ["1", "2"]:
            print("[!] Invalid setup choice. Enter 1 or 2.")
    return choice


def run_hardware_test(port, hw_choice):
    """Tool 1: Hardware & Serial Port Loopback Test [Context-Aware Instruction Engine]"""
    print("\n========================================================")
    print("=== TOOL 1: HARDWARE & SERIAL PORT LOOPBACK DIAGNOSTIC ===")
    print("========================================================")
    print("⚠️  CRITICAL SAFETY WARNINGS FOR BENCH TESTING:")
    print(" -> Ensure your USB-to-TTL adapter logic jumper is physically locked to 5V (NOT 3.3V).")
    print(" -> If the XR77U controller is mains-powered, DISCONNECT the VCC/5V wire from your adapter.")
    print("    Only bridge TX, RX, and GND. Backfeeding VCC will destroy your computer's USB controller.")
    print("\n--- WIRING ACTIONS REQUIRED NOW BEFORE CONTINUING ---")
    
    if hw_choice == "1":
        print("[METHOD A SETUP] Take a temporary jumper wire and short the TXD pin directly")
        print("                 to the RXD pin on your USB-to-TTL board terminals.")
    else:
        print("[METHOD B SETUP] Take a temporary jumper wire and short the A(+) terminal directly")
        print("                 to the B(-) terminal on your USB-to-RS485 board blocks.")
        
    input("\n[!] Once the physical loopback bridge jumper wire is secured, press ENTER to test...")
    print("Executing electrical loopback payload broadcast...")

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        payload = b"DIXELL_LOOPBACK_VERIFY_2C310000"
        ser.write(payload)
        time.sleep(0.1)
        
        result = ser.read(len(payload))
        ser.close()
        
        if result == payload:
            print(f"\n[✓] SUCCESS: Electrical loopback verified perfectly! (Bytes match: {result.decode()})")
            print("    Your serial port, system drivers, and adapter chip are working cleanly.")
        else:
            print(f"\n[X] FAILURE: Cable opened but data frame dropped or corrupted.")
            print(f"    Sent: {payload}")
            print(f"    Recv: {result}")
            print("    -> Action: Check that the jumper wire is making solid contact with the pins.")
    except Exception as e:
        print(f"\n[X] OS DRIVER ERROR: Could not open {port}. Details: {e}")
        
    input("\nRemove the bridge jumper wire, then press ENTER to return to menu...")


def run_raw_sniffer(port):
    """Tool 2: Raw Byte Sniffer [Modbus RTU Frame-Aware Analyzer]"""
    print("\n========================================================")
    print("=== TOOL 2: REAL-TIME MODBUS RTU FRAME ANALYSER / SNIFFER ===")
    print("========================================================")
    print(f"Passively monitoring all traffic on {port} at 9600 bps.")
    print("Auto-checking custom XR77U Slave Address 01 transaction blocks...")
    print("Press Ctrl+C at any time to break the sniffer and return to the menu.\n")

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=0.5)
        while True:
            if ser.in_waiting > 0:
                time.sleep(0.04)  # Small processing buffer to allow trailing frame bytes to land
                data = ser.read(ser.in_waiting)
                hex_out = " ".join(f"{b:02X}" for b in data)
                
                analysis = ""
                if len(data) >= 4 and data[0] == 0x01:
                    func = data[1]
                    if func in [0x03, 0x06, 0x10, 0x83, 0x86, 0x90]:
                        msg_bytes = data[:-2]
                        expected_crc = calculate_modbus_crc(msg_bytes)
                        actual_crc = data[-2:]
                        
                        if expected_crc == actual_crc:
                            if func == 0x03:
                                analysis = " -> [Valid Modbus Read Frame]"
                            elif func == 0x06:
                                analysis = " -> [Valid Modbus Write Register Frame]"
                            elif func & 0x80:
                                analysis = " -> [Modbus EXCEPTION Response Code returned from unit]"
                        else:
                            analysis = " -> [Structure matches Modbus layout but CRC Check FAILED]"

                print(f"[{time.strftime('%H:%M:%S')}] RX: {hex_out}{analysis}")
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n[✓] Sniffing paused.")
    except Exception as e:
        print(f"[X] Sniffer Execution Interrupted: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            
    input("\nPress ENTER to return to the principal workspace menu...")


def run_register_scanner(instrument):
    """Utility Tool: Scans Modbus register blocks systematically to find valid operational zones."""
    print("\n========================================================")
    print("=== UTILITY: DIXELL OEM DYNAMIC REGISTER SCANNER ===")
    print("========================================================")
    print("Finds valid map addresses to bypass 'illegal data address' blocks.")
    
    try:
        start_addr = int(input("Enter Scan Starting Address (Decimal, e.g., 0 or 256): ").strip() or "0")
        end_addr = int(input("Enter Scan Ending Address (Decimal, e.g., 1000): ").strip() or "1000")
    except ValueError:
        print("[!] Invalid integer parameters. Reverting to test environment.")
        return

    print(f"\nScanning range {start_addr} to {end_addr} on Slave ID 1... Press Ctrl+C to abort.")
    valid_registers = []

    try:
        for addr in range(start_addr, end_addr + 1):
            try:
                val = instrument.read_register(addr, number_of_decimals=0, signed=False)
                hex_str = f"0x{addr:04X}"
                print(f"  [✓] FOUND ACTIVE REGISTER: Dec {addr} ({hex_str}) | Raw Data: {val}")
                valid_registers.append((addr, hex_str, val))
                time.sleep(0.05)
            except minimalmodbus.IllegalRequestError:
                pass
            except (minimalmodbus.NoResponseError, minimalmodbus.ModbusException):
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[!] Scanner aborted early by user.")

    print("\n=== SCAN SUMMARY RESULTS ===")
    if valid_registers:
        print(f"Discovered {len(valid_registers)} active register boundaries:")
        for reg in valid_registers:
            print(f"  -> Decimal: {reg[0]} | Hex: {reg[1]} | Current Raw Value: {reg[2]}")
    else:
        print("[X] No valid data addresses mapped inside selected scan limits.")
    print("========================================================")


def run_modbus_reader(port, hw_choice):
    """Tool 3: Targeted Dixell XR77U Custom Modbus Poller [Family 44 Multi-Register Layout]"""
    print("\n========================================================")
    print("=== TOOL 3: TARGETED DIXELL XR77U LIVE INTERACTIVE POLLER ===")
    print("========================================================")
    
    timeout_val = 0.4 if hw_choice == "1" else 0.6
    slave_id = 1

    try:
        instrument = minimalmodbus.Instrument(port, slave_id)
        instrument.serial.baudrate = 9600
        instrument.serial.bytesize = 8
        instrument.serial.parity = serial.PARITY_NONE
        instrument.serial.stopbits = 1
        instrument.serial.timeout = timeout_val
        instrument.mode = minimalmodbus.MODE_RTU
        print(f"[✓] Internal Modbus communication pipeline initialized on {port}.")
    except Exception as e:
        print(f"[X] Engine Hook Setup Failed: {e}")
        input("\nPress ENTER to return to workspace menu...")
        return

    while True:
        print(f"\n--- Live Action Options (Locked to Slave Address 1) ---")
        print(" 1) Stream Live Telemetry (Track Discovered Register Range)")
        print(" 2) Modify Temperature Setpoint (Write Test Zone)")
        print(" 3) Run Custom Address Map Scanner (Locate hidden variables)")
        if hw_choice == "2":
            print(" 4) XJ485CX Optocoupler Line Stability & Stress Diagnostic")
        print(" Q) Return to Main Menu")
        
        test_choice = input("\nSelect workspace command: ").strip().upper()
        
        if test_choice == "Q":
            break
            
        elif test_choice == "1":
            print(f"\nStreaming all active Family 44 registers on {port}. Press Ctrl+C to halt stream...\n")
            try:
                while True:
                    try:
                        # Query the exact active register nodes revealed by your scan
                        r256 = instrument.read_register(256, number_of_decimals=1, signed=True)
                        r260 = instrument.read_register(260, number_of_decimals=1, signed=True)
                        r264 = instrument.read_register(264, number_of_decimals=1, signed=True)
                        
                        print(f"[{time.strftime('%H:%M:%S')}] Query Succeeded:")
                        print(f"  -> Register 256 (0x0100):  {r256} °C")
                        print(f"  -> Register 260 (0x0104):  {r260} °C")
                        print(f"  -> Register 264 (0x0108):  {r264} °C")
                        print("-" * 40)
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] [TIMEOUT/ERROR] Data drop: {e}")
                    time.sleep(2.0)
            except KeyboardInterrupt:
                print("\nLive data stream terminated.")
                
        elif test_choice == "2":
            print("\nExecuting targeted parameter override routine...")
            try:
                print("Broadcasting Modbus Write single register test payload to register 6...")
                val_input = input("Enter new targeted testing Setpoint value in °C (e.g. 4.0): ").strip()
                if not val_input:
                    continue
                new_val = float(val_input)
                
                instrument.write_register(6, new_val, number_of_decimals=1, signed=True)
                print(f"[✓] SUCCESS: Command committed to register 6 memory layer.")
            except Exception as e:
                print(f"[X] Modbus Write Transaction Aborted: {e}")
                
        elif test_choice == "3":
            run_register_scanner(instrument)
            
        elif test_choice == "4" and hw_choice == "2":
            print("\nTesting XJ485CX transceiver physical stability over 10 loops...")
            success = 0
            for i in range(1, 11):
                try:
                    instrument.read_register(256, number_of_decimals=0, signed=False)
                    print(f"  [Frame {i:02d}/10] Echo Delivery: OK")
                    success += 1
                except Exception:
                    print(f"  [Frame {i:02d}/10] Echo Delivery: TIMEOUT / DROPPED PACKET")
                time.sleep(0.2)
            print(f"\n[INTEGRITY RATING] Line Stability Score: {success * 10}%")
        else:
            print("[!] Command unavailable under current structural hardware selections.")
            
        input("\nPress ENTER to continue inside current test environment...")


def main():
    print("=========================================================")
    print("  CONTROLLER SERIAL DIAGNOSTIC & WORKSPACE SUITE v2.2 ")
    print("=========================================================")
    print("Initial hardware binding required before entering diagnostic loop.")
    
    active_port = scan_and_select_port()
    if not active_port:
        print("\n[!] No communications interface bound. Application exiting.")
        sys.exit(0)
        
    hardware_type = select_hardware_topology()
    hw_mode_string = "Direct 5V TTL" if hardware_type == "1" else "RS-485 (via XJ485CX)"
    
    while True:
        print("\n" + "="*55)
        print("            CONTROLLER ACTIVE DIAGNOSTIC MENUS            ")
        print(f" Current Active Interface: {active_port} | Mode: {hw_mode_string}")
        print("="*55)
        print(" 1) Run Safety-Enhanced Jumper Loopback Test")
        print(" 2) Run Modbus RTU Raw Byte Frame Sniffer")
        print(" 3) Launch Custom XR77U Targeted Modbus Workspace Menu")
        print(" 4) Switch Hardware Interface Configurations / Rescan Ports")
        print(" 5) Exit Suite Workspace safely")
        print("="*55)

        choice = input("Select workspace execution action (1-5): ").strip()
        if choice == "1": 
            run_hardware_test(active_port, hardware_type)
        elif choice == "2": 
            run_raw_sniffer(active_port)
        elif choice == "3": 
            run_modbus_reader(active_port, hardware_type)
        elif choice == "4":
            print("\nRe-entering initialization wizard...")
            active_port = scan_and_select_port()
            if not active_port:
                print("\n[!] Interface dropped. Application closing.")
                break
            hardware_type = select_hardware_topology()
            hw_mode_string = "Direct 5V TTL" if hardware_type == "1" else "RS-485 (via XJ485CX)"
        elif choice == "5":
            print("\nClosing serial diagnostic workspaces. Goodbye.")
            sys.exit(0)
        else:
            print("\n[!] Input entry invalid. Select an index value between 1 and 5.")


if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        print("\nWorkspace broken by user execution command.")
        sys.exit(0)
