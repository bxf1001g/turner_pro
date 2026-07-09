"""In-memory design model produced by circuit blocks and consumed by writers."""

from __future__ import annotations

from dataclasses import dataclass, field


NC = "__NC__"  # explicit no-connect marker for a pin


@dataclass
class Part:
    ref: str
    lib_id: str
    value: str
    x: float  # schematic position, mm
    y: float
    rotation: int = 0
    footprint: str = ""  # empty -> use library default
    nets: dict[str, str] = field(default_factory=dict)  # pin number -> net name
    dnp: bool = False
    label_side_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class PowerTap:
    """A power-symbol attachment (GND / +12V / +3V3 / PWR_FLAG) at a pin."""

    part_ref: str
    pin_number: str
    symbol: str  # e.g. "power:GND"


@dataclass
class TextNote:
    text: str
    x: float
    y: float
    size: float = 2.0
    bold: bool = False


@dataclass
class Design:
    name: str
    title: str
    company: str = ""
    rev: str = "A"
    paper: str = "A2"
    parts: list[Part] = field(default_factory=list)
    power_taps: list[PowerTap] = field(default_factory=list)
    notes: list[TextNote] = field(default_factory=list)

    # Nets treated as power rails: labels drawn as small bar-style power taps
    rail_nets: set = field(default_factory=set)

    def add(self, part: Part) -> Part:
        if any(p.ref == part.ref for p in self.parts):
            raise ValueError(f"duplicate reference {part.ref}")
        self.parts.append(part)
        return part

    def tap(self, part_ref: str, pin: str, symbol: str):
        self.power_taps.append(PowerTap(part_ref, pin, symbol))

    def note(self, text: str, x: float, y: float, size: float = 2.0, bold: bool = False):
        self.notes.append(TextNote(text, x, y, size, bold))

    def part(self, ref: str) -> Part:
        for p in self.parts:
            if p.ref == ref:
                return p
        raise KeyError(ref)
