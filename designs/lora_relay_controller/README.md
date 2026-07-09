# LoRa 4-Channel Relay Controller with Human Detection

Generated from `requirements.yaml` by the pcbflow pipeline. Open
`output/lora_relay_controller.kicad_sch` in KiCad 9.

## Architecture

- **220V AC input** — Phoenix MKDS 5.08mm pluggable terminal block → T2A 250V fuse
  → S14K275 MOV → **HLK-20M12** AC/DC module (12V, 20W).
- **+3V3 rail** — LM2596S-3.3 buck (SS34 catch diode, 33µH inductor,
  100µF in / 220µF out) from the 12V rail; powers MCU, radio, sensor.
- **MCU** — ESP32-WROOM-32E (industrial grade, −40…+85°C). EN RC reset
  (10k + 1µF), IO0 boot pull-up, decoupling, 6-pin **UART flashing header**
  (3V3 / GND / EN / IO0 / TXD / RXD — ESP-Prog style, auto-program capable).
- **LoRa** — Ai-Thinker **RA-01SH** (Semtech SX1262, 803–930MHz) on SPI,
  with SMA antenna connector.
- **Relays** — 4× SANYOU SRD-12VDC-SL-C (SPDT) driven by a ULN2003A darlington
  array (built-in flyback diodes via the COM pin to +12V). Coil-side red status
  LED per channel. COM contacts are bussed to +12V (per the product block
  diagram); NO contacts go to the output terminal.
- **Human detection** — 5-pin header for the Waveshare **HMMD mmWave sensor**
  (3.3V, UART @115200 + OT2 presence GPIO).
- **Output** — Phoenix MKDS 6-pos terminal: OUT1…OUT4, +12V, GND.

## Note on "SX1268 900MHz"

The requirements asked for SX1268 at 900MHz. The SX1268 only covers
410–810MHz (Ra-01S module: 410–525MHz). For the 900MHz band, the correct part
is the pin-compatible **SX1262** — hence the RA-01SH (803–930MHz) in this design.
If you actually need 433/470MHz, swap the module for a Ra-01S (SX1268); it is
footprint- and pin-identical, no schematic change required.

## ESP32 GPIO map

| GPIO | Net | Function |
|---|---|---|
| IO5 / IO18 / IO19 / IO23 | LORA_NSS / SCK / MISO / MOSI | LoRa SPI (VSPI) |
| IO21 / IO22 / IO4 | LORA_RST / BUSY / DIO1 | LoRa control |
| IO32 / IO33 | LORA_TXEN / RXEN | LoRa RF switch |
| IO13 / IO14 / IO25 / IO26 | RELAY1…RELAY4 | Relay drive (via ULN2003A) |
| IO17 / IO16 | HMMD_RX / HMMD_TX | Sensor UART2 (crossover) |
| IO35 | PRESENCE | Sensor OT2 presence output (input-only pin) |
| IO0, EN, TXD0, RXD0 | — | Boot / flashing header |

## Safety notes for layout

- Keep ≥6mm creepage between the 220V AC section and everything else; slot the
  board under the HLK module per its datasheet.
- Relay contact traces: size for the switched load; the SRD contacts are rated
  10A but the terminal blocks and traces set the real limit.
- Keep the SMA feedline short (50Ω), ground pour under the RA-01SH except the
  antenna pad keepout.
