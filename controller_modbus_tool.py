#!/usr/bin/env python3
"""
UNIVERSAL MODBUS DIAGNOSTIC SUITE & CONTROLLER ANALYSER (v3.0)
Includes specialized profile mapping for Dixell XR77U Custom OEM (2C310000)
"""

import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: 'pyserial' is missing. Run: pip install pyserial")
    sys.exit(1)

try:
    import minimalmodbus
except ImportError:
    print("Error: 'minimalmodbus' is missing. Run: pip install minimalmodbus")
    sys.exit(1)


class ConfigWorkspace:
    """Manages global Modbus RTU communication environment variables."""
    def __init__(self):
        self.port = None
        self.hw_choice = "2"    # Default to Method B (RS-485 via XJ485CX)
        self.slave_id = 1       # Default Slave Address
        self.baudrate = 9600    # Default speed
        self.parity = serial.PARITY_NONE
        self.stopbits = 1
        self.timeout = 0.6      # Dynamic time cushion

    def get_parity_string(self):
        if self.parity == serial.PARITY_EVEN: return "Even"
        if self.parity == serial.PARITY_ODD: return "Odd"
        return "None"


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


def run_initialization_wizard(cfg):
    """Wizard that dynamically binds ports and configures universal Modbus parameters."""
    print("\n" + "="*55)
    print("      INITIALISATION WIZARD: CONFIGURE SERIAL WORKSPACE    ")
    print("="*55)
    
    cfg.port = scan_and_select_port()
    if not cfg.port:
        print("\n[!] No communications interface bound. Exiting wizard.")
        return

    # Hardware Connection Type Selection
    hardware_choice = select_hardware_topology()
    if hardware_choice == "1":
        cfg.hw_choice = "1"
        cfg.timeout = 0.4
    else:
        cfg.hw_choice = "2"
        cfg.timeout = 0.6

    # Advanced Universal Modbus Variable Prompts
    print("\n--- Configure Universal Modbus Parameters ---")
    
    slave_in = input(f"Enter Target Slave ID (1-247) [Default {cfg.slave_id}]: ").strip()
    if slave_in: cfg.slave_id = int(slave_in)
        
    baud_in = input(f"Enter Baud Rate (9600, 19200, 38400) [Default {cfg.baudrate}]: ").strip()
    if baud_in: cfg.baudrate = int(baud_in)
        
    parity_in = input("Enter Parity (N=None, E=Even, O=Odd) [Default N]: ").strip().upper()
    if parity_in == 'E': cfg.parity = serial.PARITY_EVEN
    elif parity_in == 'O': cfg.parity = serial.PARITY_ODD
    else: cfg.parity = serial.PARITY_NONE
        
    stop_in = input(f"Enter Stop Bits (1 or 2) [Default {cfg.stopbits}]: ").strip()
    if stop_in: cfg.stopbits = int(stop_in)
    
    print(f"\n[✓] Config Complete: Bound to {cfg.port} | Slave Address: {cfg.slave_id} | {cfg.baudrate} bps")


def build_instrument_context(cfg, target_slave=None):
    """Generates an operational MinimalModbus context based on dynamic workspace configurations."""
    slave = target_slave if target_slave is not None else cfg.slave_id
    try:
        instrument = minimalmodbus.Instrument(cfg.port, slave)
        instrument.serial.baudrate = cfg.baudrate
        instrument.serial.bytesize = 8
        instrument.serial.parity = cfg.parity
        instrument.serial.stopbits = cfg.stopbits
        instrument.serial.timeout = cfg.timeout
        instrument.mode = minimalmodbus.MODE_RTU
        return instrument
    except Exception as e:
        print(f"[X] Modbus Engine Hook Initialization Setup Failed: {e}")
        return None


