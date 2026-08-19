"""
cso_hgo.py
==========
Ireland in Data — CSO Health Graduate Outcomes ETL
Downloads HGO tables from the CSO PxStat REST API and saves dated CSV snapshots.

Tables collected:
  HGO07  Health graduates by institution and field of study (counts)
  HGO08  Health graduates by institution, field and gender
  HGO09  Graduate outcomes at 1,2,3,4,5 years post-graduation ("Not Captured" proxy)
  HGO11  Graduate returns to Ireland
  HGO15  Graduate earnings (if available)
  HGO16  Graduate earnings by gender

Endpoint pattern (confirmed, public, no auth required):
  https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{TABLE}/CSV/1.0/en

NOTE: This endpoint is blocked from the Anthropic cloud sandbox (HTTP 403).
Run this script locally or in GitHub Actions.

Decision E002: The "Not Captured" outcome in HGO09 is NOT confirmed emigration.
CSO background notes state it means graduates not found in Irish employment or
social insurance records. Always label as "not captured in Irish employment records".

Decision (RCSI exclusion): HGO08 RCSI medicine graduates 2012–2016 must be loaded
with data_excluded=True due to PPSN validation issues (documented in CSO background notes).

Run:
  pip install requests pandas duckdb
  python cso_hgo.py [--tables HGO08 HGO09] [--db path/to/ireland_in_data.duckdb]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CSO_BASE = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset"
TABLES = ["HGO07", "HGO08", "HGO09", "HGO11", "HGO15", "HGO16"]
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "cso"
TODAY = date.today().isoformat()

# CSO institution name → our institution_id
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

# RCSI data exclusion: HGO08, graduation years 2012–2016
# Source: CSO background note on PPSN validation issues
RCSI_EXCLUSION = {
    "table": "HGO08",
    "institution": "RCSI",
    "years": list(range(2012, 2017)),
    "reason": "RCSI PPSN validation issues 2012-2016 (CSO HGO08 background note)"
}


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
    Load HGO07 / HGO08 into fact_health_graduates.
    Column names are inferred from the actual CSV — adjust mapping if CSO changes headers.
    """
    # Normalise column names (CSO uses title-case with spaces)
    df.columns = [c.strip() for c in df.columns]

    # Identify likely column names (CSO headers vary slightly between tables)
    col_map = {
        "institution":      next((c for c in df.columns if "institution" in c.lower()), None),
        "field":            next((c for c in df.columns if "field" in c.lower()), None),
        "gender":           next((c for c in df.columns if "gender" in c.lower() or "sex" in c.lower()), None),
        "year":             next((c for c in df.columns if "year" in c.lower()), None),
        "value":            next((c for c in df.columns if c.lower() in ("value", "statistic", "graduates")), None),
    }
    print(f"  Column mapping: {col_map}")

    rows_loaded = 0
    rows_excluded = 0

    for _, row in df.iterrows():
        raw_inst = str(row.get(col_map["institution"], "")).strip()
        institution_id = INSTITUTION_MAP.get(raw_inst)
        field = str(row.get(col_map["field"], "")).strip()
        gender = str(row.get(col_map["gender"], "")).strip() if col_map["gender"] else None
        year_raw = str(row.get(col_map["year"], "")).strip()
        year = int(year_raw) if year_raw.isdigit() else None
        value_raw = str(row.get(col_map["value"], "")).strip()
        count = int(float(value_raw)) if value_raw.replace(".", "").isdigit() else None

        # Check RCSI exclusion
        excluded = False
        excl_reason = None
        if (table_id == RCSI_EXCLUSION["table"]
                and raw_inst == "Royal College of Surgeons in Ireland"
                and year in RCSI_EXCLUSION["years"]):
            excluded = True
            excl_reason = RCSI_EXCLUSION["reason"]
            rows_excluded += 1

        conn.execute("""
            INSERT INTO fact_health_graduates
                (institution_id, graduation_year, field_of_study, gender,
                 graduate_count, data_excluded, exclusion_reason, source_table, load_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_date)
        """, [institution_id, year, field, gender, count, excluded, excl_reason, table_id])
        rows_loaded += 1

    print(f"  Loaded {rows_loaded} rows ({rows_excluded} excluded/flagged)")


def load_graduate_outcomes(df: pd.DataFrame, table_id: str, conn):
    """
    Load HGO09 into fact_graduate_outcomes.
    Includes "Not Captured" rows — must never be relabelled as emigration.
    """
    df.columns = [c.strip() for c in df.columns]

    col_map = {
        "field":            next((c for c in df.columns if "field" in c.lower()), None),
        "grad_year":        next((c for c in df.columns if "graduation" in c.lower() and "year" in c.lower()), None),
        "years_since":      next((c for c in df.columns if "years since" in c.lower() or "year after" in c.lower()), None),
        "outcome":          next((c for c in df.columns if "outcome" in c.lower() or "status" in c.lower()), None),
        "count":            next((c for c in df.columns if c.lower() in ("value", "count", "graduates")), None),
        "pct":              next((c for c in df.columns if "%" in c or "percent" in c.lower()), None),
    }
    print(f"  Column mapping: {col_map}")

    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO fact_graduate_outcomes
                (field_of_study, graduation_year, years_since_graduation,
                 outcome_category, graduate_count, pct_of_cohort, source_table, load_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, current_date)
        """, [
            str(row.get(col_map["field"], "")).strip(),
            int(str(row.get(col_map["grad_year"], 0)).strip() or 0) or None,
            int(str(row.get(col_map["years_since"], 0)).strip() or 0) or None,
            str(row.get(col_map["outcome"], "")).strip(),
            int(float(str(row.get(col_map["count"], "")).strip() or 0)) or None,
            float(str(row.get(col_map["pct"], "")).strip() or 0) or None,
            table_id,
        ])

    print(f"  Loaded {len(df)} rows")


def load_graduate_returns(df: pd.DataFrame, table_id: str, conn):
    """Load HGO11 into fact_graduate_returns."""
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        "field":         next((c for c in df.columns if "field" in c.lower()), None),
        "grad_year":     next((c for c in df.columns if "graduation" in c.lower() and "year" in c.lower()), None),
        "years_return":  next((c for c in df.columns if "return" in c.lower()), None),
        "count":         next((c for c in df.columns if c.lower() in ("value", "count", "graduates")), None),
    }

    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO fact_graduate_returns
                (field_of_study, graduation_year, years_since_return, returner_count, source_table, load_date)
            VALUES (?, ?, ?, ?, ?, current_date)
        """, [
            str(row.get(col_map["field"], "")).strip(),
            int(str(row.get(col_map["grad_year"], 0)).strip() or 0) or None,
            int(str(row.get(col_map["years_return"], 0)).strip() or 0) or None,
            int(float(str(row.get(col_map["count"], "")).strip() or 0)) or None,
            table_id,
        ])
    print(f"  Loaded {len(df)} rows")


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

        if conn and table_id in ("HGO07", "HGO08"):
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
