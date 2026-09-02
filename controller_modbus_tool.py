#!/usr/bin/env python3
"""
FIELD SERIAL DIAGNOSTIC TOOL (Fully Optimised for Dixell XR77U Custom OEM)
Consolidates standalone scripts into a single workspace tailored to the Family 44 architecture.
"""

import sys
import time

# Verify global dependencies are accessible
try:
    import serial
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


def run_hardware_test():
    """Tool 1: Hardware & Serial Port Loopback Test [Safety-Enhanced for XR77U Setup]"""
    print("\n=== TOOL 1: HARDWARE & SERIAL PORT LOOPBACK TEST ===")
    print("⚠️  CRITICAL SAFETY WARNINGS FOR DIXELL XR77U HARDWARE BENCH TESTING:")
    print(" -> Ensure your USB-to-TTL adapter is locked strictly to 5V MODE (NOT 3.3V).")
    print(" -> If the controller is mains powered, DO NOT connect VCC/5V from the adapter.")
    print(" -> Ground loops from VCC backfeeding can permanently damage your PC ports.\n")
    
    port = input("Enter serial port to test (e.g. COM3): ").strip()
    if not port:
        return

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        print(f"[✓] Opened {port}. Connect TX to RX jumper wire (or A+ to B- terminals).")
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
            print(" -> Check hardware jumpers, pin cross-connections, or driver states.")
    except Exception as e:
        print(f"[X] Error opening port: {e}")
        
    input("\nPress ENTER to return to the main menu...")


def run_raw_sniffer():
    """Tool 2: Raw Byte Sniffer [Modbus RTU Frame-Aware Analyzer]"""
    print("\n=== TOOL 2: RAW BYTE SNIFFER & MODBUS FRAME ANALYSER ===")
    print("Monitors lines passively. Recognises custom Dixell Slave Address 1 patterns.")
    
    port = input("Enter serial port to sniff (e.g. /dev/ttyUSB0): ").strip()
    if not port:
        return
        
    baud_in = input("Enter Baud Rate [9600]: ").strip()
    baud = int(baud_in) if baud_in else 9600

    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.5)
        print(f"[✓] Sniffing active on {port} at {baud} bps. Press Ctrl+C to exit.\n")
        
        while True:
            if ser.in_waiting > 0:
                # Small wait window to collect entire industrial serial stream
                time.sleep(0.04)
                data = ser.read(ser.in_waiting)
                hex_out = " ".join(f"{b:02X}" for b in data)
                
                analysis = ""
                # Dynamically analyze if data is a likely Modbus packet for our locked Address 1
                if len(data) >= 4 and data[0] == 0x01:
                    func = data[1]
                    if func in [0x03, 0x06, 0x10, 0x83, 0x86, 0x90]:
                        msg_bytes = data[:-2]
                        expected_crc = calculate_modbus_crc(msg_bytes)
                        actual_crc = data[-2:]
                        
                        if expected_crc == actual_crc:
                            if func == 0x03:
                                analysis = " -> [Valid Modbus RTU Read Frame]"
                            elif func == 0x06:
                                analysis = " -> [Valid Modbus RTU Write Frame]"
                            elif func & 0x80:
                                analysis = " -> [Modbus EXCEPTION/ERROR Response Code]"
                        else:
                            analysis = " -> [Modbus Packet Layout Matched BUT CRC Check FAILED]"

                print(f"[{time.strftime('%H:%M:%S')}] {hex_out}{analysis}")
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            
    input("\nPress ENTER to return to the main menu...")


