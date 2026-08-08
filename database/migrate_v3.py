"""One-time migration: LAMDAG curriculum data version 2 -> 3.

Changes:
1. Remove the 20 old-curriculum SHS subjects (non-SSHS, Grades 11-12).
2. Merge the two SSHS G11 core communication subjects into
   "Effective Communication (Filipino and English)".
3. Add a `grouping` column to subjects.
4. Tag every SSHS subject with a grouping (strand/sector from shs_parsed.json).
5. Split each EPP (G4-G6) and TLE (G7-G10) subject into specialization
   subjects, then delete the generic EPP/TLE subject.
6. Bump PRAGMA user_version to 3.

Run:  python database/migrate_v3.py [--commit]
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from import_shs import build_subjects, slugify, grade_num  # noqa: E402

DB = os.path.join(HERE, "matatag_cg.db")
PARSED = os.path.join(HERE, "shs_parsed.json")

MERGED_CORE_CODE = "SSHS-CORE-EFFECTIVECOMMUNICATIONFILIPINOANDENGLISH-G11"
MERGED_CORE_NAME = "Effective Communication (Filipino and English)"
MERGED_CORE_GROUPING = "Curriculum Guides (Core Subjects)"
CORE_MERGE_SOURCES = [
    "SSHS-CORE-EFFECTIVECOMMUNICATION-G11",
    "SSHS-CORE-MABISANGKOMUNIKASYONSAWIKANGFILIPINO-G11",
]

SECTION_NORM = {
    "Arts, Social Sciences, and Humanities Cluster": "Arts, Social Science, and Humanities Cluster",
    "Sports Health, and Wellness Cluster": "Sports, Health, and Wellness Cluster",
    "Issuances": "",
}

# grade code -> list of (slug, name, grouping, [(term, first_seq, last_seq), ...])
SPLITS = {
    "TLE-G9": [
        ("COMPUTERPROGRAMMING", "Computer Programming", "ICT", [(1, 1, 11), (2, 1, 8)]),
        ("CONTACTCENTERSERVICES", "Contact Center Services", "ICT", [(1, 12, 22), (2, 9, 13)]),
        ("COMPUTERSYSTEMSSERVICING", "Computer Systems Servicing", "ICT", [(1, 23, 29), (2, 14, 19)]),
        ("ILLUSTRATION", "Illustration", "ICT", [(1, 30, 33), (2, 20, 25)]),
        ("ANIMATION", "Animation", "ICT", [(1, 34, 36)]),
        ("POULTRYPRODUCTIONCHICKEN", "Poultry Production (Chicken)", "Agriculture & Fishery", [(1, 37, 41)]),
        ("SWINEPRODUCTION", "Swine Production", "Agriculture & Fishery", [(1, 42, 47)]),
        ("RUMINANTSPRODUCTION", "Ruminants Production", "Agriculture & Fishery", [(2, 26, 31)]),
        ("AQUACULTURE", "Aquaculture", "Agriculture & Fishery", [(1, 48, 52), (2, 32, 39)]),
        ("AGRICULTURALCROPSPRODUCTION", "Agricultural Crops Production", "Agriculture & Fishery", [(1, 53, 57), (2, 40, 47)]),
        ("FISHCAPTUREOPERATION", "Fish Capture Operation", "Agriculture & Fishery", [(1, 58, 65), (2, 48, 52)]),
        ("FOODPROCESSING", "Food Processing", "Agriculture & Fishery", [(1, 66, 72), (2, 53, 55)]),
        ("NAILCARESERVICES", "Nail Care Services", "Home Economics", [(1, 73, 79)]),
        ("FOODANDBEVERAGESERVICES", "Food and Beverage Services", "Hospitality and Tourism", [(1, 80, 86), (2, 63, 68)]),
        ("GARMENTSARTISANRY", "Garments Artisanry", "Home Economics", [(1, 87, 93), (2, 69, 72)]),
        ("WELLNESSMASSAGE", "Wellness Massage", "Home Economics", [(1, 94, 99)]),
        ("KITCHENOPERATIONS", "Kitchen Operations", "Hospitality and Tourism", [(1, 100, 110)]),
        ("FRONTOFFICESERVICES", "Front Office Services", "Hospitality and Tourism", [(1, 111, 119)]),
        ("NEEDLECRAFT", "Needlecraft", "Home Economics", [(1, 120, 129)]),
        ("TOURISMSERVICES", "Tourism Services", "Hospitality and Tourism", [(1, 130, 137), (2, 102, 105)]),
        ("AUTOMOTIVESERVICING", "Automotive Servicing", "Industrial Arts", [(1, 138, 143), (2, 106, 109)]),
        ("ELECTRICALINSTALLATIONANDMAINTENANCE", "Electrical Installation and Maintenance", "Industrial Arts", [(1, 144, 148)]),
        ("CARPENTRY", "Carpentry", "Industrial Arts", [(1, 149, 161), (2, 112, 119)]),
        ("MASONRY", "Masonry", "Industrial Arts", [(1, 162, 169)]),
        ("PLUMBING", "Plumbing", "Industrial Arts", [(1, 170, 174), (2, 120, 126)]),
        ("MANUALMETALARCWELDING", "Manual Metal Arc Welding", "Industrial Arts", [(1, 175, 183), (2, 127, 131)]),
        ("DOMESTICREFRIGERATIONANDAIRCONDITIONINGSERVICING", "Domestic Refrigeration and Air Conditioning Servicing", "Industrial Arts", [(2, 110, 111)]),
        ("HAIRDRESSINGSERVICES", "Hairdressing Services", "Home Economics", [(2, 56, 62)]),
        ("CAREGIVING", "Caregiving", "Home Economics", [(2, 73, 76)]),
        ("BREADANDPASTRYPRODUCTION", "Bread and Pastry Production", "Home Economics", [(2, 77, 83)]),
        ("HOUSEKEEPINGSERVICES", "Housekeeping Services", "Hospitality and Tourism", [(2, 84, 95)]),
        ("LEATHERCRAFT", "Leathercraft", "Home Economics", [(2, 96, 101)]),
    ],
    "TLE-G10": [
        ("COMPUTERPROGRAMMING", "Computer Programming", "ICT", [(1, 1, 11), (2, 1, 8)]),
        ("CONTACTCENTERSERVICES", "Contact Center Services", "ICT", [(1, 12, 22), (2, 9, 13)]),
        ("COMPUTERSYSTEMSSERVICING", "Computer Systems Servicing", "ICT", [(1, 23, 29), (2, 14, 19)]),
        ("ILLUSTRATION", "Illustration", "ICT", [(1, 30, 33), (2, 20, 25)]),
        ("ANIMATION", "Animation", "ICT", [(1, 34, 36)]),
        ("POULTRYPRODUCTIONCHICKEN", "Poultry Production (Chicken)", "Agriculture & Fishery", [(1, 37, 41)]),
        ("SWINEPRODUCTION", "Swine Production", "Agriculture & Fishery", [(1, 42, 47)]),
        ("RUMINANTSPRODUCTION", "Ruminants Production", "Agriculture & Fishery", [(2, 26, 31)]),
        ("AQUACULTURE", "Aquaculture", "Agriculture & Fishery", [(1, 48, 52), (2, 32, 39)]),
        ("AGRICULTURALCROPSPRODUCTION", "Agricultural Crops Production", "Agriculture & Fishery", [(1, 53, 57), (2, 40, 47)]),
        ("FISHCAPTUREOPERATION", "Fish Capture Operation", "Agriculture & Fishery", [(1, 58, 65), (2, 48, 52)]),
        ("FOODPROCESSING", "Food Processing", "Agriculture & Fishery", [(1, 66, 72), (2, 53, 55)]),
        ("NAILCARESERVICES", "Nail Care Services", "Home Economics", [(1, 73, 79)]),
        ("FOODANDBEVERAGESERVICES", "Food and Beverage Services", "Hospitality and Tourism", [(1, 80, 86), (2, 63, 68)]),
        ("GARMENTSARTISANRY", "Garments Artisanry", "Home Economics", [(1, 87, 93), (2, 69, 72)]),
        ("WELLNESSMASSAGE", "Wellness Massage", "Home Economics", [(1, 94, 99)]),
        ("KITCHENOPERATIONS", "Kitchen Operations", "Hospitality and Tourism", [(1, 100, 110)]),
        ("FRONTOFFICESERVICES", "Front Office Services", "Hospitality and Tourism", [(1, 111, 119)]),
        ("NEEDLECRAFT", "Needlecraft", "Home Economics", [(1, 120, 129)]),
        ("TOURISMSERVICES", "Tourism Services", "Hospitality and Tourism", [(1, 130, 137), (2, 102, 105)]),
        ("AUTOMOTIVESERVICING", "Automotive Servicing", "Industrial Arts", [(1, 138, 143), (2, 106, 109)]),
        ("ELECTRICALINSTALLATIONANDMAINTENANCE", "Electrical Installation and Maintenance", "Industrial Arts", [(1, 144, 148)]),
        ("CARPENTRY", "Carpentry", "Industrial Arts", [(1, 149, 161), (2, 112, 119)]),
        ("MASONRY", "Masonry", "Industrial Arts", [(1, 162, 169)]),
        ("PLUMBING", "Plumbing", "Industrial Arts", [(1, 170, 174), (2, 120, 126)]),
        ("MANUALMETALARCWELDING", "Manual Metal Arc Welding", "Industrial Arts", [(1, 175, 183), (2, 127, 131)]),
        ("DOMESTICREFRIGERATIONANDAIRCONDITIONINGSERVICING", "Domestic Refrigeration and Air Conditioning Servicing", "Industrial Arts", [(2, 110, 111)]),
        ("HAIRDRESSINGSERVICES", "Hairdressing Services", "Home Economics", [(2, 56, 62)]),
        ("CAREGIVING", "Caregiving", "Home Economics", [(2, 73, 76)]),
        ("BREADANDPASTRYPRODUCTION", "Bread and Pastry Production", "Home Economics", [(2, 77, 83)]),
        ("HOUSEKEEPINGSERVICES", "Housekeeping Services", "Hospitality and Tourism", [(2, 84, 95)]),
        ("LEATHERCRAFT", "Leathercraft", "Home Economics", [(2, 96, 101)]),
    ],
    "TLE-G7": [
        ("ICT", "Information and Communications Technology (ICT)", "ICT", [(1, 1, 9)]),
        ("AGRICULTURALCROPSPRODUCTION", "Agricultural Crops Production", "Agriculture & Fishery", [(2, 1, 10)]),
        ("ANIMALPRODUCTION", "Animal Production", "Agriculture & Fishery", [(2, 11, 17)]),
        ("TOURISMSERVICES", "Tourism Services", "Hospitality and Tourism", [(3, 1, 5)]),
        ("FOODANDBEVERAGESERVICES", "Food and Beverage Services", "Hospitality and Tourism", [(3, 6, 11)]),
        ("INDUSTRIALARTS", "Industrial Arts", "Industrial Arts", [(3, 12, 18)]),
    ],
    "TLE-G8": [
        ("ICT", "Information and Communications Technology (ICT)", "ICT", [(1, 1, 7)]),
        ("FISHERYARTS", "Fishery Arts", "Agriculture & Fishery", [(2, 1, 16)]),
        ("FOODPROCESSING", "Food Processing", "Agriculture & Fishery", [(2, 17, 25)]),
        ("AESTHETICSERVICESBEAUTYCARE", "Aesthetic Services (Beauty Care)", "Home Economics", [(3, 1, 6)]),
        ("GARMENTSARTISANRY", "Garments Artisanry", "Home Economics", [(3, 7, 9)]),
        ("HANDICRAFTSWEAVING", "Handicrafts (Weaving)", "Home Economics", [(3, 10, 12)]),
        ("INDUSTRIALARTS", "Industrial Arts", "Industrial Arts", [(3, 13, 19)]),
    ],
    "EPP-G4": [
        ("ICT", "Information and Communications Technology (ICT)", "ICT", [(1, 1, 11)]),
        ("AGRICULTURE", "Agriculture", "Agriculture & Fishery", [(2, 1, 14)]),
        ("HOMECONOMICS", "Home Economics", "Home Economics", [(3, 1, 16)]),
        ("INDUSTRIALARTS", "Industrial Arts", "Industrial Arts", [(3, 17, 29)]),
    ],
    "EPP-G5": [
        ("ICT", "Information and Communications Technology (ICT)", "ICT", [(1, 1, 10)]),
        ("ANIMALPRODUCTION", "Animal Production", "Agriculture & Fishery", [(2, 1, 10)]),
        ("HOMECONOMICS", "Home Economics", "Home Economics", [(3, 1, 15)]),
        ("INDUSTRIALARTS", "Industrial Arts", "Industrial Arts", [(3, 16, 23)]),
    ],
    "EPP-G6": [
        ("ICT", "Information and Communications Technology (ICT)", "ICT", [(1, 1, 8)]),
        ("FISHERYARTS", "Fishery Arts", "Agriculture & Fishery", [(2, 1, 10)]),
        ("HOMECONOMICS", "Home Economics", "Home Economics", [(3, 1, 11)]),
        ("INDUSTRIALARTS", "Industrial Arts", "Industrial Arts", [(3, 12, 16)]),
    ],
}

_CODE_RE = re.compile(r"-T(\d+)-(\d+)$")


def _parse_code(code):
    m = _CODE_RE.search(code)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _load_section_map():
    with open(PARSED, encoding="utf-8") as f:
        recs = json.load(f)
    by_file = {}
    for r in recs:
        by_file.setdefault(r["file"], set()).add(r.get("section", ""))
    return {f: next(iter(s)) for f, s in by_file.items()}


def _sshs_source_map():
    """code -> (name, [files]) derived from import_shs.build_subjects()."""
    out = {}
    for kind, grade, name, files in build_subjects():
        out[f"SSHS-{kind}-{slugify(name)}-G{grade_num(grade)}"] = (name, files)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(DB):
        print("DB not found:", DB)
        sys.exit(1)

    bak = DB + ".v3.bak"
    shutil.copy2(DB, bak)
    print(f"backup -> {bak}")

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    def nsub():
        return cur.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]

    def ncomp():
        return cur.execute("SELECT COUNT(*) FROM competencies").fetchone()[0]

    print(f"\nbefore: subjects={nsub()} competencies={ncomp()} user_version="
          f"{cur.execute('PRAGMA user_version').fetchone()[0]}")

    # ---- 0. add grouping column (needed before any grouped insert) ------
    cols = {r[1] for r in cur.execute("PRAGMA table_info(subjects)")}
    if "grouping" not in cols:
        cur.execute("ALTER TABLE subjects ADD COLUMN grouping TEXT")
        print("\n[0] added subjects.grouping")
    else:
        print("\n[0] subjects.grouping already present")

    # ---- 1. remove old-curriculum SHS subjects ---------------------------
    old = cur.execute(
        "SELECT code, name FROM subjects WHERE grade_level IN ('Grade 11','Grade 12') "
        "AND code NOT LIKE 'SSHS-%' ORDER BY grade_level, code"
    ).fetchall()
    print(f"\n[1] deleting {len(old)} old-curriculum SHS subjects:")
    for code, name in old:
        print(f"    {code}  {name}")
    cur.execute(
        "DELETE FROM competencies WHERE subject_id IN "
        "(SELECT id FROM subjects WHERE grade_level IN ('Grade 11','Grade 12') "
        "AND code NOT LIKE 'SSHS-%')"
    )
    cur.execute(
        "DELETE FROM subjects WHERE grade_level IN ('Grade 11','Grade 12') "
        "AND code NOT LIKE 'SSHS-%'"
    )

    # ---- 2. merge the two SSHS G11 core communication subjects -----------
    print("\n[2] merging core communication subjects")
    src_ids = []
    for code in CORE_MERGE_SOURCES:
        row = cur.execute("SELECT id, name FROM subjects WHERE code = ?", (code,)).fetchone()
        if not row:
            print(f"    WARNING: source core subject {code} not found")
            continue
        src_ids.append(row[0])
        print(f"    source: {row[0]} {code} ({row[1]})")
    if src_ids:
        if cur.execute("SELECT 1 FROM subjects WHERE code = ?", (MERGED_CORE_CODE,)).fetchone():
            print(f"    merged subject {MERGED_CORE_CODE} already exists; skipping")
        else:
            cur.execute(
                "INSERT INTO subjects (code, name, grade_level, sort_order, grouping) VALUES (?, ?, 'Grade 11', 11, ?)",
                (MERGED_CORE_CODE, MERGED_CORE_NAME, MERGED_CORE_GROUPING),
            )
            mid = cur.execute("SELECT id FROM subjects WHERE code = ?", (MERGED_CORE_CODE,)).fetchone()[0]
            moved = 0
            for term in sorted({r[0] for r in cur.execute(
                    "SELECT DISTINCT term FROM competencies WHERE subject_id IN (%s)"
                    % ",".join("?" * len(src_ids)), src_ids)}):
                seq = 0
                rows = cur.execute(
                    """SELECT week, description, content_standard, performance_standard
                       FROM competencies WHERE subject_id IN (%s) AND term = ?
                       ORDER BY subject_id, id""" % ",".join("?" * len(src_ids)),
                    src_ids + [term]).fetchall()
                for row in rows:
                    seq += 1
                    cur.execute(
                        """INSERT INTO competencies
                           (subject_id, term, week, code, description, content_standard, performance_standard)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (mid, term, row[0], f"{MERGED_CORE_CODE}-T{term}-{seq:02d}",
                         row[1], row[2], row[3]),
                    )
                    moved += 1
            cur.execute("DELETE FROM competencies WHERE subject_id IN (%s)" % ",".join("?" * len(src_ids)), src_ids)
            cur.execute("DELETE FROM subjects WHERE id IN (%s)" % ",".join("?" * len(src_ids)), src_ids)
            print(f"    merged into {MERGED_CORE_CODE} with {moved} competencies")

    # ---- 3. tag SSHS subjects with a grouping ----------------------------
    print("\n[4] assigning SSHS groupings from shs_parsed.json")
    sec = _load_section_map()
    src_map = _sshs_source_map()
    unmatched = []
    updated = 0
    ssubs = cur.execute("SELECT code, name FROM subjects WHERE code LIKE 'SSHS-%'").fetchall()
    for code, name in ssubs:
        files = None
        if code in src_map:
            files = src_map[code][1]
        else:
            for c, (n, fl) in src_map.items():
                if n == name:
                    files = fl
                    break
        grouping = ""
        if files:
            for f in files:
                s = sec.get(f, "")
                if s:
                    grouping = SECTION_NORM.get(s, s)
                    break
        if grouping:
            cur.execute("UPDATE subjects SET grouping = ? WHERE code = ?", (grouping, code))
            updated += 1
        else:
            have = cur.execute("SELECT grouping FROM subjects WHERE code = ?", (code,)).fetchone()[0]
            if not have:
                unmatched.append((code, name))
    print(f"    tagged {updated} SSHS subjects")
    if unmatched:
        print("    SUBJECTS WITH NO GROUPING (review):")
        for code, name in unmatched:
            print(f"      {code}  {name}")

    # ---- 4. split EPP/TLE into specializations ---------------------------
    print("\n[5] splitting EPP/TLE into specialization subjects")
    for src_code, specs in SPLITS.items():
        src = cur.execute("SELECT id, name FROM subjects WHERE code = ?", (src_code,)).fetchone()
        if not src:
            print(f"    {src_code}: not found, skipping")
            continue
        src_id, src_name = src
        comps = cur.execute(
            "SELECT id, term, week, code, description, content_standard, performance_standard "
            "FROM competencies WHERE subject_id = ?", (src_id,)
        ).fetchall()
        by_key = {}
        for cid, term, week, code, desc, cs, ps in comps:
            parsed = _parse_code(code)
            if parsed is None:
                print(f"    WARNING: unparseable code {code}")
                continue
            by_key[(parsed[0], parsed[1])] = (cid, term, week, desc, cs, ps)
        total_moved = 0
        grade_lvl = cur.execute("SELECT grade_level FROM subjects WHERE id = ?", (src_id,)).fetchone()[0]
        grade_num_val = grade_num(grade_lvl)
        print(f"    {src_code} ({src_name}, {len(comps)} comps) ->")
        for slug, name, grouping, ranges in specs:
            new_code = f"{src_code}-{slug}"
            if cur.execute("SELECT 1 FROM subjects WHERE code = ?", (new_code,)).fetchone():
                print(f"      {new_code}  exists, skipping")
                continue
            wanted = []
            for term, lo, hi in ranges:
                for seq in range(lo, hi + 1):
                    row = by_key.get((term, seq))
                    if row is None:
                        print(f"      WARNING: missing {src_code}-T{term}-{seq:03d}")
                        continue
                    wanted.append((term, row))
            if not wanted:
                print(f"      {new_code}  NO COMPETENCIES, skipping")
                continue
            cur.execute(
                "INSERT INTO subjects (code, name, grade_level, sort_order, grouping) VALUES (?, ?, ?, ?, ?)",
                (new_code, name, grade_lvl, grade_num_val, grouping),
            )
            nid = cur.execute("SELECT id FROM subjects WHERE code = ?", (new_code,)).fetchone()[0]
            for term in sorted({t for t, _ in wanted}):
                seq = 0
                for _, (cid, _t, week, desc, cs, ps) in sorted(wanted, key=lambda x: x[1][1]):
                    if _t != term:
                        continue
                    seq += 1
                    cur.execute(
                        """INSERT INTO competencies
                           (subject_id, term, week, code, description, content_standard, performance_standard)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (nid, term, week, f"{new_code}-T{term}-{seq:02d}", desc, cs, ps),
                    )
            nmoved = sum(1 for _, _ in wanted)
            total_moved += nmoved
            per_term = ", ".join(f"T{t}:{sum(1 for _t, _ in wanted if _t == t)}" for t in sorted({t for t, _ in wanted}))
            print(f"      {new_code:36s} {name[:40]:40s} [{grouping}]  {per_term}")
        cur.execute("DELETE FROM competencies WHERE subject_id = ?", (src_id,))
        cur.execute("DELETE FROM subjects WHERE id = ?", (src_id,))
        print(f"    removed generic {src_code}; moved {total_moved} competencies total")

    # ---- 5. user_version ------------------------------------------------
    cur.execute("PRAGMA user_version = 3")

    print(f"\nafter: subjects={nsub()} competencies={ncomp()} user_version=3")

    print("\n--- subjects by grade (name / grouping) ---")
    for grade in [f"Grade {g}" for g in range(4, 13)]:
        rows = cur.execute(
            "SELECT name, grouping FROM subjects WHERE grade_level = ? ORDER BY grouping, name",
            (grade,),
        ).fetchall()
        print(f"\n{grade} ({len(rows)})")
        last = None
        for name, grouping in rows:
            if grouping != last:
                print(f"  [{grouping}]")
                last = grouping
            print(f"    - {name}")

    if not args.commit:
        conn.rollback()
        print("\nDRY RUN (rolled back). Re-run with --commit to save.")
    else:
        conn.commit()
        print("\nCOMMITTED.")
    conn.close()


if __name__ == "__main__":
    main()
