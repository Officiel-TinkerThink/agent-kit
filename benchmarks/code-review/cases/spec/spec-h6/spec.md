# Pump plan preview, monitor-unit export and infusion programs

Scope: dose preview (dose_calc.display_dose), monitor-unit export (plan_export),
infusion program construction (infusion) and the HTTP handlers in api.py.
Library data is read from config/drug_library.json.

## Requirements

- R1 The dose volume shown to the operator and the exported monitor-unit value agree within 0.01 mL (inclusive).
- R2 Infusion flow is stated in mL/h at every interface: API input, program record and pump export.
- R3 Drugs are referenced by stable drug_id. List position is never used to identify a drug.
- R4 Displayed and exported volumes are rounded half-up to 0.01.
- R5 A library version mismatch is an error: the loaded library must match the expected version, and a plan's recorded library version must match the library used to export it.
- R6 Doses above the order maximum are rejected on every path (preview and export).
