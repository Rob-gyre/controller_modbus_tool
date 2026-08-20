# HVAC Modbus RTU Diagnostic & Polling Toolkit

A diagnostic suite for engineers and refrigeration technicians troubleshooting industrial serial links (TTL and RS485/Modbus RTU) on commercial controllers such as Dixell, Eliwell, and Carel.

## Repository Layout

*   `hvac_modbus_tool.py`: The production-grade multi-tool interface containing all modules under a unified prompt framework.
*   `requirements.txt`: Python package requirements setup.
*   `legacy_tools/`: A reference archive containing historical standalone single-purpose diagnostic blocks.
    *   `serial_USB_test.py`: Isolated serial OS bus/port driver and physical loopback line tester.
    *   `ttl_raw_capture.py`: Non-blocking passive hexadecimal byte logger for bus analysis.
    *   `read_dixell.py`: Hardcoded single-device blueprint polling script.

## Core Features

1. **Hardware Loopback Validation**: Validates laptop hardware drivers, local USB-to-RS485 conversion chips, and internal COM port assignments without protocol checking overheads.
2. **Raw Hex Passive Sniffer**: Listens without frame structures to log data packets to inspect noise, error frames, or total device silence.
3. **Dynamic Modbus RTU Poller Engine**: Maps holding registers cleanly to inspect telemetry points with dynamic parameters for Baud Rate, Parity options, and Stop bit tracking. Integrates active signed binary calculations (two's complement) for negative Celsius tracking below freezers.

## Getting Started

### Installation
Ensure dependencies are satisfied locally:
```bash
pip install -r requirements.txt
```

### Execution
Launch the comprehensive multi-tool script directly:
```bash
python hvac_modbus_tool.py
```
