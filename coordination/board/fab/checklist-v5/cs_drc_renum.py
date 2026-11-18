#!/usr/bin/env python3
"""v5 negative control: is Code-SDR's 0-error DRC a TRUE zero?

KiCad 9's annular/clearance check skips pads whose number is duplicated inside
their footprint (measured on the ESC in esc-drc-resolve: 42 reported vs 140 in
the pad census). Code-SDR has 316 duplicate-numbered pads, so its own 0-error
DRC could be hiding rings. This makes every pad number unique on a COPY (no
geometry, no net, no position changes) and re-runs the same rule set.

Reads  : ../fab-checklist-v4/drc/cs_own/ (a copy of the repo board + its project)
Writes : ./drc/cs_renum/ only.

Run: "C:/Program Files/KiCad/9.0/bin/python.exe" cs_drc_renum.py
"""
import json, os, shutil, subprocess
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(r"E:\engineering-portfolio-audit\evidence\fab-checklist-v4\drc", "cs_own")
DST = os.path.join(HERE, "drc", "cs_renum")
CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"


def main():
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    pcb = os.path.join(DST, "cs.kicad_pcb")

    b = pcbnew.LoadBoard(pcb)
    fps, pads = 0, 0
    for fp in b.GetFootprints():
        lst = list(fp.Pads())
        nums = {}
        for p in lst:
            nums[p.GetNumber()] = nums.get(p.GetNumber(), 0) + 1
        dup = {n for n, c in nums.items() if c > 1}
        if not dup:
            continue
        fps += 1
        for i, p in enumerate(lst):
            if p.GetNumber() in dup:
                p.SetNumber("D%d_%d" % (fps, i))
                pads += 1
    pcbnew.SaveBoard(pcb, b)

    js = os.path.join(DST, "drc_renum.json")
    r = subprocess.run([CLI, "pcb", "drc", pcb, "-o", js, "--format", "json",
                        "--severity-all", "--units", "mm"],
                       capture_output=True, text=True)
    j = json.load(open(js, encoding="utf-8"))
    v = j.get("violations", [])
    res = {
        "footprints_with_duplicate_pad_numbers": fps,
        "pads_renumbered": pads,
        "rc": r.returncode,
        "total": len(v),
        "errors": sum(1 for x in v if x.get("severity") == "error"),
        "warnings": sum(1 for x in v if x.get("severity") == "warning"),
        "unconnected_items": len(j.get("unconnected_items", [])),
        "by_type": {t: sum(1 for x in v if x.get("type") == t)
                    for t in sorted({x.get("type") for x in v})},
    }
    with open(os.path.join(HERE, "out", "cs_drc_renum.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()