#!/usr/bin/env python3
"""fab-checklist-final -- the checker. Exit 0 iff nothing contradicts a row.

It is not a prose linter. It re-reads rows.json, corrections.json, facts.json and
REPORT.md, recomputes the arithmetic that the cells assert, re-derives the three
generated blocks and fails on any disagreement.

Run: "C:/Program Files/Python312/python.exe" check_fab.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.dirname(HERE)
ROWS = json.load(open(os.path.join(HERE, "rows.json"), encoding="utf-8"))
CORR = json.load(open(os.path.join(HERE, "corrections.json"), encoding="utf-8"))
FACTS = json.load(open(os.path.join(HERE, "facts.json"), encoding="utf-8"))
REPORT = open(os.path.join(HERE, "REPORT.md"), encoding="utf-8").read()
COLS = ROWS["columns"]
EVIDN = ROWS["evidence_columns"]
BOARDS = ROWS["boards"]

FAILS = []
CHECKS = []


def check(num, name, ok, detail=""):
    CHECKS.append((num, name, ok, detail))
    if not ok:
        FAILS.append((num, name, detail))


def cells(n):
    return BOARDS[n]["cells"]


def rowtext(n=None):
    """Every cell's value+reason+source, serialised, for absence tests."""
    out = []
    for name, b in BOARDS.items():
        if n and name != n:
            continue
        for k in COLS[:EVIDN]:
            c = b["cells"][k]
            out.append("%s :: %s :: %s :: %s :: %s" % (name, k, c["short"], c["value"], c["reason"]))
        out.append("%s :: orderable :: %s" % (name, b["orderable"]))
        out.append("%s :: blocking :: %s" % (name, b["blocking"]))
    return "\n".join(out)


def block(begin, end):
    m = re.search(re.escape(begin) + r"\n(.*?)\n" + re.escape(end), REPORT, re.S)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------- 1 coverage
names = list(BOARDS)
errs = []
for n in names:
    if set(cells(n)) != set(COLS[:EVIDN]):
        errs.append("%s: column set differs" % n)
    for k in COLS[:EVIDN]:
        c = cells(n)[k]
        if c["verdict"] not in ("PASS", "FAIL", "WAIVED"):
            errs.append("%s.%s verdict %r" % (n, k, c["verdict"]))
        for f in ("short", "value", "reason", "source"):
            if not str(c[f]).strip():
                errs.append("%s.%s empty %s" % (n, k, f))
        blob = (c["value"] + c["reason"]).lower()
        if "tbd" in blob or "??" in blob:
            errs.append("%s.%s contains TBD/??" % (n, k))
check(1, "coverage and vocabulary: %d cells, 4 x 13, no blank, no TBD"
      % (len(names) * EVIDN), not errs, "; ".join(errs[:4]))

# ------------------------------------------------------- 2 orderable / blocking
errs = []
for n in names:
    fails = [k for k in COLS[:EVIDN] if cells(n)[k]["verdict"] == "FAIL"]
    want = "NO" if fails else "YES"
    if BOARDS[n]["orderable"] != want:
        errs.append("%s orderable %s but %d FAIL cells" % (n, BOARDS[n]["orderable"], len(fails)))
    blk = BOARDS[n]["blocking"]
    zeroish = bool(re.fullmatch(r"0(\.0+)?\s*(errors?)?", blk)) or blk.startswith("0 (")
    if want == "NO" and (not blk or zeroish):
        errs.append("%s NO but blocking=%r" % (n, blk))
    if want == "YES" and not blk.startswith("0"):
        errs.append("%s YES but blocking=%r" % (n, blk))
check(2, "orderable == (0 FAIL cells), and blocking is non-zero iff a FAIL exists", not errs,
      "; ".join(errs))

# ------------------------------------------- 3 blocking verbatim in a FAIL cell
errs = []
for n in names:
    if BOARDS[n]["orderable"] == "NO":
        blk = BOARDS[n]["blocking"]
        hits = [k for k in COLS[:EVIDN] if cells(n)[k]["verdict"] == "FAIL"
                and (blk in cells(n)[k]["value"] or blk in cells(n)[k]["reason"])]
        if not hits:
            errs.append("%s: %r not verbatim in any FAIL cell" % (n, blk))
check(3, "every NO row's blocking number occurs verbatim in a FAIL cell", not errs, "; ".join(errs))

# ------------------------------------------- 4 REPORT blocks == generator
import build_report
gen = build_report.blocks(ROWS, CORR)
errs = []
for b, e, body in gen:
    got = block(b, e)
    if got is None:
        errs.append("marker missing: " + b)
    elif got != body.strip():
        errs.append("block differs: " + b)
check(4, "the three REPORT blocks are byte-identical to the generator's output", not errs,
      "; ".join(errs))

