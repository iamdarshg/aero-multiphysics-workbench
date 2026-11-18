#!/usr/bin/env python3
"""fab-checklist-v5 negative test -- the checker must FAIL when it should.

Four+ one-variable mutations of the sheet's own inputs, each run through
check_fab.py as a subprocess so the exit code is real, not asserted in-process.
Every mutation must produce exit 1 AND the specific check that should catch it
must appear in the output. A mutation that slips through is a hole in the
checker, and this script exits 1 for it.

Run: "C:/Program Files/Python312/python.exe" negative_test.py
"""
import copy, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEG = os.path.join(HERE, "out", "neg")
PY = sys.executable


def write(case, rows, corr, report):
    d = os.path.join(NEG, case)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    if rows is not None:
        json.dump(rows, open(os.path.join(d, "rows.json"), "w"), indent=1)
    if corr is not None:
        json.dump(corr, open(os.path.join(d, "corrections.json"), "w"), indent=1)
    if report is not None:
        open(os.path.join(d, "REPORT.md"), "w", encoding="utf-8").write(report)
    return d


def run(d):
    env = dict(os.environ)
    env["CF5_ROWS"] = os.path.join(d, "rows.json")
    env["CF5_CORR"] = os.path.join(d, "corrections.json")
    env["CF5_REPORT"] = os.path.join(d, "REPORT.md")
    r = subprocess.run([PY, os.path.join(HERE, "check_fab.py")],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def main():
    rows0 = json.load(open(os.path.join(HERE, "rows.json"), encoding="utf-8"))
    corr0 = json.load(open(os.path.join(HERE, "corrections.json"), encoding="utf-8"))
    rep0 = open(os.path.join(HERE, "REPORT.md"), encoding="utf-8").read()

    cases = []

    # 1. a row contradicts its own file: DA non-through 36 -> 15 (the old artefact)
    r = copy.deepcopy(rows0)
    r["boards"]["drone-arm main rev_b"]["cells"]["nonthrough"]["value"] = \
        r["boards"]["drone-arm main rev_b"]["cells"]["nonthrough"]["value"].replace("36 non-through", "15 non-through")
    cases.append(("1 row value 36->15", write("c1", r, corr0, rep0), "6 drone-arm identities"))

    # 2. a summary flag contradicts the row: ESC orderable NO -> YES with 8 FAILs
    r = copy.deepcopy(rows0)
    r["boards"]["ESC rev_b"]["orderable"] = "YES"
    cases.append(("2 orderable NO->YES", write("c2", r, corr0, rep0), "2 orderable"))

    # 3. an OLD figure reintroduced as a live claim
    r = copy.deepcopy(rows0)
    r["boards"]["Code-SDR V2"]["cells"]["min_ring"]["value"] += " ; the fiducial clears by 1.22 mm"
    cases.append(("3 old figure reintroduced", write("c3", r, corr0, rep0), "11a no OLD value"))

    # 4. a REPORT cell hand-edited away from the generated block
    rep = rep0.replace("| **1,536-1,542 unconnected** |", "| **499 unconnected** |", 1)
    if rep == rep0:
        raise SystemExit("mutation 4 did not apply")
    cases.append(("4 report cell edited", write("c4", rows0, corr0, rep), "4 REPORT"))

    # 5. the blocking number invented rather than quoted from a FAIL cell
    r = copy.deepcopy(rows0)
    r["boards"]["drone-arm main rev_b"]["blocking"] = "0 errors"
    cases.append(("5 blocking not in a FAIL cell", write("c5", r, corr0, rep0), "3 blocking"))

    # 6. a NEW figure that exists only inside the correction table
    rep = rep0.replace("**621 fab-real**", "**six hundred fab-real**", 1)
    rep = rep.replace("fab-real 621 = 523", "fab-real many = 523", 1)
    rep = rep.replace("621 fab-real", "many fab-real")
    cases.append(("6 NEW value only in section 2", write("c6", rows0, corr0, rep), "11b every NEW value"))

    print("negative test: the checker must exit 1 on every one of these")
    ok = True
    for name, d, expect in cases:
        rc, out = run(d)
        caught = rc != 0 and expect in out
        fail_lines = [l for l in out.splitlines() if l.startswith("FAIL ")]
        print("\n%-34s exit=%d  expected=%r  %s"
              % (name, rc, expect, "CAUGHT" if caught else "MISSED  <-- checker hole"))
        for l in fail_lines[:4]:
            print("    " + l[:150])
        ok = ok and caught
    print("\nnegative test: %d/%d caught, exit %d"
          % (sum(1 for n, d, e in cases if True), len(cases), 0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())