def run_hardware_test(cfg):
    """Tool 1: Hardware & Serial Port Loopback Test [Context-Aware Instruction Engine]"""
    print("\n=== TOOL 1: HARDWARE & SERIAL PORT LOOPBACK DIAGNOSTIC ===")
    print("⚠️  CRITICAL SAFETY WARNINGS FOR BENCH TESTING:")
    print(" -> Ensure your USB-to-TTL adapter logic jumper is physically locked to 5V (NOT 3.3V).")
    print(" -> If the controller is mains-powered, DISCONNECT the VCC/5V wire from your adapter.")
    print("\n--- WIRING ACTIONS REQUIRED NOW BEFORE CONTINUING ---")
    
    if cfg.hw_choice == "1":
        print("[METHOD A SETUP] Bridge TXD pin directly to RXD pin on your USB-to-TTL board.")
    else:
        print("[METHOD B SETUP] Bridge A(+) terminal directly to B(-) terminal on your USB-to-RS485 block.")
        
    input("\n[!] Once the physical loopback bridge jumper wire is secured, press ENTER to test...")
    print("Executing electrical loopback payload broadcast...")

    try:
        ser = serial.Serial(cfg.port, baudrate=cfg.baudrate, timeout=1)
        payload = b"DIXELL_UNIVERSAL_LOOPBACK_VERIFY"
        ser.write(payload)
        time.sleep(0.1)
        
        result = ser.read(len(payload))
        ser.close()

        if result == payload:
            print(f"\n[✓] SUCCESS: Electrical loopback verified perfectly! (Bytes match: {result.decode()})")
        else:
            print(f"\n[X] FAILURE: Cable opened but data frame dropped or corrupted.")
    except Exception as e:
        print(f"\n[X] OS DRIVER ERROR: Could not open {cfg.port}. Details: {e}")
        
    input("\nRemove the bridge jumper wire, then press ENTER to return to menu...")


def run_raw_sniffer(cfg):
    """Tool 2: Raw Byte Sniffer [Modbus RTU Frame-Aware Analyzer]"""
    print("\n=== TOOL 2: REAL-TIME MODBUS RTU FRAME ANALYSER / SNIFFER ===")
    print(f"Passively monitoring all traffic on {cfg.port} at {cfg.baudrate} bps.")
    print(f"Filtering for transaction blocks matching Slave Address {cfg.slave_id}...")
    print("Press Ctrl+C at any time to break the sniffer and return to the menu.\n")

    try:
        ser = serial.Serial(cfg.port, baudrate=cfg.baudrate, timeout=0.5)
        while True:
            if ser.in_waiting > 0:
                time.sleep(0.04)
                data = ser.read(ser.in_waiting)
                hex_out = " ".join(f"{b:02X}" for b in data)
                
                analysis = ""
                if len(data) >= 4 and data[0] == cfg.slave_id:
                    func = data[1]
                    if func in [0x01, 0x02, 0x03, 0x04, 0x06, 0x10, 0x83, 0x86, 0x90]:
                        msg_bytes = data[:-2]
                        expected_crc = calculate_modbus_crc(msg_bytes)
                        actual_crc = data[-2:]
                        
                        if expected_crc == actual_crc:
                            if func in [0x03, 0x04]: analysis = " -> [Valid Modbus Read Request/Response]"
                            elif func in [0x06, 0x10]: analysis = " -> [Valid Modbus Write Request/Response]"
                            elif func & 0x80: analysis = " -> [Modbus EXCEPTION/ERROR Response from device]"
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
    input("\nPress ENTER to return to the workspace menu...")


def run_universal_register_scanner(cfg):
    """Tool 3: Universal Dynamic Register Scanner (Supports FC3 and FC4)"""
    print("\n=== TOOL 3: UNIVERSAL DYNAMIC REGISTER MEMORY SCANNER ===")
    instrument = build_instrument_context(cfg)
    if not instrument: return

    print("Select Modbus Function Code for Scan Probing:")
    print("  3) Function Code 0x03 (Read Holding Registers - Standard Settings/Config)")
    print("  4) Function Code 0x04 (Read Input Registers - Read-Only Analog Probes)")
    fc_choice = input("Select Function Code (3 or 4) [Default 3]: ").strip()
    use_fc4 = True if fc_choice == "4" else False

    try:
        start_addr = int(input("Enter Scan Starting Address (Decimal, e.g., 0 or 256): ").strip() or "0")
        end_addr = int(input("Enter Scan Ending Address (Decimal, e.g., 1000): ").strip() or "1000")
    except ValueError:
        print("[!] Invalid integer parameters. Reverting to menu.")
        return

    print(f"\nScanning range {start_addr} to {end_addr} on Slave ID {cfg.slave_id}... Press Ctrl+C to abort.")
    valid_registers = []

    try:
        for addr in range(start_addr, end_addr + 1):
            try:
                if use_fc4:
                    val = instrument.read_register(addr, number_of_decimals=0, signed=False, functioncode=4)
                else:
                    val = instrument.read_register(addr, number_of_decimals=0, signed=False, functioncode=3)
                
                hex_str = f"0x{addr:04X}"
                print(f"  [✓] FOUND ACTIVE REGISTER: Dec {addr} ({hex_str}) | Current Raw Value: {val}")
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
    input("\nPress ENTER to continue...")