def run_modbus_reader():
    """Tool 3: Targeted Dixell XR77U Custom Modbus Poller"""
    print("\n=== TOOL 3: DIXELL XR77U CUSTOM TARGETED MODBUS POLLER ===")
    
    # Step 1: Physical Hardware Selector Topology
    print("Select Your Current Physical Hardware Layout:")
    print("  1) Method A: Direct USB-to-TTL to Controller (Direct 5V Micro-bus)")
    print("  2) Method B: Controller -> XJ485CX -> USB-to-RS485 Adapter")
    
    hw_choice = ""
    while hw_choice not in ["1", "2"]:
        hw_choice = input("Select Setup Option (1 or 2): ").strip()
        if hw_choice not in ["1", "2"]:
            print("[!] Invalid selection. Enter 1 or 2.")
            
    hw_mode = "Method A (Direct 5V TTL)" if hw_choice == "1" else "Method B (RS-485 via XJ485CX)"
    timeout_val = 0.4 if hw_choice == "1" else 0.6  # Dynamic delay buffer configuration
    
    port = input("\nEnter serial port (e.g. COM3): ").strip()
    if not port:
        return
        
    # Hardcoded Custom Profile Rules
    slave_id = 1
    REG_ROOM_TEMP = 256  # 0x0100
    REG_EVAP_TEMP = 257  # 0x0101
    REG_SETPOINT  = 512  # 0x0200
    REG_DIFF      = 513  # 0x0201

    # Initialize MinimalModbus mapping constraints
    try:
        instrument = minimalmodbus.Instrument(port, slave_id)
        instrument.serial.baudrate = 9600
        instrument.serial.bytesize = 8
        instrument.serial.parity = serial.PARITY_NONE
        instrument.serial.stopbits = 1
        instrument.serial.timeout = timeout_val
        instrument.mode = minimalmodbus.MODE_RTU
        print(f"[✓] Modbus engine online on {port} targeting hardcoded Address {slave_id}.")
    except Exception as e:
        print(f"[X] Engine Initialization Failed: {e}")
        input("\nPress ENTER to return to menu...")
        return

    # Filtered Context Menu Loop
    while True:
        print(f"\n---------------------------------------------")
        print(f" Available Tests Under: {hw_mode}")
        print(f"---------------------------------------------")
        print(" 1) Read Live Telemetry (P1 Room Temp, P2 Evap Temp, Parameters)")
        print(" 2) Write Operational Parameter (Modify SEt Setpoint)")
        if hw_choice == "2":
            print(" 3) XJ485CX Transceiver Line Integrity & Packet Stress Test")
        print(" Q) Return to Main Menu")
        
        test_choice = input("\Select test choice: ").strip().upper()
        
        if test_choice == "Q":
            break
            
        elif test_choice == "1":
            print("\nReading live data telemetry streams (Ctrl+C to stop)...")
            try:
                while True:
                    try:
                        room_temp = instrument.read_register(REG_ROOM_TEMP, numberOfDecimals=1, signed=True)
                        evap_temp = instrument.read_register(REG_EVAP_TEMP, numberOfDecimals=1, signed=True)
                        setpoint  = instrument.read_register(REG_SETPOINT, numberOfDecimals=1, signed=True)
                        diff      = instrument.read_register(REG_DIFF, numberOfDecimals=1, signed=False)
                        
                        print(f"[{time.strftime('%H:%M:%S')}] Telemetry Decoded:")
                        print(f"  -> Room Probe Temp (P1):   {room_temp} °C")
                        print(f"  -> Evaporator Temp (P2):   {evap_temp} °C")
                        print(f"  -> Current Setpoint (SEt): {setpoint} °C")
                        print(f"  -> Differential (Hy):      {diff} °C")
                        print("-" * 35)
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] [ERROR] Stream Interrupted: {e}")
                    time.sleep(2.0)
            except KeyboardInterrupt:
                print("\nTelemetry loop stopped by user.")
                
        elif test_choice == "2":
            print("\nPreparing secure parameter override...")
            try:
                current_set = instrument.read_register(REG_SETPOINT, numberOfDecimals=1, signed=True)
                print(f"Current Setpoint reads: {current_set} °C")
                val_input = input("Enter new targeted Setpoint in °C: ").strip()
                if not val_input:
                    continue
                new_val = float(val_input)
                
                print("Broadcasting payload packet...")
                instrument.write_register(REG_SETPOINT, new_val, numberOfDecimals=1, signed=True)
                
                time.sleep(0.2)
                if instrument.read_register(REG_SETPOINT, numberOfDecimals=1, signed=True) == new_val:
                    print(f"[SUCCESS] Change verified on memory bank: {new_val} °C")
                else:
                    print("[WARNING] Write transaction processing verification failed.")
            except Exception as e:
                print(f"[ERROR] Transaction aborted: {e}")
                
        elif test_choice == "3" and hw_choice == "2":
            print("\nTesting XJ485CX transceiver physical stability over 10 loops...")
            success = 0
            for i in range(1, 11):
                try:
                    instrument.read_register(REG_ROOM_TEMP, numberOfDecimals=1, signed=True)
                    print(f"  [Cycle {i:02d}/10] Echo Frame: OK")
                    success += 1
                except Exception:
                    print(f"  [Cycle {i:02d}/10] Echo Frame: TIMEOUT/CRC_ERR")
                time.sleep(0.2)
            print(f"\n[RESULTS] Line stability score: {success * 10}%")
        else:
            print("[!] Request invalid or structural restriction applied to your hardware selection.")
            
        input("\nPress ENTER to continue inside current hardware block...")


def main_menu():
    """Core terminal workspace dispatcher loop."""
    while True:
        print("\n" + "="*50)
        print("    DIXELL XR77U FIELD SERVICE DIAGNOSTIC SUITE    ")
        print("="*50)
        print("1) Run Safety-Enhanced Hardware Loopback Test")
        print("2) Run Modbus RTU Raw Byte Frame Sniffer")
        print("3) Run Custom XR77U Targeted Modbus Poller")
        print("4) Exit Program")
        print("="*50)

        choice = input("Select an option (1-4): ").strip()
        if choice == "1": 
            run_hardware_test()
        elif choice == "2": 
            run_raw_sniffer()
        elif choice == "3": 
            run_modbus_reader()
        elif choice == "4":
            print("\nExiting workspace safely. Goodbye.")
            sys.exit(0)
        else:
            print("\n[!] Invalid Selection. Please type 1 to 4.")


if __name__ == "__main__":
    try: 
        main_menu()
    except KeyboardInterrupt: 
        sys.exit(0)







