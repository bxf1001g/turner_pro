"""Circuit block generators.

Each block turns one section of the requirements spec into placed,
netted components. Net connectivity is by net name (global labels);
positions only affect readability of the generated schematic.
"""

from __future__ import annotations

from .design import NC, Design, Part

# ESP32-WROOM-32E symbol pin numbers, by function.
ESP32_PINS = {
    "EN": "3", "SENSOR_VP": "4", "SENSOR_VN": "5",
    "IO0": "25", "IO2": "24", "IO4": "26", "IO5": "29",
    "IO12": "14", "IO13": "16", "IO14": "13", "IO15": "23",
    "IO16": "27", "IO17": "28", "IO18": "30", "IO19": "31",
    "IO21": "33", "IO22": "36", "IO23": "37",
    "IO25": "10", "IO26": "11", "IO27": "12",
    "IO32": "8", "IO33": "9", "IO34": "6", "IO35": "7",
    "TXD0": "35", "RXD0": "34", "VDD": "2", "GND": "1",
}

# GPIOs safe to allocate to relay channels (no boot strapping conflicts).
RELAY_GPIO_POOL = ["IO13", "IO14", "IO25", "IO26", "IO27", "IO15", "IO2", "IO12"]

R_0603 = "Resistor_SMD:R_0603_1608Metric"
C_0603 = "Capacitor_SMD:C_0603_1608Metric"
C_0805 = "Capacitor_SMD:C_0805_2012Metric"
LED_0805 = "LED_SMD:LED_0805_2012Metric"


