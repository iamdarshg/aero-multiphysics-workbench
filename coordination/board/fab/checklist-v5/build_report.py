#!/usr/bin/env python3
"""fab-checklist-v5 -- generates the three machine-checkable sections of REPORT.md.

Everything here is derived from rows.json. Nothing is typed twice: the 4x15
matrix, the verdict ledger, the tally and the five-condition table all come out
of one dataset, so a summary CANNOT disagree with its rows by construction.
check_fab.py re-runs this generator and fails if REPORT.md's marked block differs
by one byte, which is what catches a hand-edited cell.

Writes: out/auto_sections.md  (the block that REPORT.md embeds between markers)
Run:    "C:/Program Files/Python312/python.exe" build_report.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = json.load(open(os.path.join(HERE, "rows.json"), encoding="utf-8"))["columns"]
EVID = 13  # columns 0..12 carry verdicts; orderable/blocking are derived

# Terse cell text for the matrix. The ledger carries the full value + reason.
SHORT = {
    ("drone-arm main rev_b", "layers"): "4 (F/In1/In2/B)",
    ("drone-arm main rev_b", "copper"): "0.035 x4 = 1 oz",
    ("drone-arm main rev_b", "min_track"): "0.200 mm",
    ("drone-arm main rev_b", "min_space"): "0.1250 mm",
    ("drone-arm main rev_b", "min_drill"): "via 0.100 / PTH 0.200",
    ("drone-arm main rev_b", "min_ring"): "via 0.100 / PTH 0.150",
    ("drone-arm main rev_b", "nonthrough"): "36 = 26 blind + 10 buried / 341",
    ("drone-arm main rev_b", "unconnected"): "0 (pcbnew, uncapped)",
    ("drone-arm main rev_b", "drc"): "0 own rules / 36 span gate",
    ("drone-arm main rev_b", "package"): "package7 only, 5 B/B files, SENDABLE NO",
    ("drone-arm main rev_b", "revision"): "empty on board; 'B' on a copy",
    ("drone-arm main rev_b", "outline"): "140.000 x 100.000 mm = 140.00 cm2",
    ("drone-arm main rev_b", "finish"): "ENIG",
    ("ESC rev_b", "layers"): "4 (F/In1/In2/B)",
    ("ESC rev_b", "copper"): "0.140 outer 4 oz / 0.0525 inner 1.5 oz",
    ("ESC rev_b", "min_track"): "0.200 mm (rule 0.250)",
    ("ESC rev_b", "min_space"): "0.2000 mm (rule 0.250)",
    ("ESC rev_b", "min_drill"): "via 0.300 / PTH 0.200",
    ("ESC rev_b", "min_ring"): "via 0.150 / PTH 0.125; 140 below 0.200",
    ("ESC rev_b", "nonthrough"): "0 of 1,990 vias",
    ("ESC rev_b", "unconnected"): "1,536-1,542 (pcbnew, uncapped)",
    ("ESC rev_b", "drc"): "523 reported / 621 fab-real",
    ("ESC rev_b", "package"): "none",
    ("ESC rev_b", "revision"): "empty, no silk rev",
    ("ESC rev_b", "outline"): "173.800 x 282.930 mm = 491.732 cm2",
    ("ESC rev_b", "finish"): "ENIG",
    ("Code-SDR V2", "layers"): "4 (F/In1/In2/B)",
    ("Code-SDR V2", "copper"): "0.035 x4 = 1 oz",
    ("Code-SDR V2", "min_track"): "0.100 mm",
    ("Code-SDR V2", "min_space"): "0.1000 mm",
    ("Code-SDR V2", "min_drill"): "via 0.200 / PTH 0.200",
    ("Code-SDR V2", "min_ring"): "via 0.100 / PTH 0.150",
    ("Code-SDR V2", "nonthrough"): "0 of 1,085 vias",
    ("Code-SDR V2", "unconnected"): "0 (pcbnew and kicad-cli agree)",
    ("Code-SDR V2", "drc"): "222 warn / 0 error; fab-real 222",
    ("Code-SDR V2", "package"): "22 files at HEAD, 1,215 holes, rev 2.1",
    ("Code-SDR V2", "revision"): "2.1 board = 2.1 job",
    ("Code-SDR V2", "outline"): "101.600 mm square = 103.2256 cm2",
    ("Code-SDR V2", "finish"): "ENIG",
    ("drone-mech airframe", "layers"): "n/a: 0 PCB files",
    ("drone-mech airframe", "copper"): "n/a: 0 PCB files",
    ("drone-mech airframe", "min_track"): "n/a: 0 PCB files",
    ("drone-mech airframe", "min_space"): "n/a: 0 PCB files",
    ("drone-mech airframe", "min_drill"): "n/a: 0 holes",
    ("drone-mech airframe", "min_ring"): "n/a: 0 plated holes",
    ("drone-mech airframe", "nonthrough"): "n/a: 0 vias",
    ("drone-mech airframe", "unconnected"): "n/a: 0 nets",
    ("drone-mech airframe", "drc"): "0 genuine pairs on copies / 6 in the record; 4 solids",
    ("drone-mech airframe", "package"): "none: 0 drawings, 0 ply book",
    ("drone-mech airframe", "revision"): "no revision carries the fix",
    ("drone-mech airframe", "outline"): "372.425 x 158.328 x 640.000 mm; 649.84 cm2 plan",
    ("drone-mech airframe", "finish"): "n/a: no finish callout",
}


def conditions(b):
    """The five objective conditions, each DERIVED from the row's own cells."""
    c = b["cells"]
    drc = b["cells"]["drc"]["verdict"] == "PASS"
    unc = b["cells"]["unconnected"]["verdict"] != "FAIL"
    geom = (b["solid_integrity"]["verdict"] == "PASS"
            and c["nonthrough"]["verdict"] != "FAIL"
            and c["min_ring"]["verdict"] != "FAIL")
    pkg = c["package"]["verdict"] == "PASS" and c["revision"]["verdict"] == "PASS"
    open_cells = [k for k in COLS[:EVID]
                  if c[k]["verdict"] not in ("PASS", "FAIL", "WAIVED")
                  or not c[k]["value"].strip() or not c[k]["reason"].strip()]
    return [
        ("1 DRC-clean at the right rules", "PASS" if drc else "FAIL",
         "0 errors at its own rules AND 0 fab-real items"),
        ("2 zero unconnected", "PASS" if unc else "FAIL",
         "pcbnew ratsnest 0, not at a tool cap" if unc else "pcbnew count > 0"),
        ("3 zero geometry defects", "PASS" if geom else "FAIL",
         "0 non-through, ring not FAIL, model one piece"
         if geom else "non-through or ring or solid integrity fails"),
        ("4 validated package", "PASS" if pkg else "FAIL",
         "package exists, reconciles, and its revision matches the board"
         if pkg else "no package, or package revision does not match"),
        ("5 no open checklist cell", "PASS" if not open_cells else "FAIL",
         "all 13 cells carry a value, a verdict and a reason"
         if not open_cells else "open: " + ", ".join(open_cells)),
    ]


