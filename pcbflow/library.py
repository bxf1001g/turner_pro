"""KiCad symbol library loader.

Loads ``.kicad_sym`` libraries, resolves ``extends`` (derived symbols) by
flattening them onto their parent, and exposes pin geometry so the
schematic generator can place global labels exactly on pin connection
points.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from .sexpr import QStr, find, find_all, parse


@dataclass
class Pin:
    number: str
    name: str
    etype: str  # electrical type: input/output/passive/power_in/...
    x: float  # connection point, symbol coords (y up)
    y: float
    angle: int  # 0 pin extends +x toward body, 90 +y, 180 -x, 270 -y
    length: float


class SymbolLibraries:
    """Resolves ``LibName:SymbolName`` ids across one or more search paths."""

    def __init__(self, search_paths):
        self.search_paths = [Path(p) for p in search_paths]
        self._lib_cache: dict[str, dict] = {}
        self._flat_cache: dict[str, list] = {}

    def _load_lib(self, lib_name: str) -> dict:
        if lib_name in self._lib_cache:
            return self._lib_cache[lib_name]
        for base in self.search_paths:
            path = base / f"{lib_name}.kicad_sym"
            if path.exists():
                doc = parse(path.read_text())
                symbols = {}
                for sym in find_all(doc, "symbol"):
                    symbols[str(sym[1])] = sym
                self._lib_cache[lib_name] = symbols
                return symbols
        raise FileNotFoundError(f"symbol library not found: {lib_name}.kicad_sym")

    def flattened(self, lib_id: str) -> list:
        """Return a flattened (extends-resolved) copy of the symbol definition."""
        if lib_id in self._flat_cache:
            return self._flat_cache[lib_id]
        lib_name, sym_name = lib_id.split(":", 1)
        symbols = self._load_lib(lib_name)
        if sym_name not in symbols:
            raise KeyError(f"symbol {sym_name!r} not in library {lib_name!r}")
        sym = copy.deepcopy(symbols[sym_name])

        ext = find(sym, "extends")
        if ext is not None:
            parent = copy.deepcopy(self.flattened(f"{lib_name}:{ext[1]}"))
            parent_name = str(parent[1])
            merged = [parent[0], QStr(sym_name)]
            child_props = {str(p[1]): p for p in find_all(sym, "property")}
            for item in parent[2:]:
                if not isinstance(item, list):
                    merged.append(item)
                    continue
                tag = item[0]
                if tag == "property":
                    pname = str(item[1])
                    merged.append(child_props.pop(pname, item))
                elif tag == "symbol":
                    # rename sub-units PARENT_u_s -> CHILD_u_s
                    unit = copy.deepcopy(item)
                    suffix = str(unit[1])[len(parent_name):]
                    unit[1] = QStr(sym_name + suffix)
                    merged.append(unit)
                else:
                    merged.append(item)
            for extra in child_props.values():
                merged.append(extra)
            sym = merged

        self._flat_cache[lib_id] = sym
        return sym

    def pins(self, lib_id: str) -> list[Pin]:
        sym = self.flattened(lib_id)
        out = []
        for unit in find_all(sym, "symbol"):
            for pin in find_all(unit, "pin"):
                at = find(pin, "at")
                length = find(pin, "length")
                name = find(pin, "name")
                number = find(pin, "number")
                out.append(
                    Pin(
                        number=str(number[1]),
                        name=str(name[1]),
                        etype=str(pin[1]),
                        x=float(at[1]),
                        y=float(at[2]),
                        angle=int(float(at[3])) if len(at) > 3 else 0,
                        length=float(length[1]) if length else 0.0,
                    )
                )
        return out

    def property_layout(self, lib_id: str) -> dict:
        """Reference/Value placement from the library: name -> (x, y, justify)."""
        out = {}
        for prop in find_all(self.flattened(lib_id), "property"):
            name = str(prop[1])
            if name not in ("Reference", "Value"):
                continue
            at = find(prop, "at")
            justify = []
            eff = find(prop, "effects")
            if eff is not None:
                j = find(eff, "justify")
                if j is not None:
                    justify = [str(t) for t in j[1:]]
            angle = float(at[3]) if len(at) > 3 else 0.0
            out[name] = (float(at[1]), float(at[2]), angle, justify)
        return out

    def default_footprint(self, lib_id: str) -> str:
        for prop in find_all(self.flattened(lib_id), "property"):
            if str(prop[1]) == "Footprint":
                return str(prop[2])
        return ""

    def embeddable(self, lib_id: str) -> list:
        """Symbol definition renamed for embedding in a schematic's lib_symbols."""
        sym = copy.deepcopy(self.flattened(lib_id))
        sym[1] = QStr(lib_id)
        ext = find(sym, "extends")
        if ext is not None:
            sym.remove(ext)
        return sym
