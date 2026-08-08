import argparse
import json
import os
import re
import sqlite3
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_DEF_DB = r"C:\Users\Administrator\Desktop\LAMDAG-Portable\database\matatag_cg.db"

# quarter -> term  aligned with official DepEd three-term calendar
# (DO 009, s. 2026: T1 Jun8-Sep15, T2 Sep16-Dec18, T3 Jan4-Apr8):
#   Q1 (Jun-Sep) -> T1, Q2 (Sep-Dec) -> T2, Q3+Q4 (Jan-Apr) -> T3
Q2T = {1: 1, 2: 2, 3: 3, 4: 3}

GRADE_ORDER = {
    "Kindergarten": 0,
    "Grade 1": 1, "Grade 2": 2, "Grade 3": 3, "Grade 4": 4,
    "Grade 5": 5, "Grade 6": 6, "Grade 7": 7, "Grade 8": 8,
    "Grade 9": 9, "Grade 10": 10, "Grade 11": 11, "Grade 12": 12,
}


def grade_num(grade):
    if grade == "Kindergarten":
        return 0
    m = re.fullmatch(r"Grade (\d+)", grade)
    return int(m.group(1)) if m else None


def subject_target(subject, grade):
    g = grade_num(grade)
    if subject == "Araling Panlipunan":
        return f"AP-G{g}", "Araling Panlipunan"
    if subject == "English":
        return f"ENG-G{g}", "English"
    if subject == "EPP/TLE":
        if g <= 6:
            return f"EPP-G{g}", "EPP/TLE"
        return f"TLE-G{g}", "TLE"
    if subject == "Filipino":
        return f"FIL-G{g}", "Filipino"
    if subject == "GMRC/VE":
        if g <= 6:
            return f"GMRC-G{g}", "GMRC"
        return f"VE-G{g}", "Values Education"
    if subject == "Kindergarten":
        return "KINDER", "Kindergarten"
    if subject == "Language":
        return "LANG-G1", "Language"
    if subject == "Makabansa":
        return f"MAKABANSA-G{g}", "Makabansa"
    if subject == "Mathematics":
        return f"MATH-G{g}", "Mathematics"
    if subject == "Music and Arts":
        return f"MA-G{g}", "Music and Arts"
    if subject == "PE and Health":
        return f"PEH-G{g}", "PE and Health"
    if subject == "Reading and Literacy":
        return "RL-G1", "Reading and Literacy"
    if subject == "Science":
        return f"SCI-G{g}", "Science"
    return None, None


