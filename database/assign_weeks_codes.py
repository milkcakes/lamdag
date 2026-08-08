"""Assign weeks and generate codes for imported MATATAG competencies.

Idempotent: only touches competencies whose week is NULL (assigns weeks) and
whose code is empty (generates codes). Subjects with official CG codes
(English, Language, Reading and Literacy, SHS) and existing weeks are untouched.

Weeks are spread evenly across the full 10-week term so every subject/term
reaches Week 10 (start at Week 1, land the last competency on Week 10).

Run:  python database/assign_weeks_codes.py [--db PATH] [--commit]
"""

import argparse
import os
import sqlite3
import sys

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matatag_cg.db")


def assign(db_path, commit=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    subjects = cur.execute(
        "SELECT id, code FROM subjects"
    ).fetchall()
    code_by_subject = {s["id"]: s["code"] for s in subjects}

    changed_weeks = 0
    changed_codes = 0

    rows = cur.execute(
        """SELECT id, subject_id, term, week, code
           FROM competencies
           ORDER BY subject_id, term, id"""
    ).fetchall()

    groups = {}
    for r in rows:
        groups.setdefault((r["subject_id"], r["term"]), []).append(r)

    for (subject_id, term), comps in groups.items():
        subject_code = code_by_subject.get(subject_id, "SUBJ")
        n = len(comps)
        width = max(2, len(str(n)))

        seq = 0
        for i, c in enumerate(comps):
            sets = []
            if c["week"] is None:
                # Even-spread across the full 10-week term: always start at
                # Week 1 and land the last competency on Week 10.
                week = 1 if n == 1 else min(10, 1 + (i * 9) // (n - 1))
                sets.append(("week", week))
            if not (c["code"] or "").strip():
                seq += 1
                code = f"{subject_code}-T{term}-{seq:0{width}d}"
                sets.append(("code", code))
            if sets:
                set_sql = ", ".join(f"{col} = ?" for col, _ in sets)
                vals = [val for _, val in sets]
                cur.execute(
                    f"UPDATE competencies SET {set_sql} WHERE id = ?",
                    vals + [c["id"]],
                )
                for col, _ in sets:
                    if col == "week":
                        changed_weeks += 1
                    else:
                        changed_codes += 1

    if commit:
        conn.commit()
        print(f"COMMITTED. weeks assigned: {changed_weeks}, codes generated: {changed_codes}")
    else:
        conn.rollback()
        print(f"DRY RUN (no changes saved). weeks to assign: {changed_weeks}, codes to generate: {changed_codes}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()
    assign(args.db, commit=args.commit)
