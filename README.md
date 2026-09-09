# Controller Serial Mapping Tool

Interactive terminal tool for proving communications, discovering readable
locations, mapping controller parameters and carefully verifying writes.

## Protocols and profiles

- Modbus RTU with an initial XR77U / 2C310000 firmware 5.9 profile.
- CAREL PJEZ TTL/key-port protocol using the proven `F1` table-dump sequence.

The XR77U profile starts with the 24 parameter addresses recorded in
`Universal_R_Map.xlsx`, plus the previously established live probe registers
Pb1=256, Pb2=257 and Pb3=258. They are labelled `mapped_unverified` until checked
on the live controller. The remaining workbook parameters are included as an
unmapped work queue. The CAREL profile contains mappings proven during the PJEZ
investigation.

Connection settings are entered once at startup and reused by every menu action.
Use `Change connection` only when moving to another controller or adapter.
Every prompt and submenu accepts `B` to return to the preceding/main menu.

Choose `N) Create a new blank profile` on the profile-selection screen for an
undocumented controller. Only a name, optional model/version and the connection
settings are needed. No manual, known addresses or predefined scaling is
required. Numeric values, text/enumerated values and Boolean/status points can
then be learned interactively and are saved to that profile as work proceeds.

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

Modbus discovery can scan all standard read areas without profile restrictions:

- Coils, function 01.
- Discrete inputs, function 02.
- Holding registers, function 03.
- Input registers, function 04.

## Mapping

The mapping menu remains open so several parameters can be mapped in one session.
The discovery result and active connection are reused rather than entered again.
It supports existing profile parameters, new numeric values, Boolean/status
points and manually known locations.

Mapping is snapshot-first. After selecting a parameter, change only that
parameter on the controller and press Enter. The tool rereads the unassigned
locations and compares them with the saved baseline. A single changed location
is offered automatically; when several change, only those candidates are shown.
For documented enums the new raw value is interpreted from the profile. For an
undocumented enum the tool asks for the new displayed text. For a numeric value
it asks only for the new displayed value and derives the likely signed/scaled
interpretation.

After saving, the assigned location is removed from the working snapshot and
the refreshed remaining snapshot is saved. Reopening the profile resumes from
that reduced pool. The original timestamped discovery is retained unchanged as
an audit record. Profiles are saved as UTF-8 JSON in `profiles/`.

Fixed/read-only values use a separate no-change workflow. Enter the value shown
on the controller and the tool matches it against the unassigned snapshot using
the documented or user-entered format. This is used for the Universal-R map
code, software release and three probe displays. A unique match is offered
automatically; multiple identical matches remain a user choice because a fixed
value provides no second change with which to distinguish them.

Candidate selection defaults to `R` (reject) rather than forcing the first
candidate. Only exact before/after matches are presented as candidates.

Boolean/status mapping compares a user-created state change. This works with
coils, discrete inputs and 0/1 register values. Unknown coils are never written.
After a successful identification the tool leaves the controller at its changed
value; restore it manually only when the application requires it.

Verification is a separate, user-led menu. Default/reference values imported
from a workbook never verify a live controller automatically. For one or all
mapped points, the program displays the raw and decoded value and asks the user
to confirm it against the physical controller. Text responses create enum
mappings. Evidence states include `mapped_unverified`, `value_matched`,
`user_verified`, `change_verified` and `write_verified`.

The XR77U profile also includes the enumerated choices documented in the
Universal-R manual. During enum mapping the tool explains that the parameter
label and displayed setting are different. For example, `dFd` is the parameter
name while `dEF` is setting 3. A before/after read is still used to prove the
actual Modbus address. If exactly one location changes, the tool offers to save
it immediately instead of making the user select it from a one-item list.

Every discovery scan is saved under `discoveries/` and linked from the active
profile. Choose `Export profile/map` to create a timestamped folder under
`exports/` containing:

- `profile.json` — the complete reusable machine-readable profile.
- `map.csv` — a spreadsheet-friendly parameter/register map (UTF-8 with BOM).
- `map.md` — a concise human-readable report.
- `latest_discovery.json` — the most recent discovery scan, when available.

Both divide scaling and multiply scaling are supported. For example, raw 80
divided by 10 is 8.0, while raw 9 multiplied by 10 is 90.

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
