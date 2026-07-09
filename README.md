# pcbflow — PCB design automation

A pipeline that turns a high-level **requirements spec** (YAML) into a complete,
ERC-clean **KiCad 9 schematic**, plus netlist, BOM, and PDF/SVG exports —
no manual schematic drawing needed.

```
requirements.yaml ──> circuit blocks ──> .kicad_sch ──> ERC ──> verify netlist ──> PDF / SVG / BOM / .net
                      (power, MCU,       (KiCad 9,      (kicad-cli)  (extracted nets ==
                       radio, relays,     opens in       0 errors,    design intent,
                       sensors)           the GUI)       0 warnings)  every pin checked)
```

## Quick start

```bash
# prerequisites: KiCad 9 (kicad-cli + symbol/footprint libraries), Python 3.10+, PyYAML
sudo add-apt-repository -y ppa:kicad/kicad-9.0-releases
sudo apt-get install -y kicad kicad-symbols kicad-footprints
pip3 install -r requirements.txt

# generate the LoRa relay controller board
python3 -m pcbflow.pipeline designs/lora_relay_controller/requirements.yaml
```

Outputs land in `designs/lora_relay_controller/output/`:

| File | What it is |
|---|---|
| `lora_relay_controller.kicad_sch` | Schematic — open directly in KiCad 9 (eeschema) |
| `lora_relay_controller.pdf` | Printable schematic |
| `svg/lora_relay_controller.svg` | Vector render |
| `lora_relay_controller.net` | Netlist for PCB layout |
| `lora_relay_controller_bom.csv` | Grouped bill of materials |
| `erc.rpt` | Electrical rules check report |
| `sym-lib-table` | Project library table (resolves the custom RA-01SH symbol) |

## How it works

- `pcbflow/sexpr.py` — minimal S-expression parser/writer for KiCad file formats.
- `pcbflow/library.py` — loads installed KiCad symbol libraries, resolves derived
  (`extends`) symbols, and exposes exact pin geometry.
- `pcbflow/blocks.py` — circuit block generators (AC input + HLK converter, LM2596
  buck, ESP32 MCU with boot/reset strapping, SX126x LoRa radio, ULN2003A + relay
  channels, HMMD sensor header). Blocks read the spec and register pin→net maps.
- `pcbflow/schematic.py` — writes the `.kicad_sch`: places symbols, wire stubs,
  global labels, power symbols, PWR_FLAGs and no-connect markers on the KiCad grid.
- `pcbflow/verify.py` — re-imports the netlist KiCad extracted from the generated
  schematic and diffs it against the intended pin→net map. Any merged, missing, or
  dangling net fails the pipeline.
- `pcbflow/pipeline.py` — CLI glue: build → ERC → export PDF/SVG/netlist/BOM → verify.

## Editing the design

Change `designs/<name>/requirements.yaml` and re-run the pipeline. For example
`relays.channels: 2` generates a 2-channel board (driver inputs, coils, LEDs and
the output terminal all resize automatically).

New board? Copy the `designs/lora_relay_controller/` folder, edit the spec, run
the pipeline. New circuit blocks (e.g. a different MCU or radio) are added in
`pcbflow/blocks.py`; custom symbols live in `library/`.

## Tests

```bash
python3 -m pytest tests/ -v
```

Covers: ERC clean at `--severity-all`, netlist == design intent, key connectivity
spot checks (SPI bus, UART crossover, relay coils/contacts, AC path), and a
spec-driven variant (2 relay channels).
