"""DA-G2 diagnostic: audit the 915 MHz RF nets on drone-arm Rev B.

Read-only. Extracts, per RF-ish net: segment count, via count, distinct trace
widths, layers used, total routed length and endpoint coordinates. This is a
geometry/net audit only -- it is NOT an impedance solve, NOT an S-parameter
result and NOT a sign-off. Run with KiCad's bundled Python (needs pcbnew).
"""
from __future__ import annotations

import json
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "main_rev_b.kicad_pcb"
OUT = sys.argv[2] if len(sys.argv) > 2 else "rf915_audit.json"

board = pcbnew.LoadBoard(BOARD)

nets: dict[str, dict] = {}
for item in board.GetTracks():
    name = item.GetNetname()
    entry = nets.setdefault(
        name, {"segments": 0, "vias": 0, "widths_mm": set(), "layers": set(), "length_mm": 0.0}
    )
    if item.Type() == pcbnew.PCB_VIA_T:
        entry["vias"] += 1
        entry["layers"].add("via")
    else:
        entry["segments"] += 1
        entry["widths_mm"].add(round(item.GetWidth() / 1e6, 4))
        entry["layers"].add(item.GetLayerName())
        entry["length_mm"] += item.GetLength() / 1e6

rf_names = sorted(n for n in nets if any(k in n.upper() for k in ("RF", "915", "ANT")))

# Pads on RF-ish nets, for connectivity questions.
pads: dict[str, list] = {}
for fp in board.GetFootprints():
    for pad in fp.Pads():
        name = pad.GetNetname()
        if name in rf_names:
            pads.setdefault(name, []).append(
                {
                    "footprint": fp.GetReference(),
                    "pad": pad.GetNumber(),
                    "pos_mm": [round(pad.GetPosition().x / 1e6, 3), round(pad.GetPosition().y / 1e6, 3)],
                }
            )

# Stackup copper layers + dielectric hints.
stackup = []
settings = board.GetDesignSettings()
try:
    for layer in board.GetEnabledLayers().CuLayers():
        name = board.GetLayerName(layer)
        stackup.append({"layer": name, "thickness_mm": round(settings.GetLayerThickness(layer) / 1e6, 4)})
except Exception as exc:  # pragma: no cover - diagnostic only
    stackup.append({"error": str(exc)})

report = {
    "board": BOARD,
    "rf_nets": {
        name: {
            "segments": nets[name]["segments"],
            "vias": nets[name]["vias"],
            "widths_mm": sorted(nets[name]["widths_mm"]),
            "layers": sorted(nets[name]["layers"]),
            "length_mm": round(nets[name]["length_mm"], 3),
            "pads": pads.get(name, []),
        }
        for name in rf_names
    },
    "non_rf_note": "only nets matching RF/915/ANT are reported",
    "stackup_copper": stackup,
    "claim_boundary": (
        "Geometry and connectivity audit only. No impedance solve, no S-parameter "
        "result, no VNA measurement. Not fab sign-off."
    ),
}

with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)

for name, data in report["rf_nets"].items():
    print(
        f"{name:26s} segs={data['segments']:4d} vias={data['vias']:2d} "
        f"widths={data['widths_mm']} layers={data['layers']} len={data['length_mm']:.2f}mm "
        f"pads={len(data['pads'])}"
    )
print(f"\nwrote {OUT}")