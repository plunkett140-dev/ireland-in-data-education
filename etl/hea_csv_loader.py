"""
hea_csv_loader.py
==================
Ireland in Data — HEA Enrolments CSV Loader
Transforms the raw CSV snapshots downloaded by hea_enrolments.py into rows
in fact_student_enrolments.

Verified format (2026-08-19): a WIDE pivot, one row per category, one column
per academic year. Three distinct shapes, by filename / identifier column(s):

  hea_enrolments_health_welfare_*.csv        "Programme Type"          -> programme_type
  hea_enrolments_medicine_institutions_*.csv "Programme Type"          -> programme_type
  hea_enrolments_gender_*.csv                "Gender"                  -> gender
  hea_enrolments_domicile_*.csv              "Domicile Group","Domicile" -> eu_status

The domicile file is two levels deep — a "Domicile Group" (Ireland /
(Other) EU / Non-EU / Great Britain / Northern Ireland / Unknown) broken
further into individual countries, with a "<Group>_TOTAL" rollup row per
group. This loader uses ONLY the "_TOTAL" rows for fact_student_enrolments
(one row per group per year) — the individual-country detail is real and
worth having but isn't loaded here; a future per-country chart would read
the raw CSV directly rather than adding ~150 country rows to this table.

There is no Institution or ISCED-code column in any of these files, and no
file combines more than one of {Programme Type, Gender, Domicile Group} at
once — each download is a different single-dimension cut of the SAME
underlying Health & Welfare population (medicine_institutions narrows
institutions too). Consequently a given row only ever populates ONE of
{programme_type, gender, eu_status}; the other two stay NULL. Getting a
combined cut (e.g. Domicile x Gender together) would need a different Shiny
Row/Column Variable combination — not fetched by hea_enrolments.py today.

isced_label is always "Health and welfare" — none of these files isolate
Medicine specifically. HEA's Field of Study filter doesn't offer a
narrower-than-broad-field option; Medicine-specific data only comes from
the CSO HGO tables via cso_hgo.py, not from HEA.

IMPORTANT — files are OVERLAPPING, not additive. Every file (except
medicine_institutions, which narrows institutions) covers the exact same
national Health & Welfare population, just sliced by a different dimension.
Never SUM across source_file — always filter WHERE source_file = '...' for
a coherent total. GROUP BY source_file is done for you in the validation
printout below.

"TOTAL" / "<Group>_TOTAL" grand-total rows are dropped at load time (except
that domicile's "_TOTAL" rows ARE the data we keep — see above) — they're
derived aggregates, not real categories, and summing the table naively
would double-count them.

Run:
  python hea_csv_loader.py --inspect                                   # safe, no writes
  python hea_csv_loader.py --load --db data/education.duckdb
  python hea_csv_loader.py --load --db data/education.duckdb --file data/raw/hea/hea_enrolments_gender_2026-08-19.csv
"""

import argparse
import csv
import re
import sys
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
# Shape detection — which schema column does this file's category map to?
# ---------------------------------------------------------------------------

# id_cols (as a tuple, in header order) -> target fact_student_enrolments column
SHAPE_MAP = {
    ("Programme Type",): "programme_type",
    ("Gender",): "gender",
    ("Domicile Group", "Domicile"): "eu_status",
}


def detect_shape(header):
    yr_cols = set(year_columns(header))
    id_cols = tuple(c for c in header if c not in yr_cols)
    return id_cols, SHAPE_MAP.get(id_cols)


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

        id_cols, target_field = detect_shape(header)
        yr_cols = year_columns(header)
        print(f"  Identifier column(s): {list(id_cols)}")
        print(f"  Academic-year columns: {yr_cols}")

        if target_field is None:
            print(f"  ⚠ Unrecognised shape {id_cols} — not in SHAPE_MAP, "
                  f"this file won't load until SHAPE_MAP is updated for it.")
        else:
            print(f"  Maps to fact_student_enrolments.{target_field}")

        print(f"  Rows: {len(rows)}")
        if len(id_cols) == 1:
            vals = [r.get(id_cols[0], "") for r in rows]
            print(f"  {id_cols[0]} values: {vals}")
        else:
            # multi-level (domicile): show just the _TOTAL rows we'll actually use
            totals = [r.get(id_cols[0], "") for r in rows if r.get(id_cols[0], "").endswith("_TOTAL")]
            print(f"  Group _TOTAL rows (what gets loaded): {totals}")
            print(f"  ({len(rows) - len(totals)} individual-country/detail rows NOT loaded — see docstring)")

        # Spot-check for non-numeric / suppressed cells
        bad_cells = []
        for r in rows:
            for c in yr_cols:
                cell = r.get(c, "")
                if parse_headcount(cell) is None and cell.strip() != "":
                    bad_cells.append((r.get(id_cols[0]), c, cell))
        if bad_cells:
            print(f"  ⚠ Cells that didn't parse as a plain number: {bad_cells[:10]}"
                  f"{' ...' if len(bad_cells) > 10 else ''}")


# ---------------------------------------------------------------------------
# --load
# ---------------------------------------------------------------------------

def melt_file(path: Path):
    """Turn one wide CSV into a list of long-format row dicts."""
    header, rows = read_csv(path)
    id_cols, target_field = detect_shape(header)
    yr_cols = year_columns(header)
    out = []
    skipped_total = 0

    if target_field is None:
        raise ValueError(f"{path.name}: unrecognised identifier columns {id_cols} — "
                          f"add a SHAPE_MAP entry for this file's shape before loading")

    if len(id_cols) == 1:
        # Simple one-level shape: Programme Type or Gender
        id_col = id_cols[0]
        for r in rows:
            category = (r.get(id_col) or "").strip()
            if category.upper() == "TOTAL":
                skipped_total += 1
                continue
            for yr in yr_cols:
                out.append(_row(target_field, category, yr, parse_headcount(r.get(yr)), path.name))
    else:
        # Two-level domicile shape: keep only the "<Group>_TOTAL" rollup rows,
        # skip the individual-country detail rows and the grand "TOTAL" row.
        group_col, detail_col = id_cols
        for r in rows:
            group_raw = (r.get(group_col) or "").strip()
            if group_raw == "TOTAL":
                skipped_total += 1
                continue
            if not group_raw.endswith("_TOTAL"):
                continue  # individual-country detail row — not loaded here
            category = group_raw[: -len("_TOTAL")]
            for yr in yr_cols:
                out.append(_row(target_field, category, yr, parse_headcount(r.get(yr)), path.name))

    return out, skipped_total


def _row(target_field, category, academic_year, headcount, source_file):
    row = {
        "institution_id": None, "academic_year": academic_year, "gender": None,
        "eu_status": None, "isced_code": None, "isced_label": ISCED_LABEL,
        "programme_level": None, "programme_type": None, "entry_type": None,
        "mode": None, "headcount": headcount, "is_rounded": True, "source_file": source_file,
    }
    row[target_field] = category
    return row


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
        try:
            long_rows, skipped_total = melt_file(path)
        except ValueError as e:
            print(f"  ⚠ Skipping: {e}")
            continue

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