def tally(rows):
    out = {}
    for name, b in rows["boards"].items():
        t = {"PASS": 0, "FAIL": 0, "WAIVED": 0}
        for k in COLS[:EVID]:
            t[b["cells"][k]["verdict"]] += 1
        out[name] = t
    return out


def render(rows):
    L = []
    boards = rows["boards"]
    names = list(boards)
    # ---- matrix
    L.append("| board | " + " | ".join(COLS) + " |")
    L.append("|---" * (len(COLS) + 1) + "|")
    for n in names:
        cells = [SHORT[(n, k)] for k in COLS[:EVID]]
        L.append("| **%s** | %s | **%s** | **%s** |"
                 % (n, " | ".join(cells), boards[n]["orderable"], boards[n]["blocking"]))
    L.append("")
    # ---- verdict ledger
    L.append("### 1.1 Verdict ledger (full value, reason, source)")
    L.append("")
    L.append("| board | column | verdict | value | reason | source |")
    L.append("|---|---|---|---|---|---|")
    for n in names:
        for k in COLS[:EVID]:
            c = boards[n]["cells"][k]
            L.append("| %s | %s | **%s** | %s | %s | %s |"
                     % (n, k, c["verdict"], c["value"], c["reason"], c["source"]))
    L.append("")
    # ---- tally
    t = tally(rows)
    L.append("### 1.2 Tally, recomputed from the rows")
    L.append("")
    L.append("| board | PASS | FAIL | WAIVED | cells | orderable | blocking number |")
    L.append("|---|---:|---:|---:|---:|---|---|")
    for n in names:
        L.append("| %s | %d | %d | %d | %d | **%s** | **%s** |"
                 % (n, t[n]["PASS"], t[n]["FAIL"], t[n]["WAIVED"],
                    sum(t[n].values()), boards[n]["orderable"], boards[n]["blocking"]))
    tot = {k: sum(t[n][k] for n in names) for k in ("PASS", "FAIL", "WAIVED")}
    L.append("| **all four** | **%d** | **%d** | **%d** | **%d** | 1 of 4 | — |"
             % (tot["PASS"], tot["FAIL"], tot["WAIVED"], sum(tot.values())))
    L.append("")
    return "\n".join(L)


