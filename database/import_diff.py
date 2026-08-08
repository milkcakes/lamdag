"""Differential MATATAG K-10 importer: refresh `matatag_cg.db` competencies from
`k10_parsed.json` without deleting rows.

Matching per subject, against existing DB competency descriptions:
  1. FORCE_UPDATE map (manually reviewed rewordings) -> UPDATE
  2. exact normalized equality                                -> UPDATE
  3. containment: one description is a prefix of the other
     (shared length >= 25, both >= 25)                       -> UPDATE
  4. difflib ratio >= 0.85                                    -> UPDATE
  5. otherwise                                               -> INSERT

Each DB row is updated at most once (strongest parsed match wins); the weaker
one falls through to INSERT.  Existing DB rows that no parsed record matches
are left untouched (reported as stale).

`TLE-G{}-<SLUG>` subject codes expand to `TLE-G9-...` and `TLE-G10-...`.
New subjects (TELECOMMUNICATIONS, VISUALARTS) are created first.

Usage:
    python import_diff.py [k10_parsed.json] [-d db] [--commit]
(without --commit it runs as a dry run and prints the full insert list)
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_DEF_DB = r"C:\Users\Administrator\Desktop\LAMDAG-Portable\database\matatag_cg.db"
_DEF_PARSED = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\deped\k10_parsed.json"

GRADE_ORDER = {f"Grade {g}": g for g in range(1, 13)}
GRADE_ORDER["Kindergarten"] = 0

# new 2026 sectors without a DB subject yet: slug -> (name, grouping)
NEW_SUBJECTS = {
    "TLE-G9-TELECOMMUNICATIONS": ("Telecommunications", "ICT", "Grade 9"),
    "TLE-G10-TELECOMMUNICATIONS": ("Telecommunications", "ICT", "Grade 10"),
    "TLE-G9-VISUALARTS": ("Visual Arts", "ICT", "Grade 9"),
    "TLE-G10-VISUALARTS": ("Visual Arts", "ICT", "Grade 10"),
}

# manually reviewed rewordings: (subject_code, parsed_prefix, db_desc_prefix)
FORCE_UPDATE = [
    ("AP-G4", "nailalarawan ang pagkakakilanlang heograpikal ng pilipinas",
              "nailalarawan ang pagkakakilanlang heograpikal ng pilipinas"),
    ("AP-G4", "nasusuri ang papel ng pamahalaan at mga programang pangkalusugan",
              "nasusuri ang papel ng pamahalaan at mga programang"),
    ("MA-G4", "compare the musical, theatrical, dance, and visual arts representations",
              "compare the musical, theatrical, dance, and visual arts representations"),
    ("MA-G4", "produce creative artworks based on the celebrations",
              "produce creative works based on the celebrations"),
    ("GMRC-G6", "naisasabuhay ang pagiging magalang sa pamamagitan ng pagkilala sa mga kapangyarihan",
                "naisasabuhay ang pagiging magalang sa pamamagitan ng pagkilala sa mga kapangyarihan"),
    ("GMRC-G5", "naisasabuhay ang pagiging magalang sa pamamagitan ng wastong pakikitungo sa mga nakatatanda",
                "naisasabuhay ang pagiging magalang sa pamamagitan ng wastong pakikitungo sa mga nakatatanda"),
    ("VE-G10", "nakapagsasanay sa pagiging maunawain sa pamamagitan ng walang paghuhusgang pagtanggap",
               "nakapagsasanay sa pagiging maunawain sa pamamagitan ng walang paghuhusgang pagtanggap"),
    ("VE-G7", "nakapagsasanay sa pagiging mapanagutan sa pamamagitan ng pagtitiyak sa kabutihan",
              "nakapagsasanay sa pagiging mapanagutan sa pamamagitan ng pagtitiyak sa kabutihan"),
    ("MA-G6", "discuss how relevant events and principles/ beliefs/ ideas in the commonwealth period",
              "discuss how relevant events and principles/ beliefs/ ideas in the commonwealth period"),
    ("MA-G7", "produce creative works about contemporary and emerging popular performing",
              "produce creative works about contemporary and emerging popular performing"),
    ("MA-G8", "integrate relevant concepts, techniques, processes, and/or practices of emerging and contemporary",
              "integrate relevant concepts, techniques, processes, and/or practices of emerging and contemporary"),
    ("MA-G8", "evaluate their own or others",
              "evaluate representative creative works of selected asian communities"),
    ("MA-G8", "produce an integrated creative work inspired by asian folk",
              "produce creative works inspired by selected asian court music"),
    ("MA-G8", "apply selected conventional and emerging concepts, techniques, and processes from asian folk",
              "apply the salient features of relevant conventional and emerging concepts"),
    ("MA-G10", "explain how technical and artistic elements",
               "examine the aesthetic principles and technical elements"),
    ("MA-G10", "analyze the challenges and issues encountered by artists",
               "examine the challenges and issues faced by select local filipino artists"),
    ("MA-G10", "evaluate technology-based creative works based on the effective use",
               "evaluate their technology-based creative work in terms of its technical and aesthetic"),
    ("MA-G10", "critique proposed strategies or solutions that address identified challenges",
               "critique a relevant case study or available and credible resources"),
    ("MATH-G2", "illustrate and apply the following properties of addition",
                "illustrate and apply the following properties of addition"),
    ("MATH-G9", "transform the quadratic functions",
                "transform the quadratic functions"),
    ("MATH-G10", "solve problems involving: a. central angles b. inscribed angles c. angles formed by two intersecting chords d. angles formed by two secants intersecting",
                 "solve problems involving: a. central angles b. inscribed angles c. angles formed by two intersecting chords d. angles formed by two secants intersecting"),
    ("SCI-G5", "plan simple scientific investigations in answering questions",
               "plan simple scientific investigations in answering questions"),
    ("PEH-G4", "perform physical activities using target and or invasion game concepts",
               "perform physical activities using target game concepts"),
    ("PEH-G5", "perform physical activities using striking/fielding and or net/wall",
               "perform physical activities using net/wall game concepts"),
    ("EPP-G5-ANIMALPRODUCTION", "naipaliliwanag ang mga piling batas, local na ordinansa",
                                 "naipaliliwanag ang mga piling batas, lokal na ordinansa"),
    ("EPP-G6-FISHERYARTS", "identify the government agencies and non-government organizations",
                           "explain the legal basis and agencies in fish raising"),
]


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ratio(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def expand(rec):
    code = rec["db_code"]
    if not code:
        return
    if "{}" in code:
        for g in (9, 10):
            yield code.replace("{}", str(g)), rec
    else:
        yield code, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parsed", nargs="?", default=_DEF_PARSED)
    ap.add_argument("-d", "--db", default=_DEF_DB)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    with open(args.parsed, encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    subs = {r[0]: {"id": r[1], "name": r[2], "grade": r[3], "sort": r[4], "group": r[5]}
            for r in cur.execute("SELECT code,id,name,grade_level,sort_order,grouping FROM subjects")}
    comps_by_subj = {}
    for sid, cid, term, week, code, desc, cs, ps in cur.execute(
            "SELECT subject_id,id,term,week,code,description,content_standard,performance_standard "
            "FROM competencies ORDER BY id"):
        comps_by_subj.setdefault(sid, []).append(
            {"id": cid, "term": term, "week": week, "code": code or "",
             "desc": desc or "", "cs": cs or "", "ps": ps or ""})

    by_code = {}
    for r in data:
        for code, rc in expand(r):
            by_code.setdefault(code, []).append(rc)

    print(f"k10_parsed.json: {len(data)} records -> {len(by_code)} concrete subject codes\n")

    # ---- new subjects first (so inserts can FK) ----
    to_create = [c for c in by_code if c not in subs and c in NEW_SUBJECTS]
    for code in sorted(to_create):
        name, group, grade = NEW_SUBJECTS[code]
        cur.execute(
            "INSERT INTO subjects (code,name,grade_level,sort_order,grouping) VALUES (?,?,?,?,?)",
            (code, name, grade, GRADE_ORDER.get(grade, 99), group))
        subs[code] = {"id": cur.lastrowid, "name": name, "grade": grade,
                      "sort": GRADE_ORDER.get(grade, 99), "group": group}
        print(f"NEW SUBJECT: {code} ({name})")
    if to_create:
        print()

    rows_by_code = {code: [] for code in by_code}
    for code, sid in [(c, subs[c]["id"]) for c in by_code if c in subs]:
        rows_by_code[code] = comps_by_subj.get(sid, [])

    plan = []          # (code, rec, action, db_row or None)
    for code in sorted(by_code):
        if code not in subs:
            continue
        rows = rows_by_code[code]
        used = set()
        for rec in by_code[code]:
            p = norm(rec["desc"])
            if not p:
                continue
            target = None
            kind = None
            # 1. FORCE_UPDATE
            for subj, pp, dp in FORCE_UPDATE:
                if subj == code and p.startswith(norm(pp)):
                    for row in rows:
                        if norm(row["desc"]).startswith(norm(dp)):
                            if id(row) not in used:
                                target, kind = row, "force"
                                used.add(id(row))
                            break
                    break
            # 2/3/4. auto
            if target is None:
                cands = [(row, norm(row["desc"])) for row in rows if id(row) not in used]
                exact = [r for r in cands if r[1] == p]
                if exact:
                    target, kind = exact[0][0], "exact"
                    used.add(id(target))
            if target is None:
                best = None
                for row, d in [(row, norm(row["desc"])) for row in rows if id(row) not in used]:
                    if len(p) >= 25 and len(d) >= 25:
                        if d.startswith(p) or p.startswith(d):
                            shared = min(len(p), len(d))
                            if best is None or shared > best[1]:
                                best = (row, shared)
                if best:
                    target, kind = best[0], "contain"
                    used.add(id(target))
            if target is None:
                best = None
                for row, d in [(row, norm(row["desc"])) for row in rows if id(row) not in used]:
                    sc = ratio(p, d)
                    if sc >= 0.85 and (best is None or sc > best[1]):
                        best = (row, sc)
                if best:
                    target, kind = best[0], "ratio"
                    used.add(id(target))
            if target is None:
                plan.append((code, rec, "insert", None))
            else:
                plan.append((code, rec, kind, target))

    # ---- generate insert codes (matches existing {SUBJ}-T{term}-{seq} convention) ----
    _code_re_cache = {}
    max_seq = {}
    for code in by_code:
        if code not in subs:
            continue
        rx = re.compile(re.escape(code) + r"-T\d+-(\d+)$")
        _code_re_cache[code] = rx
        mx = 0
        for row in rows_by_code[code]:
            m = rx.search(row["code"])
            if m:
                mx = max(mx, int(m.group(1)))
        max_seq[code] = mx

    plan_seq = {}
    for i, (code, rec, kind, _) in enumerate(plan):
        if kind == "insert":
            term = rec["term"] if rec["term"] is not None else 1
            max_seq[code] += 1
            plan_seq[i] = f"{code}-T{term}-{max_seq[code]:02d}"

    # ---- report ----
    from collections import Counter, defaultdict
    upd = Counter(); ins = Counter()
    stale = defaultdict(int)
    for code in sorted(by_code):
        if code not in subs:
            continue
        matched = sum(1 for c, _, k, _ in plan if c == code and k != "insert")
        rows = rows_by_code[code]
        stale[code] = len(rows) - matched
        upd[code] = matched
        ins[code] = sum(1 for c, _, k, _ in plan if c == code and k == "insert")

    print("==== plan summary (dry run) ====")
    total_u = total_i = 0
    for code in sorted(by_code):
        if code not in subs:
            print(f"{code:45s} subject NOT in DB - skipped")
            continue
        u, i, s = upd[code], ins[code], stale[code]
        total_u += u; total_i += i
        if u or i or s:
            print(f"{code:45s} update={u:3d} insert={i:3d} stale={s:3d}")
    print(f"\nTOTALS: update={total_u}  insert={total_i}")

    print("\n==== INSERT list (review) ====")
    for i, (code, rec, kind, _) in enumerate(plan):
        if kind == "insert":
            c = plan_seq.get(i, "")
            print(f"[{code}] T{rec['term']} w{rec['week']} {c} | {rec['desc'][:100]}")

    if not args.commit:
        print("\n(dry run - pass --commit to write to DB)")
        conn.close()
        return

    # ---- apply ----
    bak = args.db + ".bak"
    shutil.copy2(args.db, bak)
    print(f"\nbackup -> {bak}")

    n_upd = n_ins = 0
    for i, (code, rec, kind, row) in enumerate(plan):
        if kind == "insert":
            term = rec["term"] if rec["term"] is not None else 1
            week = rec["week"]
            cur.execute(
                "INSERT INTO competencies (subject_id,term,week,code,description,"
                "content_standard,performance_standard) VALUES (?,?,?,?,?,?,?)",
                (subs[code]["id"], term, week, plan_seq.get(i, ""),
                 (rec["desc"] or "").strip(),
                 rec.get("content_standard") or "",
                 rec.get("performance_standard") or ""))
            n_ins += 1
            continue
        if row is None:
            continue
        new_desc = rec["desc"].strip()
        if kind == "contain":
            db_d = row["desc"]
            if len(norm(db_d)) > len(norm(new_desc)):
                new_desc = db_d
        term = rec["term"] if rec["term"] is not None else row["term"]
        week = rec["week"] if rec["week"] is not None else row["week"]
        cs = rec.get("content_standard") or row["cs"]
        ps = rec.get("performance_standard") or row["ps"]
        cur.execute(
            "UPDATE competencies SET description=?, term=?, week=?, "
            "content_standard=?, performance_standard=? WHERE id=?",
            (new_desc, term, week, cs, ps, row["id"]))
        if cur.rowcount == 1:
            n_upd += 1
        else:
            print(f"  ! update affected {cur.rowcount} rows for {code} id={row['id']}")
    conn.commit()

    print(f"applied: {n_upd} updates, {n_ins} inserts")
    print("subjects:", cur.execute("SELECT COUNT(*) FROM subjects").fetchone()[0])
    print("competencies:", cur.execute("SELECT COUNT(*) FROM competencies").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