def run_universal_dashboard_node(cfg):
    """Tool 4: Universal Interactive Dashboard Node (Read/Write any individual register)"""
    print("\n=== TOOL 4: UNIVERSAL INTERACTIVE REGISTER DASHBOARD NODE ===")
    instrument = build_instrument_context(cfg)
    if not instrument: return

    try:
        target_reg = int(input("Enter Target Decimal Register Address to monitor/control: ").strip())
    except ValueError:
        print("[!] Invalid address entry.")
        return

    scale_in = input("Enter Decimal Scaling Multiplier (e.g., 10.0 for x0.1 resolution, or 1.0) [Default 1.0]: ").strip()
    scale_factor = float(scale_in) if scale_in else 1.0

    while True:
        print(f"\n--- Controlling Dynamic Node Address: Dec {target_reg} (0x{target_reg:04X}) ---")
        print(" 1) Stream Real-Time Value Queries")
        print(" 2) Send Modbus Write Single Register Payload Command")
        print(" B) Back to principal application loop")
        
        choice = input("\nSelect node command action: ").strip().upper()
        if choice == "B":
            break
        elif choice == "1":
            print(f"\nStreaming queries on register {target_reg}. Press Ctrl+C to halt stream...\n")
            try:
                while True:
                    raw_val = instrument.read_register(target_reg, number_of_decimals=0, signed=True)
                    scaled_val = raw_val / scale_factor
                    print(f"[{time.strftime('%H:%M:%S')}] Register {target_reg}: Raw={raw_val} | Mapped Scaled={scaled_val}")
                    time.sleep(2.0)
            except KeyboardInterrupt:
                print("\nStreaming paused.")
        elif choice == "2":
            try:
                raw_curr = instrument.read_register(target_reg, number_of_decimals=0, signed=True)
                print(f"\nCurrent Raw Register Integer Value: {raw_curr}")
                val_in = input("Enter new targeted raw integer value to write: ").strip()
                if not val_in: continue
                new_int_val = int(val_in)
                
                print(f"Transmitting Modbus Write packet to Register {target_reg}...")
                instrument.write_register(target_reg, new_int_val, number_of_decimals=0, signed=True)
                time.sleep(0.3)

                verify = instrument.read_register(target_reg, number_of_decimals=0, signed=True)
                if verify == new_int_val:
                    print(f"[✓] SUCCESS: Mapped value committed and verified: {verify}")
                else:
                    print(f"[X] ERROR: Verification mismatch. Sent {new_int_val} but read back {verify}")
            except Exception as e:
                print(f"[X] Modbus Transaction Aborted: {e}")
        input("\nPress ENTER to continue inside current register dashboard node...")


