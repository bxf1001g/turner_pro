"""End-to-end regression tests for the pcbflow pipeline.

Runs the full spec -> schematic -> kicad-cli ERC/netlist flow and checks
that KiCad's extracted connectivity matches the design intent.
Requires kicad-cli (KiCad 9) on PATH.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from pcbflow.blocks import BoardBuilder
from pcbflow.library import SymbolLibraries
from pcbflow.pipeline import KICAD_SYMBOL_DIR, REPO_ROOT
from pcbflow.schematic import write_project
from pcbflow.verify import load_netlist, verify

SPEC = REPO_ROOT / "designs/lora_relay_controller/requirements.yaml"

kicad = shutil.which("kicad-cli")
pytestmark = pytest.mark.skipif(kicad is None, reason="kicad-cli not installed")


def _build(tmp_path, spec_overrides=None):
    spec = yaml.safe_load(SPEC.read_text())
    if spec_overrides:
        for key, val in spec_overrides.items():
            spec[key] = {**spec.get(key, {}), **val}
    design = BoardBuilder(spec).build()
    libs = SymbolLibraries([KICAD_SYMBOL_DIR, REPO_ROOT / "library"])
    sch = write_project(design, libs, tmp_path)
    return design, sch


def _netlist(sch, tmp_path):
    net = tmp_path / "out.net"
    res = subprocess.run([kicad, "sch", "export", "netlist", "-o", str(net), str(sch)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return net


def test_erc_clean(tmp_path):
    _, sch = _build(tmp_path)
    rpt = tmp_path / "erc.rpt"
    res = subprocess.run(
        [kicad, "sch", "erc", "--severity-all", "--exit-code-violations", "-o", str(rpt), str(sch)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, rpt.read_text()


def test_netlist_matches_design_intent(tmp_path):
    design, sch = _build(tmp_path)
    problems = verify(design, _netlist(sch, tmp_path))
    assert not problems, "\n".join(problems)


def test_key_connectivity(tmp_path):
    design, sch = _build(tmp_path)
    nets = load_netlist(_netlist(sch, tmp_path))

    # LoRa SPI bus reaches the MCU
    assert ("U1", "29") in nets["LORA_NSS"] and ("U3", "15") in nets["LORA_NSS"]
    assert ("U1", "30") in nets["LORA_SCK"] and ("U3", "12") in nets["LORA_SCK"]
    # HMMD sensor UART crossover: sensor TX -> MCU RX2 (IO16)
    assert ("J3", "3") in nets["HMMD_TX"] and ("U1", "27") in nets["HMMD_TX"]
    # each relay coil is driven by its ULN2003A output
    assert ("K1", "2") in nets["RLY1_COIL"] and ("U4", "16") in nets["RLY1_COIL"]
    assert ("K4", "2") in nets["RLY4_COIL"] and ("U4", "13") in nets["RLY4_COIL"]
    # relay COM contacts bussed to +12V; NO contacts on the output terminal
    assert ("K1", "1") in nets["+12V"]
    assert ("K1", "3") in nets["OUT1"] and ("J4", "1") in nets["OUT1"]
    # AC path: terminal -> fuse -> converter, MOV across the input
    assert nets["AC_L"] == {("J1", "1"), ("F1", "1")}
    assert nets["AC_L_F"] == {("F1", "2"), ("RV1", "1"), ("PS1", "1")}
    # 3V3 rail feeds MCU, radio, and sensor header
    for member in [("U1", "2"), ("U3", "3"), ("J3", "1")]:
        assert member in nets["+3V3"]


def test_channel_count_is_spec_driven(tmp_path):
    design, sch = _build(tmp_path, {"relays": {"channels": 2}})
    refs = {p.ref for p in design.parts}
    assert "K2" in refs and "K3" not in refs
    problems = verify(design, _netlist(sch, tmp_path))
    assert not problems, "\n".join(problems)
