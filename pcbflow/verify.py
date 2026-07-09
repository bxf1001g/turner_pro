"""Verify that the netlist KiCad extracted from the generated schematic
matches the design intent (the pin->net map of every part).

This guards against geometric mistakes in the generated schematic: two
stubs overlapping merges two nets; an off-position label leaves a pin
dangling. Both would silently corrupt the board.
"""

from __future__ import annotations

from pathlib import Path

from .design import NC, Design
from .sexpr import find, find_all, parse


def load_netlist(path: Path) -> dict[str, set]:
    doc = parse(Path(path).read_text())
    nets = {}
    for net in find_all(find(doc, "nets"), "net"):
        name = str(find(net, "name")[1])
        members = set()
        for node in find_all(net, "node"):
            ref = str(find(node, "ref")[1])
            pin = str(find(node, "pin")[1])
            members.add((ref, pin))
        nets[name] = members
    return nets


def intended_nets(design: Design) -> dict[str, set]:
    nets: dict[str, set] = {}
    for part in design.parts:
        for pin, net in part.nets.items():
            if net == NC:
                continue
            nets.setdefault(net, set()).add((part.ref, pin))
    return nets


def verify(design: Design, netlist_path: Path) -> list[str]:
    """Return a list of human-readable problems (empty = pass)."""
    problems = []
    actual = load_netlist(netlist_path)
    wanted = intended_nets(design)

    connected_pins = set()
    for name, members in actual.items():
        if name.startswith("unconnected-"):
            if len(members) > 1:
                problems.append(f"unconnected net {name} has multiple pins: {members}")
            continue
        connected_pins |= members

    for name, members in wanted.items():
        got = actual.get(name)
        if got is None:
            problems.append(f"net {name} missing from netlist (wanted {sorted(members)})")
            continue
        if got != members:
            extra = sorted(got - members)
            missing = sorted(members - got)
            msg = f"net {name} mismatch:"
            if missing:
                msg += f" missing {missing}"
            if extra:
                msg += f" unexpected {extra}"
            problems.append(msg)

    wanted_pins = set().union(*wanted.values()) if wanted else set()
    for name, members in actual.items():
        if name.startswith("unconnected-"):
            continue
        if name not in wanted:
            problems.append(f"unexpected net {name}: {sorted(members)}")
    for pin in wanted_pins - connected_pins:
        problems.append(f"pin {pin} ended up unconnected")
    return problems