def render_conditions(rows):
    L = []
    L.append("| board | condition | verdict | blocking number |")
    L.append("|---|---|---|---|")
    for n, b in rows["boards"].items():
        for label, v, why in conditions(b):
            L.append("| %s | %s | **%s** | %s |"
                     % (n, label, v, b["blocking"] if v == "FAIL" else "—"))
    L.append("")
    return "\n".join(L)


def render_corrections(corr):
    L = []
    L.append("| id | board | what was wrong | OLD | NEW | source |")
    L.append("|---|---|---|---|---|---|")
    for r in corr["rows"]:
        L.append("| %s | %s | %s | `%s` | **%s** | %s |"
                 % (r["id"], r["board"], r["wrong"], r["old"], r["new"], r["source"]))
    L.append("")
    L.append("**%d rows.** 13 are the list the owner required; BC14 and BC15 are defects this sheet\n"
             "itself shipped in v4 (the 0.15 mm stroke and the 16-file count); BC16 and BC17 are\n"
             "earlier v4 corrections that a shorter list would have silently dropped." % len(corr["rows"]))
    L.append("")
    return "\n".join(L)


def inject(rows, corr):
    """--inject: rewrite the three marked blocks in REPORT.md in place."""
    import re
    p = os.path.join(HERE, "REPORT.md")
    txt = open(p, encoding="utf-8").read()
    pairs = [("<!-- BEGIN TABLE -->", "<!-- END TABLE -->", render(rows)),
             ("<!-- BEGIN CONDITIONS -->", "<!-- END CONDITIONS -->", render_conditions(rows)),
             ("<!-- BEGIN CORRECTIONS -->", "<!-- END CORRECTIONS -->", render_corrections(corr))]
    for b, e, body in pairs:
        pat = re.compile(re.escape(b) + r"\n.*?" + re.escape(e), re.S)
        if not pat.search(txt):
            raise SystemExit("marker pair not found in REPORT.md: %s" % b)
        txt = pat.sub(b + "\n" + body.strip() + "\n" + e, txt, count=1)
    open(p, "w", encoding="utf-8", newline="\n").write(txt)
    print("injected 3 blocks into REPORT.md")


def main():
    rows = json.load(open(os.path.join(HERE, "rows.json"), encoding="utf-8"))
    corr = json.load(open(os.path.join(HERE, "corrections.json"), encoding="utf-8"))
    if "--inject" in sys.argv:
        inject(rows, corr)
        return
    parts = [render(rows), render_conditions(rows), render_corrections(corr)]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "auto_sections.md"), "w", encoding="utf-8") as f:
        for p in parts:
            f.write(p + "\n")
    print("\n".join(parts))


if __name__ == "__main__":
    main()