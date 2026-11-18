#!/usr/bin/env python3
"""fab-checklist-final -- nine one-variable mutations, each must make check_fab.py exit non-zero.

Each mutation is applied to a private copy of the pack (out/neg/cN/), then check_fab.py runs
there as a subprocess. A mutation that still exits 0 is a hole in the checker and the test fails.

Run: "C:/Program Files/Python312/python.exe" negative_test.py
"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEG = os.path.join(HERE, "out", "neg")
PY = sys.executable
FILES = ["rows.json", "corrections.json", "facts.json", "REPORT.md", "build_report.py", "check_fab.py"]


def load(p):
    return json.load(open(p, encoding="utf-8"))


def save(p, o):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, indent=1, ensure_ascii=False)


def baseline():
    r = subprocess.run([PY, "check_fab.py"], cwd=HERE, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def mutate(name, fn):
    d = os.path.join(NEG, name)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    for f in FILES:
        shutil.copy2(os.path.join(HERE, f), os.path.join(d, f))
    fn(d)
    r = subprocess.run([PY, "check_fab.py"], cwd=d, capture_output=True, text=True)
    out = r.stdout + r.stderr
    tail = [l for l in out.splitlines() if l.startswith("FAIL")][:2]
    return r.returncode, tail


def m_orderable(d):
    p = os.path.join(d, "rows.json")
    o = load(p)
    arm = list(o["boards"])[0]
    o["boards"][arm]["orderable"] = "YES"
    save(p, o)


def m_table_cell(d):
    p = os.path.join(d, "REPORT.md")
    t = open(p, encoding="utf-8").read()
    t = t.replace("140.000 x 100.000 mm = 140.00 cm2", "140.000 x 100.000 mm = 141.00 cm2", 1)
    open(p, "w", encoding="utf-8", newline="\n").write(t)


def m_tally(d):
    p = os.path.join(d, "REPORT.md")
    t = open(p, encoding="utf-8").read()
    t = t.replace("| **all four** | **31** | **10** | **11** | **52** |",
                  "| **all four** | **32** | **10** | **11** | **52** |", 1)
    open(p, "w", encoding="utf-8", newline="\n").write(t)


def m_arm_fact(d):
    p = os.path.join(d, "facts.json")
    o = load(p)
    o["drone_arm"]["non_through"] = 36
    save(p, o)


def m_esc_fabreal(d):
    p = os.path.join(d, "facts.json")
    o = load(p)
    o["esc"]["fab_real"] = 102
    save(p, o)


def m_dm_mass(d):
    p = os.path.join(d, "rows.json")
    o = load(p)
    dm = list(o["boards"])[-1]
    o["boards"][dm]["cells"]["outline"]["value"] = \
        o["boards"][dm]["cells"]["outline"]["value"].replace("320.0042", "320.0050")
    save(p, o)


def m_successor(d):
    p = os.path.join(d, "corrections.json")
    o = load(p)
    for r in o["rows"]:
        if r["id"] == "BC33":
            r["status"] = "superseded"
            r["superseded_by"] = "BC99"
    save(p, o)


def m_waiver(d):
    p = os.path.join(d, "rows.json")
    o = load(p)
    arm = list(o["boards"])[0]
    o["boards"][arm]["cells"]["min_ring"]["reason"] = "it is fine"
    save(p, o)


def m_notknown(d):
    p = os.path.join(d, "facts.json")
    o = load(p)
    o["not_known_count"] = 26
    save(p, o)


MUTATIONS = [
    ("c1 orderable flipped to YES on a row with FAIL cells", m_orderable),
    ("c2 one cell of the generated matrix hand-edited", m_table_cell),
    ("c3 the grand-total row changed by one", m_tally),
    ("c4 non-through count changed to 36 against its own totals", m_arm_fact),
    ("c5 ESC fab-real set equal to the reported count", m_esc_fabreal),
    ("c6 drone-mech mass cell edited by 0.0008 g", m_dm_mass),
    ("c7 a superseded row points at a successor that does not exist", m_successor),
    ("c8 a WAIVED reason with no n/a and no price", m_waiver),
    ("c9 NOT KNOWN count off by one against the sheet", m_notknown),
]

base_code, base_out = baseline()
print("baseline check_fab.py exit = %d" % base_code)
print("-" * 78)
if base_code != 0:
    print(base_out)
    print("BASELINE IS NOT CLEAN -- fix the sheet before trusting the mutations")
    sys.exit(1)

bad = 0
for label, fn in MUTATIONS:
    code, tail = mutate(label.split()[0], fn)
    ok = code != 0
    print("%s  %-62s exit %d" % ("CAUGHT " if ok else "MISSED ", label, code))
    for l in tail:
        print("        " + l)
    if not ok:
        bad += 1
print("-" * 78)
print("%d of %d mutations caught" % (len(MUTATIONS) - bad, len(MUTATIONS)))
if bad:
    print("EXIT 1 -- the checker has a hole")
    sys.exit(1)
print("EXIT 0 -- every mutation forced a non-zero exit")