class BoardBuilder:
    """Builds a Design from a parsed requirements spec."""

    def __init__(self, spec: dict):
        board = spec.get("board", {})
        self.spec = spec
        self.design = Design(
            name=board.get("name", "board"),
            title=board.get("title", board.get("name", "board")),
            company=board.get("company", ""),
            rev=str(board.get("rev", "A")),
            paper=board.get("paper", "A2"),
        )
        self.design.rail_nets = {"+12V", "+3V3", "+5V"}
        # J1 = AC input, U1 = MCU, D1 = buck diode are fixed references;
        # seed the counters so generated refs start after them.
        self._counters: dict[str, int] = {"J": 1, "U": 1, "D": 1}
        self.mcu_nets: dict[str, str] = {}  # ESP32 pin function -> net

    def _ref(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}{self._counters[prefix]}"

    # ------------------------------------------------------------------ #

    def build(self) -> Design:
        d = self.design
        d.note("1. AC INPUT & 12V POWER SUPPLY", 30, 35, size=3, bold=True)
        d.note("2. 3.3V BUCK REGULATOR (LM2596S-3.3)", 210, 35, size=3, bold=True)
        d.note("3. MCU - ESP32-WROOM-32E", 30, 120, size=3, bold=True)
        d.note("4. LORA RADIO (SX126x / RA-01SH)", 330, 120, size=3, bold=True)
        d.note("5. HUMAN DETECTION SENSOR (WAVESHARE HMMD)", 330, 230, size=3, bold=True)
        d.note("6. RELAY OUTPUTS x%d" % self.spec.get("relays", {}).get("channels", 4), 30, 270, size=3, bold=True)

        self.ac_power_block(origin=(50, 65))
        self.buck_3v3_block(origin=(230, 65))
        self.radio_block(origin=(420, 165))
        self.sensor_block(origin=(390, 260))
        self.relay_block(origin=(110, 330))
        self.mcu_block(origin=(140, 180))  # last: consumes accumulated net map
        return d

    # ------------------------------------------------------------------ #

    def ac_power_block(self, origin):
        x, y = origin
        d = self.design
        d.add(Part(
            ref="J1", lib_id="Connector:Screw_Terminal_01x02", value="220V AC IN",
            x=x, y=y,
            footprint="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-3-2-5.08_1x02_P5.08mm_Horizontal",
            nets={"1": "AC_L", "2": "AC_N"},
        ))
        d.add(Part(
            ref="F1", lib_id="Device:Fuse", value="T2A 250V",
            x=x + 30, y=y,
            footprint="Fuse:Fuseholder_Cylinder-5x20mm_Schurter_0031_8201_Horizontal_Open",
            nets={"1": "AC_L", "2": "AC_L_F"},
        ))
        d.add(Part(
            ref="RV1", lib_id="Device:Varistor", value="S14K275",
            x=x + 50, y=y,
            footprint="Varistor:RV_Disc_D15.5mm_W4.2mm_P7.5mm",
            nets={"1": "AC_L_F", "2": "AC_N"},
        ))
        hlk = d.add(Part(
            ref="PS1", lib_id="Converter_ACDC:HLK-20M12", value="HLK-20M12",
            x=x + 85, y=y,
            nets={"1": "AC_L_F", "2": "AC_N", "4": "+12V", "3": "GND"},
        ))
        d.tap(hlk.ref, "1", "power:PWR_FLAG")
        d.tap(hlk.ref, "2", "power:PWR_FLAG")
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C_Polarized", value="100uF 25V",
            x=x + 115, y=y + 5,
            footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
            nets={"1": "+12V", "2": "GND"},
        ))

    def buck_3v3_block(self, origin):
        x, y = origin
        d = self.design
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C_Polarized", value="100uF 25V",
            x=x - 25, y=y + 5,
            footprint="Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
            nets={"1": "+12V", "2": "GND"},
        ))
        u = d.add(Part(
            ref=self._ref("U"), lib_id="Regulator_Switching:LM2596S-3.3", value="LM2596S-3.3",
            x=x, y=y,
            nets={"1": "+12V", "5": "GND", "3": "GND", "2": "SW_3V3", "4": "+3V3"},
        ))
        d.tap(u.ref, "4", "power:PWR_FLAG")
        d.add(Part(
            ref="D1", lib_id="Diode:SS34", value="SS34",
            x=x + 30, y=y + 10,
            nets={"1": "SW_3V3", "2": "GND"},  # K = SW node, A = GND
            label_side_overrides={"1": "passive"},
        ))
        d.add(Part(
            ref="L1", lib_id="Device:L", value="33uH 3A",
            x=x + 45, y=y,
            footprint="Inductor_SMD:L_12x12mm_H8mm",
            nets={"1": "SW_3V3", "2": "+3V3"},
        ))
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C_Polarized", value="220uF 10V",
            x=x + 65, y=y + 5,
            footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
            nets={"1": "+3V3", "2": "GND"},
        ))

    def mcu_block(self, origin):
        x, y = origin
        d = self.design
        nets = {
            "VDD": "+3V3", "GND": "GND", "EN": "EN",
            "IO0": "IO0", "TXD0": "U0TXD", "RXD0": "U0RXD",
        }
        nets.update(self.mcu_nets)
        pin_nets = {}
        for func, net in nets.items():
            pin_nets[ESP32_PINS[func]] = net
        # extra stacked ground pins
        for p in ("15", "38", "39"):
            pin_nets[p] = "GND"
        d.add(Part(
            ref="U1", lib_id="RF_Module:ESP32-WROOM-32E", value="ESP32-WROOM-32E",
            x=x, y=y, nets=pin_nets,
            footprint="RF_Module:ESP32-WROOM-32E",
        ))
        # EN RC reset circuit
        d.add(Part(
            ref=self._ref("R"), lib_id="Device:R", value="10k",
            x=x - 75, y=y - 30, footprint=R_0603,
            nets={"1": "+3V3", "2": "EN"},
        ))
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C", value="1uF",
            x=x - 65, y=y - 10, footprint=C_0603,
            nets={"1": "EN", "2": "GND"},
        ))
        # IO0 boot pull-up
        d.add(Part(
            ref=self._ref("R"), lib_id="Device:R", value="10k",
            x=x - 55, y=y - 30, footprint=R_0603,
            nets={"1": "+3V3", "2": "IO0"},
        ))
        # decoupling
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C", value="100nF",
            x=x - 95, y=y - 10, footprint=C_0603,
            nets={"1": "+3V3", "2": "GND"},
        ))
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C", value="10uF",
            x=x - 85, y=y - 10, footprint=C_0805,
            nets={"1": "+3V3", "2": "GND"},
        ))
        # UART flashing header (ESP-Prog style)
        if self.spec.get("mcu", {}).get("uart_flash_header", True):
            d.add(Part(
                ref=self._ref("J"), lib_id="Connector_Generic:Conn_01x06", value="UART FLASH",
                x=x - 60, y=y + 45,
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
                nets={"1": "+3V3", "2": "GND", "3": "EN", "4": "IO0", "5": "U0TXD", "6": "U0RXD"},
                label_side_overrides={"5": "bidirectional", "6": "bidirectional"},
            ))

    def radio_block(self, origin):
        x, y = origin
        d = self.design
        gpio = {
            "NSS": "IO5", "SCK": "IO18", "MISO": "IO19", "MOSI": "IO23",
            "RST": "IO21", "BUSY": "IO22", "DIO1": "IO4",
            "TXEN": "IO32", "RXEN": "IO33",
        }
        for sig, io in gpio.items():
            self.mcu_nets[io] = f"LORA_{sig}"
        d.add(Part(
            ref=self._ref("U"), lib_id="ProtoFlow_RF:RA-01SH", value="RA-01SH",
            x=x, y=y,
            nets={
                "1": "RF_ANT", "2": "GND", "9": "GND", "16": "GND", "3": "+3V3",
                "4": "LORA_RST", "5": "LORA_TXEN", "11": "LORA_RXEN",
                "15": "LORA_NSS", "12": "LORA_SCK", "14": "LORA_MOSI",
                "13": "LORA_MISO", "10": "LORA_BUSY", "6": "LORA_DIO1",
                "7": NC, "8": NC,
            },
        ))
        d.add(Part(
            ref=self._ref("J"), lib_id="Connector:Conn_Coaxial", value="SMA ANT",
            x=x - 45, y=y - 7.62,
            footprint="Connector_Coaxial:SMA_Amphenol_132134_Vertical",
            nets={"1": "RF_ANT", "2": "GND"},
            label_side_overrides={"1": "passive"},
        ))
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C", value="100nF",
            x=x + 40, y=y, footprint=C_0603,
            nets={"1": "+3V3", "2": "GND"},
        ))
        d.add(Part(
            ref=self._ref("C"), lib_id="Device:C", value="10uF",
            x=x + 50, y=y, footprint=C_0805,
            nets={"1": "+3V3", "2": "GND"},
        ))

    def sensor_block(self, origin):
        x, y = origin
        d = self.design
        self.mcu_nets["IO17"] = "HMMD_RX"   # MCU TX2 -> sensor RX
        self.mcu_nets["IO16"] = "HMMD_TX"   # sensor TX -> MCU RX2
        self.mcu_nets["IO35"] = "PRESENCE"  # sensor OT2 digital presence output
        d.add(Part(
            ref=self._ref("J"), lib_id="Connector_Generic:Conn_01x05", value="HMMD mmWave",
            x=x, y=y,
            footprint="Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
            nets={"1": "+3V3", "2": "GND", "3": "HMMD_TX", "4": "HMMD_RX", "5": "PRESENCE"},
            label_side_overrides={"3": "input", "4": "output", "5": "input"},
        ))

    def relay_block(self, origin):
        x, y = origin
        d = self.design
        channels = int(self.spec.get("relays", {}).get("channels", 4))
        if channels > 7:
            raise ValueError("ULN2003A driver supports at most 7 channels")

        uln_nets = {"8": "GND", "9": "+12V"}
        out_nets = {}
        for ch in range(1, channels + 1):
            io = RELAY_GPIO_POOL[ch - 1]
            self.mcu_nets[io] = f"RELAY{ch}"
            uln_nets[str(ch)] = f"RELAY{ch}"       # inputs I1..In
            uln_nets[str(17 - ch)] = f"RLY{ch}_COIL"  # outputs O1..On (16,15,14,13...)
        d.add(Part(
            ref=self._ref("U"), lib_id="Transistor_Array:ULN2003A", value="ULN2003A",
            x=x, y=y,
            footprint="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm",
            nets=uln_nets,
        ))
        for ch in range(1, channels + 1):
            kx = x + 65 + (ch - 1) * 65
            d.add(Part(
                ref=f"K{ch}", lib_id="Relay:SANYOU_SRD_Form_C", value="SRD-12VDC-SL-C",
                x=kx, y=y,
                nets={"5": "+12V", "2": f"RLY{ch}_COIL", "1": "+12V", "3": f"OUT{ch}", "4": NC},
                label_side_overrides={"1": "passive", "3": "passive"},
            ))
            # coil-side status LED
            d.add(Part(
                ref=self._ref("D"), lib_id="Device:LED", value="RED",
                x=kx - 25, y=y + 35, footprint=LED_0805,
                nets={"2": "+12V", "1": f"RLY{ch}_LED"},
            ))
            d.add(Part(
                ref=self._ref("R"), lib_id="Device:R", value="1k",
                x=kx, y=y + 35, footprint=R_0603,
                nets={"1": f"RLY{ch}_LED", "2": f"RLY{ch}_COIL"},
            ))
            out_nets[str(ch)] = f"OUT{ch}"
        # output terminal block: OUT1..OUTn, +12V, GND
        out_nets[str(channels + 1)] = "+12V"
        out_nets[str(channels + 2)] = "GND"
        d.add(Part(
            ref=self._ref("J"), lib_id=f"Connector:Screw_Terminal_01x{channels + 2:02d}",
            value="RELAY OUT / 12V",
            x=x + 65 + channels * 65 + 30, y=y,
            footprint=f"TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-3-{channels + 2}-5.08_1x{channels + 2:02d}_P5.08mm_Horizontal",
            nets=out_nets,
            label_side_overrides={"5": "passive", "6": "passive"},
        ))
