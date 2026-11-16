#!/usr/bin/env python3
"""v5 check: does Code-SDR's DRC annular blind spot apply?

The ESC's DRC under-reports PTH rings because KiCad skips pads whose number is
duplicated inside their footprint (measured in esc-drc-resolve: 42 reported vs
140 in the census). Code-SDR's 0-error DRC is only a true zero if the same
blind spot is empty on this board. This counts it, row-level.

Reads a COPY only. Writes only ./out/cs_padcheck.json.

Run: "C:/Program Files/KiCad/9.0/bin/python.exe" cs_padcheck.py
"""
import json, os
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(r"E:\engineering-portfolio-audit\evidence\fab-checklist-v4\boards", "cs.kicad_pcb")
OUT = os.path.join(HERE, "out")


def main():
    os.makedirs(OUT, exist_ok=True)
    b = pcbnew.LoadBoard(BOARD)
    fps = list(b.GetFootprints())
    dup_fps, dup_pads = 0, 0
    ring = {}
    pth = 0
    below_0125, below_020 = [], []
    for fp in fps:
        pads = list(fp.Pads())
        nums = {}
        for p in pads:
            nums[p.GetNumber()] = nums.get(p.GetNumber(), 0) + 1
        dup = {n for n, c in nums.items() if c > 1}
        if dup:
            dup_fps += 1
            dup_pads += sum(1 for p in pads if p.GetNumber() in dup)
        for p in pads:
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                continue
            pth += 1
            d = p.GetDrillSize()
            sz = p.GetSize()
            drill = max(d.x, d.y) / 1e6
            r = (min(sz.x, sz.y) / 1e6 - drill) / 2.0
            k = "%.4f" % r
            ring[k] = ring.get(k, 0) + 1
            ref = "%s.%s" % (fp.GetReference(), p.GetNumber())
            if r < 0.125 - 1e-9:
                below_0125.append([ref, round(r, 4)])
            if r < 0.200 - 1e-9:
                below_020.append([ref, round(r, 4)])
    out = {
        "board": "cs (v4 copy = commit 1a20bd6, pre-fiducial)",
        "footprints": len(fps),
        "fiducial_footprints": sum(1 for f in fps if "Fiducial" in str(f.GetFPID().GetLibItemName())),
        "pth_pads": pth,
        "footprints_with_duplicate_pad_numbers": dup_fps,
        "pads_with_duplicate_numbers": dup_pads,
        "pth_ring_hist": dict(sorted(ring.items())),
        "pth_rings_below_0.125": len(below_0125),
        "pth_rings_below_0.200": len(below_020),
        "below_0.125_list": below_0125,
        "verdict": ("annular blind spot EMPTY -> DRC count is a true count"
                    if dup_pads == 0 else
                    "annular blind spot NON-EMPTY -> DRC under-counts rings"),
    }
    with open(os.path.join(OUT, "cs_padcheck.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "below_0.125_list"}, indent=1))


if __name__ == "__main__":
    main()