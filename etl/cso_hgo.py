"""
cso_hgo.py
==========
Ireland in Data — CSO Health Graduate Outcomes ETL
Downloads HGO tables from the CSO PxStat REST API and saves dated CSV snapshots.

Tables collected (verified against CSO's own PxStat labels 2026-08-19 — the
codes below are confirmed live and correctly matched; earlier drafts of this
script had several wrong):
  HGO07  "Number of Health Graduates"                    — counts, NO institution dimension
  HGO09  "Health Graduate Outcomes"                       — the "Not Captured" proxy table
  HGO11  "Number of Health Graduates that Returned to Ireland"
  HGO15  "Graduate Earnings"

Dropped from the original table list:
  HGO08  Does not exist in CSO's PxStat catalog (404). There is no second
         institution/gender-split counts table alongside HGO07.
  HGO16  Exists, but is "Graduate Occupations in Census 2022", not "earnings
         by gender" as originally assumed — no loader reads it, so it was
         never actually used; dropped rather than left as a misleading label.

Decision E004 (schema/create_education_schema.sql): fact_health_graduates is
NATIONAL-LEVEL by design. HGO07's only dimensions are Graduation Year,
Nationality, PPSN Validity, Gender, and Field of Study — no institution at
all — and no other HGO table adds one. load_health_graduates() below does
not attempt institution matching; institution_id is always NULL for
CSO-sourced rows. This was a deliberate call (2026-08-19), not an oversight
— see the schema file's decision log before revisiting it.

Endpoint pattern (confirmed, public, no auth required):
  https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{TABLE}/CSV/1.0/en

NOTE: This endpoint is blocked from the Anthropic cloud sandbox (HTTP 403).
Run this script locally or in GitHub Actions.

Decision E002: The "Not Captured" outcome in HGO09 is NOT confirmed emigration.
CSO background notes state it means graduates not found in Irish employment or
social insurance records. Always label as "not captured in Irish employment records".

Decision (RCSI exclusion): HGO07 RCSI medicine graduates 2012–2016 must be loaded
with data_excluded=True due to PPSN validation issues (documented in CSO background notes).

Run:
  pip install requests pandas duckdb
  python cso_hgo.py [--tables HGO07 HGO09] [--db path/to/education.duckdb]
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CSO_BASE = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset"
TABLES = ["HGO07", "HGO09", "HGO11", "HGO15"]
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "cso"
TODAY = date.today().isoformat()

# CSO institution name → our institution_id. Currently unused — no CSO HGO
# table has an institution dimension (Decision E004) — kept in case a future
# per-institution source (HEA?) needs the same mapping.
INSTITUTION_MAP = {
    "University College Dublin":             "UCD",
    "UCD":                                   "UCD",
    "University College Cork":               "UCC",
    "UCC":                                   "UCC",
    "Trinity College Dublin":                "TCD",
    "TCD":                                   "TCD",
    "University of Galway":                  "NUIG",
    "NUI Galway":                            "NUIG",
    "University of Limerick":                "UL",
    "UL":                                    "UL",
    "Royal College of Surgeons in Ireland":  "RCSI",
    "RCSI":                                  "RCSI",
}

# RCSI data exclusion: HGO07, graduation years 2012–2016
# Source: CSO background note on PPSN validation issues
RCSI_EXCLUSION = {
    "table": "HGO07",
    "institution": "RCSI",
    "years": list(range(2012, 2017)),
    "reason": "RCSI PPSN validation issues 2012-2016 (CSO HGO07 background note)"
}


# ---------------------------------------------------------------------------
# Shared value parsing
# ---------------------------------------------------------------------------

def safe_int(val):
    """CSO VALUE cells can be NaN for suppressed/missing figures, or blank.
    float('nan') parses without error but int(nan) raises — and the older
    `int(x) or None` idiom used elsewhere in this file silently turns a
    genuine 0 into NULL, which is a real (if usually harmless) data bug.
    This returns None only for actually-missing values, and 0 stays 0."""
    try:
        f = float(str(val).strip())
        return None if f != f else int(f)  # f != f is the NaN check
    except (TypeError, ValueError):
        return None


def safe_float(val):
    try:
        f = float(str(val).strip())
        return None if f != f else f
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_table(table_id: str) -> pd.DataFrame:
    """Download a CSO PxStat table as a DataFrame."""
    url = f"{CSO_BASE}/{table_id}/CSV/1.0/en"
    print(f"  GET {url}")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{table_id}_{TODAY}.csv"
    raw_path.write_text(resp.text, encoding="utf-8")
    print(f"  Saved raw → {raw_path}")

    df = pd.read_csv(RAW_DIR / raw_path)
    print(f"  Rows: {len(df)}, Columns: {list(df.columns)}")
    return df


# ---------------------------------------------------------------------------
# Load to DuckDB
# ---------------------------------------------------------------------------

def load_health_graduates(df: pd.DataFrame, table_id: str, conn):
    """
    Load HGO07 into fact_health_graduates. National-level only (Decision
    E004) — institution_id is always NULL; HGO07 has no institution column
    to read one from.
    Column names are inferred from the actual CSV — adjust mapping if CSO changes headers.

    HGO07 has TWO dimensions this loader must handle carefully or every row
    gets multiplied:
      Nationality:   'All Irish', 'Non-Irish', 'All nationalities' (a total)
      PPSN Validity: 'PPSN - All', 'PPSN - Available', 'PPSN - Missing'
    'PPSN - Available'/'PPSN - Missing' further split each Nationality x
    Gender cell — we don't need that split, so only 'PPSN - All' rows are
    loaded (dropping the other two prevents inserting 3x too many rows, a
    real bug found and fixed 2026-08-19 — every (year, gender) cell was
    getting 9 rows instead of the intended few). Nationality itself has NO
    EU/Non-EU split — 'Non-Irish' is everyone who isn't Irish, undifferentiated.

    KNOWN LIMITATION — RCSI exclusion cannot be applied here: the CSO
    background note says RCSI's medicine graduate data for 2012-2016 has
    PPSN validation issues (RCSI_EXCLUSION above), but HGO07 has no
    institution column to identify which rows are RCSI's, so there is no
    way to flag or exclude them at the row level against this table. RCSI's
    numbers for those years are baked into the national Medicine total
    unflagged. Treat any national Medicine graduate_count for 2012-2016 as
    carrying that caveat until a per-institution source is found.
    """
    # Normalise column names (CSO uses title-case with spaces)
    df.columns = [c.strip() for c in df.columns]

    # Identify likely column names (CSO headers vary slightly between tables)
    col_map = {
        "field":            next((c for c in df.columns if "field" in c.lower()), None),
        "gender":           next((c for c in df.columns if "gender" in c.lower() or "sex" in c.lower()), None),
        "nationality":      next((c for c in df.columns if "nationality" in c.lower()), None),
        "ppsn":             next((c for c in df.columns if "ppsn" in c.lower()), None),
        "year":             next((c for c in df.columns if "year" in c.lower()), None),
        "value":            next((c for c in df.columns if c.lower() in ("value", "statistic", "graduates")), None),
    }
    print(f"  Column mapping: {col_map}")
    if table_id == RCSI_EXCLUSION["table"]:
        print(f"  ⚠ {table_id} has no institution column — RCSI 2012-2016 exclusion "
              f"cannot be applied at row level (see function docstring)")

    if col_map["ppsn"]:
        before = len(df)
        df = df[df[col_map["ppsn"]] == "PPSN - All"]
        print(f"  Filtered to PPSN Validity == 'PPSN - All': {before} -> {len(df)} rows "
              f"(dropping the PPSN-Available/PPSN-Missing split we don't need)")

    rows_loaded = 0

    for _, row in df.iterrows():
        field = str(row.get(col_map["field"], "")).strip()
        gender = str(row.get(col_map["gender"], "")).strip() if col_map["gender"] else None
        nationality = str(row.get(col_map["nationality"], "")).strip() if col_map["nationality"] else None
        year_raw = str(row.get(col_map["year"], "")).strip()
        year = int(year_raw) if year_raw.isdigit() else None
        value_raw = str(row.get(col_map["value"], "")).strip()
        count = int(float(value_raw)) if value_raw.replace(".", "").isdigit() else None

        conn.execute("""
            INSERT INTO fact_health_graduates
                (institution_id, graduation_year, field_of_study, gender, nationality,
                 graduate_count, data_excluded, exclusion_reason, source_table, load_date)
            VALUES (NULL, ?, ?, ?, ?, ?, FALSE, NULL, ?, current_date)
        """, [year, field, gender, nationality, count, table_id])
        rows_loaded += 1

    print(f"  Loaded {rows_loaded} rows (national-level, institution_id NULL — Decision E004)")


def load_graduate_outcomes(df: pd.DataFrame, table_id: str, conn):
    """
    Load HGO09 into fact_graduate_outcomes.
    Includes "Not Captured" rows — must never be relabelled as emigration
    (Decision E002): it means "not found in Irish employment or social
    insurance records", not confirmed emigration.

    HGO09 has no PPSN Validity / Nationality dimension (unlike HGO07), so
    there's no equivalent row-explosion risk here — every row is loaded.
    "All Graduate Outcomes" and "All genders" are real rows too (totals
    alongside their breakdowns) — consumers must filter those out rather
    than sum the whole table.
    """
    df.columns = [c.strip() for c in df.columns]

    col_map = {
        "field":            next((c for c in df.columns if "field" in c.lower()), None),
        "grad_year":        next((c for c in df.columns if "graduation" in c.lower() and "year" in c.lower()), None),
        "years_since":      next((c for c in df.columns if "years since" in c.lower() or "year after" in c.lower()), None),
        "outcome":          next((c for c in df.columns if "outcome" in c.lower() or "status" in c.lower()), None),
        "gender":           next((c for c in df.columns if "gender" in c.lower() or "sex" in c.lower()), None),
        "count":            next((c for c in df.columns if c.lower() in ("value", "count", "graduates")), None),
        "pct":              next((c for c in df.columns if "%" in c or "percent" in c.lower()), None),
    }
    print(f"  Column mapping: {col_map}")

    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO fact_graduate_outcomes
                (field_of_study, graduation_year, years_since_graduation,
                 outcome_category, gender, graduate_count, pct_of_cohort, source_table, load_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_date)
        """, [
            str(row.get(col_map["field"], "")).strip(),
            safe_int(row.get(col_map["grad_year"])),
            safe_int(row.get(col_map["years_since"])),
            str(row.get(col_map["outcome"], "")).strip(),
            str(row.get(col_map["gender"], "")).strip() if col_map["gender"] else None,
            safe_int(row.get(col_map["count"])),
            safe_float(row.get(col_map["pct"])) if col_map["pct"] else None,
            table_id,
        ])

    print(f"  Loaded {len(df)} rows")