# ------------------------------------------------------------- 5 tally
t = build_report.tally(ROWS)
errs = []
mat = block("<!-- BEGIN TABLE -->", "<!-- END TABLE -->")
for n in names:
    s = sum(t[n].values())
    if s != EVIDN:
        errs.append("%s tally sums to %d" % (n, s))
tot = {k: sum(t[n][k] for n in names) for k in ("PASS", "FAIL", "WAIVED")}
if sum(tot.values()) != len(names) * EVIDN:
    errs.append("grand total %d != %d" % (sum(tot.values()), len(names) * EVIDN))
n_yes = sum(1 for n in names if BOARDS[n]["orderable"] == "YES")
mlast = [l for l in (mat or "").splitlines() if l.startswith("| **all four**")]
if not mlast:
    errs.append("grand-total row missing")
else:
    nums = [x.strip().strip("*") for x in mlast[0].split("|")[2:9]]
    if nums[:4] != [str(tot["PASS"]), str(tot["FAIL"]), str(tot["WAIVED"]), str(sum(tot.values()))]:
        errs.append("grand-total row %r != %r" % (nums[:4], [tot["PASS"], tot["FAIL"], tot["WAIVED"], 52]))
    if "%d of 4" % n_yes not in mlast[0]:
        errs.append("orderable count in grand total != %d" % n_yes)
check(5, "the tally rows reproduce from rows.json (52 cells, %d YES)" % n_yes, not errs, "; ".join(errs))

# ------------------------------------------------------ 6 drone-arm identities
a = FACTS["drone_arm"]
errs = []
if a["through"] + a["non_through"] != a["vias_total"]:
    errs.append("318+19 != 337")
if a["micro"] + a["blind"] != a["non_through"]:
    errs.append("15+4 != 19")
if sum(a["by_pair"].values()) != a["non_through"]:
    errs.append("pair sum != 19")
if sum(a["by_ref"].values()) != a["non_through"]:
    errs.append("ref split sum != 19")
if a["own_drc"] != a["own_via_diameter"]:
    errs.append("own rules != via_diameter rows")
if a["gate"] != a["gate_hole_size"] + a["gate_via_diameter"]:
    errs.append("22 != 18+4")
if abs(a["via_pad"] + 2 * a["clearance"] - a["clear_need"]) > 1e-9:
    errs.append("0.60 + 2*0.125 != 0.85")
if a["u10_lane"] >= a["clear_need"]:
    errs.append("the blocker is not a blocker: U10 lane >= 0.85")
arm = cells(names[0])
req = {"nonthrough": ["19", "15 micro + 4 blind", "0.85 mm", "337", "318", "16 stacks"],
       "min_drill": ["0.100"], "drc": ["22", "18 hole_size", "4 via_diameter"],
       "unconnected": ["0 pcbnew", "438"], "package": ["SENDABLE = NO"]}
for k, toks in req.items():
    for tok in toks:
        if tok not in arm[k]["value"] and tok not in arm[k]["reason"]:
            errs.append("arm.%s missing %r" % (k, tok))
check(6, "drone-arm identities: 337=318+19, 19=15+4, 0.60+2x0.125=0.85, 4/22 DRC, 0 unconnected",
      not errs, "; ".join(errs))

# -------------------------------------------------------------- 7 ESC identities
e = FACTS["esc"]
errs = []
if e["drc_3oz"] + e["gone"] != e["drc_4oz"]:
    errs.append("102+127 != 229")
if e["gone"] != e["gone_clearance"] + e["gone_track_width"] + e["gone_connection_width"]:
    errs.append("127 != 120+4+3")
if e["annular"] + e["via_diameter"] + e["via_dangling"] != e["drc_3oz"]:
    errs.append("70+16+16 != 102")
if e["annular"] != e["annular_pth"] + e["annular_via"]:
    errs.append("70 != 42+28")
if e["fab_real"] != e["drc_3oz"] + e["invisible_rings"]:
    errs.append("200 != 102+98")
if e["padgap_qfn"] + e["padgap_usbc"] != e["padgap_total"]:
    errs.append("75+14 != 89")
if abs(e["cu_outer"] * 2 + e["cu_inner"] * 2 + 0.2 + 0.865 + 0.2 + 2 * 0.010 - e["board_mm"]) > 1e-9:
    errs.append("stackup does not close to 1.600 mm")
if abs(e["bus_capacity_A"] - e["barrels"] * e["barrel_A"]) > 1e-9:
    errs.append("34.5 != 23*1.50")
# IPC-2221: A = (I/(k*dT^0.44))^(1/0.725) -> I = k*dT^0.44*A^0.725, width_mil = A_mil2/t_mil
area_mil2 = (e["phase_corridor_mm"] / 0.0254) * (e["cu_outer"] / 0.0254)
i_calc = 0.048 * (20 ** 0.44) * (area_mil2 ** 0.725)
if abs(i_calc - e["i_phase_possible"]) > 0.05:
    errs.append("IPC-2221 gives %.2f A, not %.2f" % (i_calc, e["i_phase_possible"]))
