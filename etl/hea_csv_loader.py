"""
hea_csv_loader.py
==================
Ireland in Data — HEA Enrolments CSV Loader
Transforms the raw CSV snapshots downloaded by hea_enrolments.py into rows
in fact_student_enrolments.

Verified format (2026-08-19, both files in data/raw/hea/): a WIDE pivot —
one row per Programme Type, one column per academic year:

    "Programme Type","2018/2019","2019/2020",...,"2024/2025"
    "Certificates",1570,1725,...,1695
    ...
    "TOTAL",...

There is NO Institution, Gender, Domicile, or Field-of-Study column in
either downloaded file — hea_enrolments.py's Shiny filters aggregate those
away before download. Consequently this loader can only populate:
  isced_label   = "Health and welfare" (the field filter both downloads use)
  programme_type = the row's Programme Type value
  academic_year  = the column header
  headcount      = the cell value
Every other column (institution_id, gender, eu_status, isced_code,
programme_level, entry_type, mode) is left NULL — there is no source data
to populate them from these particular downloads. Getting institution- or
gender-level enrolment data would need different Shiny filter/grouping
settings in hea_enrolments.py (a separate, not-yet-done piece of work).

IMPORTANT — the two files are OVERLAPPING, not additive:
  hea_enrolments_health_welfare_*.csv        = all Health & Welfare students
  hea_enrolments_medicine_institutions_*.csv = the subset of those students
                                                at UCD/UCC/TCD/Galway/UL/RCSI
Both get loaded (source_file distinguishes them), but summing headcount
across both source files double-counts every medicine-institution student.
Always filter WHERE source_file = '...' for a coherent total; never SUM
across the whole table without that filter.

"TOTAL" rows are dropped at load time — they're a derived aggregate of the
other rows in the same file, not a real programme type, and summing the
table naively would double-count them too.

Run:
  python hea_csv_loader.py --inspect                                   # safe, no writes
  python hea_csv_loader.py --load --db data/education.duckdb
  python hea_csv_loader.py --load --db data/education.duckdb --file data/raw/hea/hea_enrolments_health_welfare_2026-08-19.csv
"""

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "hea"
ISCED_LABEL = "Health and welfare"  # the field-of-study filter used for every download
ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{4}$")


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------

