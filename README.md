# Controller Serial Mapping Tool

Interactive terminal tool for proving communications, discovering readable
locations, mapping controller parameters and carefully verifying writes.

## Protocols and profiles

- Modbus RTU with an initial XR77U / 2C310000 firmware 5.9 profile.
- CAREL PJEZ TTL/key-port protocol using the proven `F1` table-dump sequence.

The XR77U profile starts with the 24 addresses recorded in
`Universal_R_Map.xlsx`. They are labelled `mapped_unverified` until checked on
the live controller. The CAREL profile contains the mappings proven during the
PJEZ investigation.

## Safety

Register discovery and before/after mapping are read-only. The program never
writes unknown locations. Controlled Modbus writing requires a mapped parameter,
a proposed value and the user typing `WRITE` exactly.

Do not write unknown probe, relay, compressor-protection, defrost or identity
settings on operating equipment. Do not bridge RS485 A and B; that is not a
valid RS485 loopback test.

## Raspberry Pi installation

```bash
cd ~/controller_modbus_tool
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python controller_modbus_tool.py
```

The XR77U adapter currently appears as `/dev/ttyUSB0`. A stable path from
`/dev/serial/by-id/` is preferable when available.

## First XR77U test

1. Choose `Test controller connection`.
2. Choose `Modbus RTU`, then `XR77U`.
3. Confirm `/dev/ttyUSB0`, the controller `Adr`, baud, parity and stop bits.
4. Once a known address responds, choose `Read mapped values`.
5. Use read-only discovery and mapping before controlled write verification.

## Mapping

The wizard captures readable locations, asks the user to change one controller
parameter, reads the same locations again and ranks changes. It suggests the
signed interpretation and scale, then asks:

```text
Confirm/edit scale [10]:
```

Press Enter to accept the suggestion or type another scale. Profiles are saved
as UTF-8 JSON in `profiles/`.

## Upload the existing repository to GitHub

From the repository folder on Windows PowerShell:

```powershell
cd "C:\Users\Rob\OneDrive - kimbreycontrols.co.uk\Desktop\GYRE\controller_modbus_tool"
git status
git add controller_modbus_tool.py README.md requirements.txt
git commit -m "Add guided Modbus and CAREL mapping"
git push
```

If Git reports that no upstream branch exists:

```powershell
git push -u origin main
```

Do not run `git init` or replace the remote because this folder is already linked
to GitHub.

## Update the Raspberry Pi

```bash
cd ~/controller_modbus_tool
git pull
source .venv/bin/activate
python -m pip install -r requirements.txt
python controller_modbus_tool.py
```
