"""End-to-end pipeline: requirements.yaml -> KiCad schematic + checks + exports.

Usage:
    python3 -m pcbflow.pipeline designs/<name>/requirements.yaml [-o output_dir]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from .blocks import BoardBuilder
from .library import SymbolLibraries
from .schematic import write_project
from .verify import verify

KICAD_SYMBOL_DIR = "/usr/share/kicad/symbols"
REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True)


def build(spec_path: Path, out_dir: Path | None) -> int:
    spec = yaml.safe_load(spec_path.read_text())
    builder = BoardBuilder(spec)
    design = builder.build()

    out = out_dir or spec_path.parent / "output"
    libs = SymbolLibraries([KICAD_SYMBOL_DIR, REPO_ROOT / "library"])
    sch = write_project(design, libs, out)
    print(f"schematic: {sch}")

    kicad = shutil.which("kicad-cli")
    if not kicad:
        print("kicad-cli not found; skipping ERC and exports", file=sys.stderr)
        return 0

    ok = True

    erc = run([kicad, "sch", "erc", "--severity-error", "--exit-code-violations",
               "-o", str(out / "erc.rpt"), str(sch)])
    print((out / "erc.rpt").read_text())
    if erc.returncode != 0:
        print("ERC FAILED", file=sys.stderr)
        ok = False

    for fmt, name in (("pdf", f"{design.name}.pdf"), ("svg", "svg")):
        res = run([kicad, "sch", "export", fmt, "-o", str(out / name), str(sch)])
        if res.returncode != 0:
            print(res.stderr, file=sys.stderr)
            ok = False

    net_path = out / f"{design.name}.net"
    res = run([kicad, "sch", "export", "netlist", "-o", str(net_path), str(sch)])
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        ok = False
    else:
        problems = verify(design, net_path)
        if problems:
            print(f"NETLIST VERIFICATION FAILED ({len(problems)} problems):", file=sys.stderr)
            for p in problems:
                print("  -", p, file=sys.stderr)
            ok = False
        else:
            print(f"netlist verification: OK ({len(design.parts)} parts, "
                  f"{sum(len(p.nets) for p in design.parts)} pin connections)")

    res = run([kicad, "sch", "export", "bom",
               "--fields", "Reference,Value,Footprint,${QUANTITY}",
               "--group-by", "Value,Footprint",
               "-o", str(out / f"{design.name}_bom.csv"), str(sch)])
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        ok = False

    print("pipeline", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="pcbflow: requirements -> KiCad schematic")
    ap.add_argument("spec", type=Path, help="path to requirements.yaml")
    ap.add_argument("-o", "--out", type=Path, default=None, help="output directory")
    args = ap.parse_args(argv)
    return build(args.spec, args.out)


if __name__ == "__main__":
    sys.exit(main())