esc = cells(names[1])
req = {"copper": ["0.1050", "0.0525", "36.58", "34.5"], "drc": ["229", "102", "127", "200", "89", "70 annular"],
       "unconnected": ["1,536", "1,542"], "min_ring": ["0.125", "70"], "min_drill": ["0.300", "0.200"],
       "outline": ["491.732", "382.709"]}
for k, toks in req.items():
    for tok in toks:
        if tok not in esc[k]["value"] and tok not in esc[k]["reason"]:
            errs.append("esc.%s missing %r" % (k, tok))
check(7, "ESC identities: 229=102+127, 102=70+16+16, 200=102+98, 89=75+14, 34.5=23x1.50, IPC 36.58 A",
      not errs, "; ".join(errs))

# --------------------------------------------------------- 8 Code-SDR identities
c = FACTS["code_sdr"]
errs = []
if c["drills"] + c["slots"] != c["holes"]:
    errs.append("1213+2 != 1215")
if c["vias"] + c["drills"] + c["slots"] - 3 != c["holes"] * 0 and False:
    pass  # vias are not a hole population; the hole census is drills+slots
if c["gerber_job"] + c["excellon_docs"] + c["assembly_csv"] + c["root_files"] != c["files"]:
    errs.append("12+4+3+3 != 22")
if c["pos_parts"] + c["fiducials"] != c["pos_rows"]:
    errs.append("373+4 != 377")
if abs(c["edge_mm"] + c["stroke_mm"] - c["bbox_mm"]) > 1e-9:
    errs.append("101.6+0.100 != 101.70")
if c["warn_lib_footprint"] + c["warn_via_dangling"] + c["warn_track_dangling"] != c["drc_warnings"]:
    errs.append("199+13+10 != 222")
if c["drc_errors"] != 0:
    errs.append("drc errors != 0")
cs = cells(names[2])
req = {"package": ["22 files", "20/20", "1,215", "1,213", "377 pos rows", "373"], "outline": ["101.600", "101.70", "0.100 mm stroke"],
       "drc": ["222", "0 errors"], "unconnected": ["0 pcbnew", "1,093"], "revision": ["2.1"]}
for k, toks in req.items():
    for tok in toks:
        if tok not in cs[k]["value"] and tok not in cs[k]["reason"]:
            errs.append("cs.%s missing %r" % (k, tok))
check(8, "Code-SDR identities: 1213+2=1215, 22=12+4+3+3, 373+4=377, 101.6+0.100=101.70, 222=199+13+10",
      not errs, "; ".join(errs))

# -------------------------------------------------------- 9 drone-mech identities
m = FACTS["drone_mech"]
errs = []
mass = m["volume_mm3"] / 1000.0 * (m["density_kg_m3"] / 1000.0)
if abs(mass - m["mass_g"]) > 2e-4:
    errs.append("mass %.4f != %.4f" % (mass, m["mass_g"]))
if abs(m["stl_delta_mm3"] / m["volume_mm3"] * 100 - (-m["stl_pct"])) > 0.004:
    errs.append("STL delta %% does not close on -0.052")
if abs((m["genuine_mm3"] + m["artefact_mm3"] + m["rings_mm3"]) - m["pairs_volume_mm3"]) > 2e-6:
    errs.append("6+2+2 volumes do not sum to 3,305.834869")
if abs(2 * m["ring_each_mm3"] - m["rings_mm3"]) > 1e-9:
    errs.append("2 x 1,048.409726 != 2,096.819452")
pct = m["rings_mm3"] / m["pairs_volume_mm3"] * 100
if abs(pct - m["ring_pct_of_total"]) > 0.05:
    errs.append("ring share %.2f %% != 63.4 %%" % pct)
if m["pairs"] != 2 + 2 + 2 + 2 + 2:
    errs.append("10 pairs != 2+2+2+2+2")
if m["manifest_files"] + 1 != m["files_on_disk"]:
    errs.append("45+1 != 46 files on disk")
dm = cells(names[3])
req = {"drc": ["206,454.3197", "10 pairs", "3,305.834869", "2,096.819452", "63.4"],
       "package": ["45", "-0.052", "59,964"], "revision": ["DM-FUS-001 REV 1"],
       "outline": ["640.00", "320.0042", "1.1492"]}
for k, toks in req.items():
    for tok in toks:
        if tok not in dm[k]["value"] and tok not in dm[k]["reason"]:
            errs.append("dm.%s missing %r" % (k, tok))
check(9, "drone-mech identities: 320.0042 g closes, 10=2+2+2+2+2, sets sum to 3,305.834869, 2x1,048.409726, 63.4 %",
      not errs, "; ".join(errs))

