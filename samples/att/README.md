# ATT framework — example test cases

This folder holds the **ATT / RuBatch (ExcelToATT)** example artifacts used to
exercise the `att` adapter (`adapters/att_adapter.py`).

## Place the example files here

Drop the provided files into **this folder** (`samples/att/`):

| File | Type | What the adapter does with it |
|---|---|---|
| `260607_0811_Sim_CaliperStiffness_DiscTilt_Highdynamic_.zip` | Simulation result bundle | Scans every `*.xml` (and bundled `*.xlsb`) inside, dispatches by report root tag |
| `TM_CaliperStiffness_DiscTilt_Highdynamic_ExcelToATT.xlsb` | ExcelToATT authoring workbook | Reads signals → CIR inputs, `expected_*` → CIR assertions |
| `TM_CaliperStiffness_DiscTilt_init_ExcelToATT.xlsb` | ExcelToATT authoring workbook (init variant) | Same as above |

> Chat attachments are **not** written to disk, so these binaries must be copied
> here manually (or via the PowerShell snippet below) before parsing.

```powershell
# from wherever the originals live (e.g. your Downloads folder)
Copy-Item "<source>\260607_0811_Sim_CaliperStiffness_DiscTilt_Highdynamic_.zip" "samples\att\"
Copy-Item "<source>\TM_CaliperStiffness_DiscTilt_Highdynamic_ExcelToATT.xlsb"   "samples\att\"
Copy-Item "<source>\TM_CaliperStiffness_DiscTilt_init_ExcelToATT.xlsb"          "samples\att\"
```

## Parse them into the Common Internal Representation (CIR)

```powershell
$env:PYTHONUTF8=1
python samples\att\parse_att_sample.py
```

This prints the normalized `CIRSuite` (test cases, inputs, assertions) and any
parser warnings, so you can see exactly how each ATT artifact maps into the
framework-agnostic model.

## Requirements

Reading `.xlsb` workbooks needs `pyxlsb` (already added to `requirements.txt`):

```powershell
pip install pyxlsb
```
