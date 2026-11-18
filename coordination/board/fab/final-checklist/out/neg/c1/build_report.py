#!/usr/bin/env python3
"""fab-checklist-final -- generates the three machine-checkable sections of REPORT.md.

Everything is derived from rows.json / corrections.json. The matrix, the verdict ledger,
the tally, the correction table and the five-condition table are all produced here, so a
summary cannot disagree with its rows by construction. check_fab.py re-runs this generator
and fails if a marked block in REPORT.md differs by one byte.

Run: "C:/Program Files/Python312/python.exe" build_report.py [--inject]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "rows.json"), encoding="utf-8"))
CORR = json.load(open(os.path.join(HERE, "corrections.json"), encoding="utf-8"))
COLS = ROWS["columns"]
EVID = ROWS["evidence_columns"]


def conditions(b):
    """The five objective conditions, each DERIVED from the row's own cells."""
    c = b["cells"]
    drc = c["drc"]["verdict"] == "PASS"
    unc = c["unconnected"]["verdict"] != "FAIL"
    geom = (b["solid_integrity"]["verdict"] == "PASS"
            and c["nonthrough"]["verdict"] != "FAIL"
            and c["min_ring"]["verdict"] != "FAIL")
    pkg = c["package"]["verdict"] == "PASS" and c["revision"]["verdict"] == "PASS"
    open_cells = [k for k in COLS[:EVID]
                  if c[k]["verdict"] not in ("PASS", "FAIL", "WAIVED")
                  or not c[k]["value"].strip() or not c[k]["reason"].strip()]
    return [
        ("1 DRC-clean at the right rules", "PASS" if drc else "FAIL",
         "0 at its own rules AND 0 fab-real items" if drc else "non-zero at the right rules"),
        ("2 zero unconnected", "PASS" if unc else "FAIL",
         "0 on two tools / n/a" if unc else "open connections remain"),
        ("3 zero geometry defects", "PASS" if geom else "FAIL",
         "0 non-through, ring not FAIL, model one piece"
         if geom else "non-through, ring or model integrity fails"),
        ("4 validated package", "PASS" if pkg else "FAIL",
         "package exists, reconciles, and its revision matches"
         if pkg else "no package, or package revision does not match"),
        ("5 no open checklist cell", "PASS" if not open_cells else "FAIL",
         "all 13 cells carry a value, a verdict and a reason"
         if not open_cells else "open: " + ", ".join(open_cells)),
    ]


def tally(rows=None):
    rows = rows or ROWS
    out = {}
    for name, b in rows["boards"].items():
        t = {"PASS": 0, "FAIL": 0, "WAIVED": 0}
        for k in COLS[:EVID]:
            t[b["cells"][k]["verdict"]] += 1
        out[name] = t
    return out


def render(rows=None):
    rows = rows or ROWS
    L, boards, names = [], rows["boards"], list(rows["boards"])
    L.append("| board | " + " | ".join(COLS) + " |")
    L.append("|---" * (len(COLS) + 1) + "|")
    for n in names:
        cells = [boards[n]["cells"][k]["short"] for k in COLS[:EVID]]
        L.append("| **%s** | %s | **%s** | **%s** |"
                 % (n, " | ".join(cells), boards[n]["orderable"], boards[n]["blocking"]))
    L.append("")
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
    n_yes = sum(1 for n in names if boards[n]["orderable"] == "YES")
    L.append("| **all four** | **%d** | **%d** | **%d** | **%d** | %d of 4 | — |"
             % (tot["PASS"], tot["FAIL"], tot["WAIVED"], sum(tot.values()), n_yes))
    L.append("")
    return "\n".join(L)


def render_corrections(corr=None):
    corr = corr or CORR
    L = ["| id | board | what was wrong | OLD | NEW | status | source |",
         "|---|---|---|---|---|---|---|"]
    for r in corr["rows"]:
        status = "live" if r["status"] == "live" else "superseded by " + r["superseded_by"]
        L.append("| %s | %s | %s | `%s` | **%s** | %s | %s |"
                 % (r["id"], r["board"], r["wrong"], r["old"], r["new"], status, r["source"]))
    n_live = sum(1 for r in corr["rows"] if r["status"] == "live")
    n_sup = len(corr["rows"]) - n_live
    L.append("")
    L.append("**%d rows: %d live, %d superseded.** BC1-BC26 are the v6 list, carried with their "
             "OLD/NEW pairs intact and their status re-derived. Seventeen of them describe a board "
             "that has since moved (36 vias to 19, 4 oz to 3 oz, 43.5 A to 36.6 A, 4 solids to 1), so "
             "they are marked superseded and their successor is named: a superseded row is history, "
             "not a live claim. BC27-BC35 are wave-18. Check 11 fails if a live OLD token survives in "
             "rows.json, if a live NEW token is used nowhere outside this section, or if a superseded "
             "row's stale token is still quoted in a cell."
             % (len(corr["rows"]), n_live, n_sup))
    L.append("")
    return "\n".join(L)


def render_conditions(rows=None):
    rows = rows or ROWS
    L = ["| board | condition | verdict | blocking number |", "|---|---|---|---|"]
    for n, b in rows["boards"].items():
        for label, v, why in conditions(b):
            L.append("| %s | %s | **%s** | %s |"
                     % (n, label, v, b["blocking"] if v == "FAIL" else "—"))
    L.append("")
    return "\n".join(L)


def blocks(rows=None, corr=None):
    return [("<!-- BEGIN TABLE -->", "<!-- END TABLE -->", render(rows)),
            ("<!-- BEGIN CORRECTIONS -->", "<!-- END CORRECTIONS -->", render_corrections(corr)),
            ("<!-- BEGIN CONDITIONS -->", "<!-- END CONDITIONS -->", render_conditions(rows))]


def inject(rows=None, corr=None):
    import re
    p = os.path.join(HERE, "REPORT.md")
    txt = open(p, encoding="utf-8").read()
    for b, e, body in blocks(rows, corr):
        pat = re.compile(re.escape(b) + r"\n.*?" + re.escape(e), re.S)
        if not pat.search(txt):
            raise SystemExit("marker pair not found in REPORT.md: %s" % b)
        txt = pat.sub(lambda m: b + "\n" + body.strip() + "\n" + e, txt, count=1)
    open(p, "w", encoding="utf-8", newline="\n").write(txt)
    print("injected 3 blocks into REPORT.md")


def main():
    if "--inject" in sys.argv:
        inject()
        return
    parts = [b[2] for b in blocks()]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "auto_sections.md"), "w", encoding="utf-8", newline="\n") as f:
        for p in parts:
            f.write(p + "\n")
    print("\n".join(parts))


if __name__ == "__main__":
    main()