def main():
    ap = argparse.ArgumentParser(description="Import official MATATAG K-10 competencies into LAMDAG DB")
    ap.add_argument("parsed_json", nargs="?", default=None,
                    help="parsed_cg.json path (default: alongside this script)")
    ap.add_argument("-d", "--db", default=None,
                    help=f"target sqlite db path (default: {_DEF_DB})")
    args = ap.parse_args()

    if args.parsed_json:
        PARSED = args.parsed_json
    else:
        PARSED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parsed_cg.json")
    DB = args.db or _DEF_DB

    with open(PARSED, encoding="utf-8") as f:
        recs = json.load(f)
    print(f"parsed_cg.json: {len(recs)} records")

    # group parsed records by target subject code
    by_code = {}
    unmapped = []
    for r in recs:
        code, name = subject_target(r["subject"], r["grade"])
        if code is None:
            unmapped.append((r["subject"], r["grade"]))
            continue
        by_code.setdefault(code, {"name": name, "grade": r["grade"], "rows": []})
        by_code[code]["rows"].append(r)

    if unmapped:
        print("UNMAPPED:", set(unmapped))
    print(f"target subjects: {len(by_code)}")

    # backup db
    bak = DB + ".bak"
    shutil.copy2(DB, bak)
    print(f"backup -> {bak}")

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    owned = set(by_code.keys())
    removed_mapeh = [f"MAPEH-G{g}" for g in range(4, 11)]
    affected = owned | set(removed_mapeh)

    # delete old competencies + subjects for affected codes
    ph = ",".join("?" * len(affected))
    cur.execute(f"DELETE FROM competencies WHERE subject_id IN "
                f"(SELECT id FROM subjects WHERE code IN ({ph}))", sorted(affected))
    cur.execute(f"DELETE FROM subjects WHERE code IN ({ph})", sorted(affected))
    conn.commit()
    print(f"removed old rows for {len(affected)} subject codes "
          f"(incl. MAPEH-G4..G10: {removed_mapeh})")

    # insert subjects
    for code, info in sorted(by_code.items()):
        cur.execute(
            "INSERT OR IGNORE INTO subjects (code, name, grade_level, sort_order) VALUES (?, ?, ?, ?)",
            (code, info["name"], info["grade"], GRADE_ORDER.get(info["grade"], 99)),
        )
    conn.commit()

    cur.execute("SELECT id, code FROM subjects WHERE code IN ({})".format(
        ",".join("?" * len(owned))), list(owned))
    sid = {row[1]: row[0] for row in cur.fetchall()}

    # insert competencies
    #  - exploratory TLE G9/G10: same course listed under "QUARTER I/III" and
    #    "II/IV" (offered in one OR the other) -> global dedupe by description,
    #    keep earliest quarter so each competency lands in exactly one term
    #  - other subjects: spiral competencies may repeat across quarters with
    #    distinct official codes -> dedupe only WITHIN a term
    total = 0
    dupes = 0
    for code, info in sorted(by_code.items()):
        tle_explor = code in ("TLE-G9", "TLE-G10")
        best = {}
        for r in info["rows"]:
            desc = (r["description"] or "").strip()
            if not desc:
                continue
            q = r["quarter"]
            if tle_explor:
                key = desc.casefold()
            else:
                key = (Q2T.get(q), desc.casefold())
            if key not in best or q < best[key][0]:
                best[key] = (q, r)
        dupes += len(info["rows"]) - len(best)
        for key, (q, r) in best.items():
            term = Q2T.get(q)
            if term is None:
                print("  ! no term for quarter", q, code, r["description"])
                continue
            desc = (r["description"] or "").strip()
            cur.execute(
                """INSERT OR IGNORE INTO competencies
                   (subject_id, term, week, code, description, content_standard, performance_standard)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sid[code], term, None, (r["code"] or "").strip(), desc,
                 r["content_standard"] or "", r["performance_standard"] or ""),
            )
            total += 1
    conn.commit()

    print(f"competencies inserted: {total} (duplicates skipped: {dupes})")

    # report
    print("\n--- per subject / grade / term ---")
    for row in cur.execute(
        """SELECT s.code, s.name, s.grade_level, c.term, COUNT(*)
           FROM subjects s LEFT JOIN competencies c ON c.subject_id = s.id
           WHERE s.code IN ({})
           GROUP BY s.id, c.term
           ORDER BY s.sort_order, s.code, c.term""".format(",".join("?" * len(owned))),
        list(owned)):
        print(f"  {row[0]:12s} {row[1]:20s} {row[2]:12s} T{row[3]}: {row[4]}")

    print("\n--- DB totals ---")
    print("subjects:", cur.execute("SELECT COUNT(*) FROM subjects").fetchone()[0])
    print("competencies:", cur.execute("SELECT COUNT(*) FROM competencies").fetchone()[0])
    ids = sorted(sid.values())
    ph = ",".join("?" * len(ids))
    print("competencies (K-10 official):", cur.execute(
        f"SELECT COUNT(*) FROM competencies WHERE subject_id IN ({ph})", ids).fetchone()[0])
    print("competencies (SHS untouched):", cur.execute(
        f"SELECT COUNT(*) FROM competencies WHERE subject_id NOT IN ({ph})", ids).fetchone()[0])

    conn.close()


if __name__ == "__main__":
    main()