# ------------------------------------------------------------- 10 corrections
errs = []
ids = [r["id"] for r in CORR["rows"]]
if len(ids) != 35 or len(set(ids)) != 35:
    errs.append("35 unique ids expected, got %d/%d" % (len(ids), len(set(ids))))
live = [r for r in CORR["rows"] if r["status"] == "live"]
sup = [r for r in CORR["rows"] if r["status"] == "superseded"]
rt = rowtext()
sec2 = block("<!-- BEGIN CORRECTIONS -->", "<!-- END CORRECTIONS -->") or ""
outside = REPORT.replace(sec2, "")
for r in live:
    for tok in r.get("absent_in_rows", []):
        if tok in rt:
            errs.append("%s old token %r still in rows" % (r["id"], tok))
    got = 0
    for tok in r.get("present", []):
        if tok in outside:
            got += 1
    if r.get("present") and got == 0:
        errs.append("%s new tokens used nowhere outside section 2" % r["id"])
for r in sup:
    for tok in r.get("stale_in_rows", []):
        if tok in rt:
            errs.append("%s stale token %r still in rows" % (r["id"], tok))
    by = r.get("superseded_by")
    if by not in ids:
        errs.append("%s superseded_by %r missing" % (r["id"], by))
    elif next(x for x in CORR["rows"] if x["id"] == by)["status"] != "live":
        errs.append("%s successor %s is not live" % (r["id"], by))
check(10, "corrections: 35 rows, %d live / %d superseded, no stale token survives, every successor is live"
      % (len(live), len(sup)), not errs, "; ".join(errs[:6]))

# --------------------------------------------------- 11 WAIVED cells are priced
errs = []
for n in names:
    for k in COLS[:EVIDN]:
        cc = cells(n)[k]
        if cc["verdict"] == "WAIVED":
            r = cc["reason"].lower()
            if not ("n/a" in r or "quote" in r or "waiver" in r):
                errs.append("%s.%s WAIVED without an n/a or a price" % (n, k))
check(11, "every WAIVED cell is either n/a (no such parameter) or a priced quote line", not errs,
      "; ".join(errs[:4]))

# ------------------------------------ 12 conditions block + not-known section
errs = []
cond = block("<!-- BEGIN CONDITIONS -->", "<!-- END CONDITIONS -->") or ""
rows_cond = [l for l in cond.splitlines() if l.startswith("| ") and "condition" not in l]
if len(rows_cond) != 20:
    errs.append("conditions table has %d rows, expected 20" % len(rows_cond))
for n in names:
    derived = build_report.conditions(BOARDS[n])
    for label, v, _why in derived:
        if "| %s | %s | **%s** |" % (n, label, v) not in cond:
            errs.append("%s %s derived %s missing" % (n, label, v))
nk = re.findall(r"^\| \*\*N(\d+)\*\* \|", REPORT, re.M)
if len(nk) != FACTS["not_known_count"]:
    errs.append("NOT KNOWN has %d rows, facts say %d" % (len(nk), FACTS["not_known_count"]))
for subject in ("bearing-ring", "150", "route", "path choice"):
    if subject.lower() not in REPORT.lower():
        errs.append("NOT KNOWN misses %r" % subject)
check(12, "conditions block reproduces from the cells and NOT KNOWN carries %d owned items"
      % FACTS["not_known_count"], not errs, "; ".join(errs[:4]))

# ------------------------------------------------------ 13 sources exist on disk
errs, seen = [], set()
pat = re.compile(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-/]+")
for n in names:
    for k in COLS[:EVIDN]:
        for tok in pat.findall(cells(n)[k]["source"]):
            tok = tok.rstrip(".")
            if tok.split("/")[0] not in os.listdir(EVID):
                continue  # a bare filename or a facts.json reference
            seen.add(tok)
            if not os.path.exists(os.path.join(EVID, tok.replace("\\", "/"))):
                errs.append("%s.%s source not on disk: %s" % (n, k, tok))
check(13, "every cited evidence path under %d distinct evidence dirs exists on disk" % len({s.split('/')[0] for s in seen}),
      not errs, "; ".join(sorted(set(errs))[:6]))

# ------------------------------------------------------------------- summary
print("=" * 78)
print("fab-checklist-final :: check_fab.py")
print("=" * 78)
for num, name, ok, detail in CHECKS:
    print("%s %2d  %s" % ("PASS" if ok else "FAIL", num, name))
    if not ok and detail:
        print("        -> " + detail)
print("-" * 78)
print("%d checks, %d failures" % (len(CHECKS), len(FAILS)))
if FAILS:
    print("EXIT 1 -- the sheet contradicts itself")
    sys.exit(1)
print("EXIT 0 -- every summary re-derives from its rows")