def load_graduate_returns(df: pd.DataFrame, table_id: str, conn):
    """
    Load HGO11 into fact_graduate_returns.

    HGO11's "Years not captured" column holds text like '1 year', '13
    years', and 'All Years' (a total row) — not plain integers. 'All Years'
    rows are dropped (a derived aggregate across the 1-13 breakdown, same
    reasoning as dropping HEA's "TOTAL" rows) since years_since_return is
    NOT NULL and there's no meaningful integer to store for it anyway.
    """
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        "field":         next((c for c in df.columns if "field" in c.lower()), None),
        "grad_year":     next((c for c in df.columns if "graduation" in c.lower() and "year" in c.lower()), None),
        "years_return":  next((c for c in df.columns if "not captured" in c.lower() or "return" in c.lower()), None),
        "count":         next((c for c in df.columns if c.lower() in ("value", "count", "graduates")), None),
    }
    print(f"  Column mapping: {col_map}")

    def parse_years(val):
        """'1 year' -> 1, '13 years' -> 13, 'All Years' -> None (caller skips)."""
        m = re.match(r"^\s*(\d+)\s*years?\s*$", str(val), re.IGNORECASE)
        return int(m.group(1)) if m else None

    skipped_all_years = 0
    rows_loaded = 0

    for _, row in df.iterrows():
        years = parse_years(row.get(col_map["years_return"]))
        if years is None:
            skipped_all_years += 1
            continue
        conn.execute("""
            INSERT INTO fact_graduate_returns
                (field_of_study, graduation_year, years_since_return, returner_count, source_table, load_date)
            VALUES (?, ?, ?, ?, ?, current_date)
        """, [
            str(row.get(col_map["field"], "")).strip(),
            safe_int(row.get(col_map["grad_year"])),
            years,
            safe_int(row.get(col_map["count"])),
            table_id,
        ])
        rows_loaded += 1
    print(f"  Loaded {rows_loaded} rows ({skipped_all_years} 'All Years' row(s) dropped)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CSO HGO ETL")
    parser.add_argument("--tables", nargs="+", default=TABLES,
                        help="Which HGO tables to fetch (default: all)")
    parser.add_argument("--db", default="data/ireland_in_data.duckdb",
                        help="Path to DuckDB database file")
    parser.add_argument("--download-only", action="store_true",
                        help="Download CSVs but do not load into DuckDB")
    args = parser.parse_args()

    if not args.download_only:
        try:
            import duckdb
        except ImportError:
            print("ERROR: duckdb not installed. Run: pip install duckdb")
            sys.exit(1)
        conn = duckdb.connect(args.db)
        print(f"Connected to DuckDB: {args.db}")
    else:
        conn = None

    for table_id in args.tables:
        print(f"\n{'─'*60}")
        print(f"Table: {table_id}")
        try:
            df = download_table(table_id)
        except Exception as e:
            print(f"  ERROR downloading {table_id}: {e}")
            continue

        if conn and table_id == "HGO07":
            load_health_graduates(df, table_id, conn)
        elif conn and table_id == "HGO09":
            load_graduate_outcomes(df, table_id, conn)
        elif conn and table_id == "HGO11":
            load_graduate_returns(df, table_id, conn)
        else:
            if conn:
                print(f"  (No loader implemented for {table_id} — raw file saved only)")

    if conn:
        conn.close()

    print("\nAll done.")


if __name__ == "__main__":
    main()