def run_custom_xr77u_workspace(cfg):
    """Tool 5: Specialized Dixell XR77U Custom OEM Profile (2C310000 / Map Code Ptb 3)"""
    print("\n========================================================")
    print("=== TOOL 5: SPECIALISED DIXELL XR77U PROFILE WORKSPACE ===")
    print("========================================================")
    print("⚠️  Warning: This workspace targets the hardcoded limits of the 2C310000 profile.")
    print("    It automatically builds an independent connection profile forcing Address 1.")
    
    # Force alignment to verified profile parameters
    instrument = build_instrument_context(cfg, target_slave=1)
    if not instrument: return

    # Mapped registers derived from your workbench validation sweeps
    REG_ROOM_TEMP = 256   # 0x0100 - Live Room Probe (P1)
    REG_SETPOINT  = 853   # 0x0355 - Mapped Temperature Setpoint (SEt)
    REG_DIFF      = 770   # 0x0302 - Mapped Regulation Differential (Hy)
    REG_STATUS    = 12    # 0x000C - Live Relay Output Bitmask Register (FC 0x03/0x04)

    while True:
        print(f"\n--- Mapped Telemetry Actions (Address: 1 | Speed: {cfg.baudrate} bps) ---")
        print(" 1) Stream Live Telemetry Dashboard (P1 Room Temp, SEt, Hy)")
        print(" 2) Modify Temperature Setpoint (Write New SEt Value to Reg 819)")
        print(" B) Back to Main Menu")
        
        choice = input("\nSelect operational profile choice: ").strip().upper()
        if choice == "B":
            break
        elif choice == "1":
            print(f"\nStreaming verified XR77U telemetry dashboard. Press Ctrl+C to stop...\n")
            try:
                while True:
                    try:
                        room_temp = instrument.read_register(REG_ROOM_TEMP, number_of_decimals=1, signed=True)
                        setpoint  = instrument.read_register(REG_SETPOINT, number_of_decimals=1, signed=True)
                        diff      = instrument.read_register(REG_DIFF, number_of_decimals=1, signed=False)
                        
                        # Query the live status word register (Register 12)
                        # status_word = instrument.read_register(REG_STATUS, number_of_decimals=0, signed=False, functioncode=4)

                        # Extract states using bitwise-AND masking logic derived from the database
                        # comp_relay = "ON" if (status_word & 0x0001) else "OFF"
                        # defrost_state = "ACTIVE" if (status_word & 0x0002) else "INACTIVE"
                        # fan_relay = "RUNNING" if (status_word & 0x0004) else "STOPPED"
                        # alarm_status = "⚠️ CRITICAL ALERT" if (status_word & 0x0010) else "NORMAL"
                        
                        print(f"[{time.strftime('%H:%M:%S')}] XR77U Custom Profile Telemetry Frame:")
                        print(f"  -> System Alarm Status:    {alarm_status}")
                        print(f"  -> Room Probe Temp (P1):   {room_temp} °C")
                        print(f"  -> Mapped Setpoint (SEt):  {setpoint} °C")
                        print(f"  -> Mapped Differential (Hy): {diff} °C")
                        print(f"  -> Compressor Output Relay: UNKNOWN (Mapping Test)")
                        print(f"  -> Defrost Cycle State:     UNKNOWN (Mapping Test)")
                        print(f"  -> Evaporator Fan Relay:    UNKNOWN (Mapping Test)")
                        print("-" * 45)
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] [TIMEOUT/ERROR] Data drop: {e}")
                    time.sleep(2.0)
            except KeyboardInterrupt:
                print("\nStream paused.")

        elif choice == "2":
            try:
                current_set = instrument.read_register(REG_SETPOINT, number_of_decimals=1, signed=True)
                print(f"\nCurrent active controller memory Setpoint reads: {current_set} °C")
                val_input = input("Enter new targeted Setpoint value in °C (e.g. 4.0): ").strip()
                if not val_input: continue
                new_val = float(val_input)
                
                print("Broadcasting Modbus Write command to Setpoint Register 819...")
                instrument.write_register(REG_SETPOINT, new_val, number_of_decimals=1, signed=True)
                time.sleep(0.3)
                
                if instrument.read_register(REG_SETPOINT, number_of_decimals=1, signed=True) == new_val:
                    print(f"[✓] SUCCESS: Mapped value successfully committed to EEPROM: {new_val} °C")
                else:
                    print("[X] ERROR: Verification check failed. Mismatch on memory readback.")
            except Exception as e:
                print(f"[X] Modbus Write Transaction Aborted: {e}")
        input("\nPress ENTER to continue inside current profile environment...")

# --- MAIN ENGINE ROUTER LOOPS ---

def main():
    cfg = ConfigWorkspace()
    print("=========================================================")
    print("  UNIVERSAL CONTROLLER MODBUS DIAGNOSTIC WORKSPACE v3.0  ")
    print("=========================================================")
    print("Initial hardware binding required before entering diagnostic loop.")
    
    # Force dynamic configuration tracking on application boot
    run_initialization_wizard(cfg)
    if not cfg.port:
        print("\n[!] Application setup aborted. Exiting suite.")
        sys.exit(0)
    
    while True:
        parity_str = cfg.get_parity_string()
        print("\n" + "="*60)
        print("          UNIVERSAL SERIAL DIAGNOSTIC SYSTEM CONTROLS      ")
        print(f" Active Port: {cfg.port} | Slave ID: {cfg.slave_id} | {cfg.baudrate} bps | Parity: {parity_str}")
        print("="*60)
        print(" 1) Run Safety-Enhanced Hardware Loopback Diagnostic Test")
        print(" 2) Run Modbus RTU Raw Byte Frame Sniffer / Analyser")
        print(" 3) Run Universal Dynamic Register Memory Scanner (FC3/FC4)")
        print(" 4) Launch Universal Interactive Register Dashboard Node")
        print(" 5) Launch Specialized Dixell XR77U Custom Profile Workspace")
        print(" 6) Re-run Initialization Wizard (Switch Serial Hardware / Speeds)")
        print(" 7) Close Application Suite safely")
        print("="*60)

        choice = input("Select workspace execution action (1-7): ").strip()
        if choice == "1":
            run_hardware_test(cfg)
        elif choice == "2":
            run_raw_sniffer(cfg)
        elif choice == "3":
            run_universal_register_scanner(cfg)
        elif choice == "4":
            run_universal_dashboard_node(cfg)
        elif choice == "5":
            run_custom_xr77u_workspace(cfg)
        elif choice == "6":
            run_initialization_wizard(cfg)
        elif choice == "7":
            print("\nClosing workspace utilities safely. Goodbye.")
            sys.exit(0)
        else:
            print("\n[!] Input entry invalid. Select an index value between 1 and 7.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nWorkspace broken by administrative shutdown execution command.")
        sys.exit(0)