def read_csv(path: Path):
    """Read a raw HEA CSV. Returns (header, rows) where rows is a list of dicts."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    return header, rows


def year_columns(header):
    """Which header columns look like academic years, e.g. '2024/2025'."""
    return [c for c in header if ACADEMIC_YEAR_RE.match(c.strip())]


def parse_headcount(raw: str):
    """Parse a HEA cell value. Handles commas; treats blank/'-'/non-numeric as
    suppressed/missing (None) rather than crashing or silently becoming 0."""
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "")
    if cleaned in ("", "-", "..", "N/A", "c"):
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# --inspect
# ---------------------------------------------------------------------------

def inspect():
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        print(f"No CSVs found in {RAW_DIR}")
        return

    for path in files:
        print(f"\n{'─' * 60}")
        print(f"File: {path.name}")
        header, rows = read_csv(path)
        print(f"  Columns ({len(header)}): {header}")

        id_cols = [c for c in header if c not in year_columns(header)]
        yr_cols = year_columns(header)
        print(f"  Identifier column(s): {id_cols}")
        print(f"  Academic-year columns: {yr_cols}")

        unrecognised = [c for c in header if c not in id_cols and c not in yr_cols]
        if unrecognised:
            print(f"  ⚠ Not recognised as identifier or academic-year: {unrecognised}")

        if id_cols != ["Programme Type"]:
            print(f"  ⚠ Expected identifier column to be exactly ['Programme Type'] — "
                  f"got {id_cols}. Loader logic may need updating for this file's shape.")

        print(f"  Rows: {len(rows)}")
        prog_types = [r.get("Programme Type", "") for r in rows]
        print(f"  Programme Type values: {prog_types}")

        # Spot-check for non-numeric / suppressed cells
        bad_cells = []
        for r in rows:
            for c in yr_cols:
                if parse_headcount(r.get(c)) is None and r.get(c, "").strip() not in ("",):
                    bad_cells.append((r.get("Programme Type"), c, r.get(c)))
        if bad_cells:
            print(f"  ⚠ Cells that didn't parse as a plain number: {bad_cells}")


# ---------------------------------------------------------------------------
# --load
# ---------------------------------------------------------------------------

def melt_file(path: Path):
    """Turn one wide CSV into a list of long-format row dicts, dropping TOTAL."""
    header, rows = read_csv(path)
    yr_cols = year_columns(header)
    out = []
    skipped_total = 0

    for r in rows:
        programme_type = (r.get("Programme Type") or "").strip()
        if programme_type.upper() == "TOTAL":
            skipped_total += 1
            continue
        for yr in yr_cols:
            headcount = parse_headcount(r.get(yr))
            out.append({
                "institution_id": None,
                "academic_year": yr,
                "gender": None,
                "eu_status": None,
                "isced_code": None,
                "isced_label": ISCED_LABEL,
                "programme_level": None,
                "programme_type": programme_type,
                "entry_type": None,
                "mode": None,
                "headcount": headcount,
                "is_rounded": True,
                "source_file": path.name,
            })

    return out, skipped_total


def load(db_path: str, only_file: str = None):
    import duckdb

    files = sorted(RAW_DIR.glob("*.csv"))
    if only_file:
        files = [Path(only_file)]
    if not files:
        print(f"No CSVs found in {RAW_DIR}")
        sys.exit(1)

    conn = duckdb.connect(db_path)
    print(f"Connected to DuckDB: {db_path}")

    total_inserted = 0
    for path in files:
        if not path.exists():
            print(f"  ⚠ Skipping missing file: {path}")
            continue

        print(f"\n{'─' * 60}")
        print(f"File: {path.name}")
        long_rows, skipped_total = melt_file(path)

        conn.executemany(
            """
            INSERT INTO fact_student_enrolments
                (institution_id, academic_year, gender, eu_status, isced_code,
                 isced_label, programme_level, programme_type, entry_type, mode,
                 headcount, is_rounded, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (r["institution_id"], r["academic_year"], r["gender"], r["eu_status"],
                 r["isced_code"], r["isced_label"], r["programme_level"], r["programme_type"],
                 r["entry_type"], r["mode"], r["headcount"], r["is_rounded"], r["source_file"])
                for r in long_rows
            ],
        )
        print(f"  Inserted {len(long_rows)} rows ({skipped_total} TOTAL row(s) dropped)")
        total_inserted += len(long_rows)

    print(f"\n{'─' * 60}")
    print(f"Total rows inserted: {total_inserted}")

    # ── Validation printout ────────────────────────────────────────────────
    print("\nValidation — headcount by academic_year, per source_file "
          "(do NOT sum across source_file — see module docstring, files overlap):")
    result = conn.execute("""
        SELECT source_file, academic_year, SUM(headcount) AS total_headcount
        FROM fact_student_enrolments
        WHERE source_file IN (SELECT DISTINCT source_file FROM fact_student_enrolments)
        GROUP BY source_file, academic_year
        ORDER BY source_file, academic_year
    """).fetchall()
    for row in result:
        print(f"  {row[0]:50s} {row[1]:10s} {row[2]}")

    conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="HEA enrolments CSV → DuckDB loader")
    parser.add_argument("--inspect", action="store_true",
                        help="Print column/shape info for every raw CSV. Safe, no writes.")
    parser.add_argument("--load", action="store_true",
                        help="Load raw CSVs into fact_student_enrolments.")
    parser.add_argument("--db", default="data/education.duckdb",
                        help="Path to DuckDB database file (--load only)")
    parser.add_argument("--file", default=None,
                        help="Load only this one CSV instead of every file in data/raw/hea/")
    args = parser.parse_args()

    if not args.inspect and not args.load:
        parser.print_help()
        sys.exit(0)

    if args.inspect:
        inspect()

    if args.load:
        load(args.db, only_file=args.file)


if __name__ == "__main__":
    main()
