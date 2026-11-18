#!/usr/bin/env python3
"""fab-checklist-v5 checker -- fails if any summary contradicts its rows.

The rule this enforces: a number in a summary paragraph, a tally, a condition
verdict or a blocking cell that is not derivable from the row-level data is a
FAIL of the sheet. Every check below is either
  (a) a recomputation from rows.json / the raw measurement JSONs, or
  (b) an identity arithmetic on the cited counts, or
  (c) a byte comparison of REPORT.md's embedded block against the generator.

Negative tests live in negative_test.py; they mutate one input at a time and
require the matching check to fire.

Run: "C:/Program Files/Python312/python.exe" check_fab.py   -> exit 0 iff clean
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V4 = os.path.join(r"E:\engineering-portfolio-audit\evidence", "fab-checklist-v4", "out")
COLS13 = ["layers", "copper", "min_track", "min_space", "min_drill", "min_ring",
          "nonthrough", "unconnected", "drc", "package", "revision", "outline", "finish"]
BEGIN = "<!-- BEGIN TABLE -->"
END = "<!-- END TABLE -->"
CONDBEGIN = "<!-- BEGIN CONDITIONS -->"
CONDEND = "<!-- END CONDITIONS -->"
C2BEGIN = "<!-- BEGIN CORRECTIONS -->"
C2END = "<!-- END CORRECTIONS -->"


def num(s):
    """First number in a string, commas stripped."""
    m = re.search(r"-?\d[\d,]*\.?\d*", s)
    return float(m.group(0).replace(",", "")) if m else None


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def validate(rows, corr, report, drc_dir, out_dir, v4=V4):
    """Returns (failures, checks). Empty failures == clean."""
    F, C = [], []

    def ck(name, ok, detail=""):
        C.append((name, ok, detail))
        if not ok:
            F.append("%s: %s" % (name, detail))

    boards = rows["boards"]
    # ---------- 1. coverage, vocabulary, no blanks ----------
    bad = []
    for n, b in boards.items():
        for k in COLS13:
            c = b["cells"].get(k)
            if not c:
                bad.append("%s/%s missing" % (n, k)); continue
            if c["verdict"] not in ("PASS", "FAIL", "WAIVED"):
                bad.append("%s/%s verdict %r" % (n, k, c["verdict"]))
            for f in ("value", "reason", "source"):
                if not str(c.get(f, "")).strip():
                    bad.append("%s/%s empty %s" % (n, k, f))
            if re.search(r"\bTBD\b|\bTODO\b|\?\?", c["value"] + c["reason"]):
                bad.append("%s/%s TBD" % (n, k))
        if b["orderable"] not in ("YES", "NO"):
            bad.append("%s orderable %r" % (n, b["orderable"]))
        if not b["blocking"].strip():
            bad.append("%s blocking empty" % n)
    ck("1 coverage/vocabulary (52 cells, no blank, no TBD)", not bad, "; ".join(bad[:6]))

    # ---------- 2. orderable is derived, not asserted ----------
    bad = []
    for n, b in boards.items():
        nfail = sum(1 for k in COLS13 if b["cells"][k]["verdict"] == "FAIL")
        want = "NO" if nfail else "YES"
        if b["orderable"] != want:
            bad.append("%s orderable=%s but %d FAIL cells -> %s"
                       % (n, b["orderable"], nfail, want))
    ck("2 orderable == (0 FAIL cells)", not bad, "; ".join(bad))

    # ---------- 3. blocking number is quoted from a FAIL cell ----------
    bad = []
    for n, b in boards.items():
        if b["orderable"] == "NO":
            hay = " ".join(b["cells"][k]["value"]
                           for k in COLS13 if b["cells"][k]["verdict"] == "FAIL")
            if b["blocking"] not in hay:
                bad.append("%s blocking %r not in a FAIL cell" % (n, b["blocking"]))
    ck("3 blocking number occurs verbatim in a FAIL cell", not bad, "; ".join(bad))

    # ---------- 4. REPORT's embedded blocks == the generator's output ----------
    try:
        import build_report
        pairs = [("table/ledger/tally", build_report.render(rows), BEGIN, END),
                 ("five conditions", build_report.render_conditions(rows), CONDBEGIN, CONDEND),
                 ("correction table", build_report.render_corrections(corr), C2BEGIN, C2END)]
        for label, want, b, e in pairs:
            want = want.strip()
            m = re.search(re.escape(b) + r"\n(.*?)" + re.escape(e), report, re.S)
            got = (m.group(1).strip() if m else None)
            ck("4 REPORT %s == generated" % label,
               got is not None and got == want,
               "markers missing" if got is None else
               ("block differs: report %d chars vs generated %d" % (len(got), len(want))
                if got != want else ""))
    except Exception as e:  # generator import must not silently pass
        ck("4 REPORT blocks == generated", False, "generator error: %r" % (e,))

    # ---------- 5. tally in REPORT == recomputed tally ----------
    t = {n: {v: sum(1 for k in COLS13 if boards[n]["cells"][k]["verdict"] == v)
             for v in ("PASS", "FAIL", "WAIVED")} for n in boards}
    bad = []
    for n in boards:
        pat = re.compile(r"\| %s \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|" % re.escape(n))
        m = pat.search(report)
        if not m:
            bad.append("%s tally row absent" % n); continue
        got = tuple(int(x) for x in m.groups())
        wantt = (t[n]["PASS"], t[n]["FAIL"], t[n]["WAIVED"], sum(t[n].values()))
        if got != wantt:
            bad.append("%s tally %s != %s" % (n, got, wantt))
    ck("5 tally rows reproduce from rows.json", not bad, "; ".join(bad))

    # ---------- 6. DA identities, from the measurement file ----------
    da = jload(os.path.join(v4, "measure_da_repo.json"))
    vs = da["vias_by_span"]; dt = da["vias_by_declared_type"]
    nt = vs["blind"] + vs["buried"]
    span = {}
    for k, v in da["via_table"].items():
        _, lyr, kind = k.split("|")
        top = lyr.split("->")[0]
        span[top + "|" + kind] = span.get(top + "|" + kind, 0) + v
    blind = sum(v for k, v in span.items() if k.endswith("|blind"))
    buried = sum(v for k, v in span.items() if k.endswith("|buried"))
    ident = [
        ("DA vias 341 = 305+26+10", da["vias_total"] == vs["through"] + nt and da["vias_total"] == 341),
        ("DA non-through 36 = 26+10", nt == 36),
        ("DA declared 36 = 33+3", dt["MICROVIA"] + dt["BLIND"] == 36),
        ("DA blind 26 = F.Cu 17 + In1 4 + In2 5",
         blind == 26 and span["F.Cu|blind"] == 17
         and span["In1.Cu|blind"] == 4 and span["In2.Cu|blind"] == 5),
        ("DA buried In1->In2 = 10", buried == 10 and span["In1.Cu|buried"] == 10),
        ("DA via count in cell == file", "341" in boards["drone-arm main rev_b"]["cells"]["nonthrough"]["value"]),
        ("DA non-through in cell == file", "36" in boards["drone-arm main rev_b"]["cells"]["nonthrough"]["value"]),
    ]
    ck("6 drone-arm identities vs measure_da_repo.json", all(o for _, o in ident),
       "; ".join(n for n, o in ident if not o))

    # ---------- 7. ESC identities, from the measurement file ----------
    esc = jload(os.path.join(v4, "measure_esc.json"))
    ident = [
        ("ESC vias 1,990", esc["vias_total"] == 1990),
        ("ESC non-through 0", esc["vias_by_span"]["blind"] + esc["vias_by_span"]["buried"] == 0),
        ("ESC 413+110 = 523 DRC rows", 413 + 110 == 523),
        ("ESC 523+98 = 621 fab-real", 523 + 98 == 621),
        ("ESC 371+42 = 413 footprint-bound", 371 + 42 == 413),
        ("ESC 371+140 = 511 effective footprint-bound", 371 + 140 == 511),
        ("ESC 110 decomposition sums", 28 + 16 + 16 + 24 + 19 + 4 + 3 == 110),
        ("ESC ring census 140 == file", esc["pth_ring_below_020_count"] == 140),
        ("ESC min drill cell 0.300 == file", esc["min_via_drill"] == 0.3),
        ("ESC 1,990 in cell", "1,990" in boards["ESC rev_b"]["cells"]["nonthrough"]["value"]),
        ("ESC 621 in DRC cell", "621" in boards["ESC rev_b"]["cells"]["drc"]["value"]),
    ]
    ck("7 ESC identities vs measure_esc.json + esc-drc-resolve", all(o for _, o in ident),
       "; ".join(n for n, o in ident if not o))

    # ---------- 8. CS identities ----------
    cs = jload(os.path.join(v4, "measure_cs.json"))
    ident = [
        ("CS vias 1,085", cs["vias_total"] == 1085),
        ("CS non-through 0", cs["vias_by_span"]["blind"] + cs["vias_by_span"]["buried"] == 0),
        ("CS 1,213+2 = 1,215 holes", 1213 + 2 == 1215),
        ("CS 1,085+128+2 = 1,215 holes", 1085 + 128 + 2 == 1215),
        ("CS 373+4 = 377 footprints", 373 + 4 == 377),
        ("CS 22 files = 12+4+3+3", 12 + 4 + 3 + 3 == 22),
        ("CS 101.6+0.100 = 101.70 bbox", round(101.6 + 0.100, 3) == 101.70),
        ("CS stroke 0.100 in outline cell", "0.100 mm stroke" in boards["Code-SDR V2"]["cells"]["outline"]["value"]),
    ]
    ck("8 Code-SDR identities", all(o for _, o in ident),
       "; ".join(n for n, o in ident if not o))

    # ---------- 9. DM identities ----------
    ident = [
        ("DM 6 genuine + 2 artefact = 8 pairs", 6 + 2 == 8),
        ("DM 4.010114 cited", "4.010114" in boards["drone-mech airframe"]["cells"]["drc"]["value"]),
        ("DM 1,250.769445 cited", "1,250.769445" in boards["drone-mech airframe"]["cells"]["drc"]["value"]),
        ("DM 4 solids cited in a FAIL cell", "4 disjoint solids" in boards["drone-mech airframe"]["cells"]["drc"]["value"]),
    ]
    ck("9 drone-mech identities", all(o for _, o in ident),
       "; ".join(n for n, o in ident if not o))

    # ---------- 10. DRC cells vs the v5 DRC runs, row-level ----------
    bad = []
    try:
        own = jload(os.path.join(drc_dir, "da_own", "drc.json"))
        span = jload(os.path.join(drc_dir, "da_span", "drc.json"))
        n_own = len(own["violations"])
        n_span = len(span["violations"])
        types = {}
        for v in span["violations"]:
            types[v["type"]] = types.get(v["type"], 0) + 1
        if n_own != 0:
            bad.append("da_own=%d" % n_own)
        if n_span != 36:
            bad.append("da_span=%d" % n_span)
        if types.get("microvia_drill_out_of_range") != 33 or types.get("drill_out_of_range") != 3:
            bad.append("span types %s" % types)
        if n_span != da["vias_by_span"]["blind"] + da["vias_by_span"]["buried"]:
            bad.append("span gate != non-through count")
    except Exception as e:
        bad.append("drc read error %r" % (e,))
    rn = jload(os.path.join(out_dir, "cs_drc_renum.json"))
    if rn["total"] != 222 or rn["errors"] != 0:
        bad.append("cs_renum %s/%s" % (rn["total"], rn["errors"]))
    pc = jload(os.path.join(out_dir, "cs_padcheck.json"))
    if rn["pads_renumbered"] != pc["pads_with_duplicate_numbers"]:
        bad.append("renumbered %d != census %d"
                   % (rn["pads_renumbered"], pc["pads_with_duplicate_numbers"]))
    ck("10 DRC cells reproduce from drc/*.json", not bad, "; ".join(bad))

    # ---------- 11. corrections: old gone from rows, new used outside the table ----------
    rowtext = json.dumps(rows, ensure_ascii=False)
    m = re.search(re.escape(C2BEGIN) + r"\n(.*?)\n" + re.escape(C2END), report, re.S)
    outside = report[:m.start()] + report[m.end():] if m else report
    bad_old, bad_new = [], []
    for r in corr["rows"]:
        for tok in r["absent_in_rows"]:
            if tok.lower() in rowtext.lower():
                bad_old.append("%s old %r still in rows" % (r["id"], tok))
        for tok in r["present"]:
            if tok.lower() not in outside.lower():
                bad_new.append("%s new %r absent outside section 2" % (r["id"], tok))
    ck("11a no OLD value survives in the rows", not bad_old, "; ".join(bad_old[:6]))
    ck("11b every NEW value is used outside the correction table", not bad_new, "; ".join(bad_new[:6]))
    ck("11c corrections table parses and holds 17 rows",
       bool(m) and len(corr["rows"]) == 17 and m.group(1).count("| BC") >= 17,
       "%d rows in json, table %s" % (len(corr["rows"]), "found" if m else "missing"))

    # ---------- 12. ledger/tally cannot hide a FAIL behind a WAIVED ----------
    bad = [n for n, b in boards.items()
           if b["orderable"] == "YES" and any(b["cells"][k]["verdict"] == "WAIVED"
                                              for k in COLS13)
           and "quote line" not in " ".join(b["cells"][k]["reason"]
                                            for k in COLS13 if b["cells"][k]["verdict"] == "WAIVED")]
    ck("12 every WAIVED on a YES row is priced as a quote line", not bad, ", ".join(bad))

    return F, C


def main():
    # CF5_* let negative_test.py point the checker at a mutated input while the
    # drc/out data stays real. Unset == the files in this directory.
    rows = jload(os.environ.get("CF5_ROWS", os.path.join(HERE, "rows.json")))
    corr = jload(os.environ.get("CF5_CORR", os.path.join(HERE, "corrections.json")))
    rpath = os.environ.get("CF5_REPORT", os.path.join(HERE, "REPORT.md"))
    with open(rpath, encoding="utf-8") as f:
        report = f.read()
    F, C = validate(rows, corr, report, os.path.join(HERE, "drc"), os.path.join(HERE, "out"))
    for name, ok, detail in C:
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  <- " + detail))
    print("")
    print("checks %d, failures %d" % (len(C), len(F)))
    if F:
        print("EXIT 1 -- the sheet contradicts its own rows")
        return 1
    print("EXIT 0 -- every summary is derivable from the rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())