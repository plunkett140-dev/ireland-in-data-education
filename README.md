# Ireland in Data — Education

The Ireland in Data education pipeline: tracking Graduate Entry Medicine
(GEM) fees, HEA student enrolments, and CSO graduate outcomes for Irish
medical education.

## What this tracks

- **GEM fees** — annual programme fees for Graduate Entry Medicine at UCD,
  UCC, UL, and RCSI, scraped from each institution's official fee schedule.
- **HEA enrolments** — student enrolment snapshots from the Higher Education
  Authority's public Shiny dashboard, filtered to Health and Welfare /
  medicine-related institutions.
- **CSO graduate outcomes** — national-level health graduate counts and
  post-graduation outcomes from the CSO's Higher Education Outcomes (HGO)
  PxStat tables (Decision E004 — see Known issues).

## Structure

```
etl/
  fee_scraper.py      GEM fee scraper (UCD, UCC, UL, RCSI) — dry-run by default
  hea_enrolments.py   HEA Shiny dashboard scraper (Playwright), downloads raw CSVs
  hea_csv_loader.py   Transforms those raw CSVs into fact_student_enrolments
  cso_hgo.py          CSO PxStat HGO table downloader/loader
schema/
  create_education_schema.sql   DuckDB schema: dim_institution + fact tables
data/raw/
  hea/                Raw HEA enrolment CSV snapshots
  cso/                Raw CSO HGO CSV snapshots
```

## Setup

```bash
pip install requests beautifulsoup4 duckdb pandas playwright
playwright install chromium

python -c "import duckdb; duckdb.connect('data/education.duckdb').execute(open('schema/create_education_schema.sql').read())"
```

## Running

```bash
# GEM fees — dry-run, prints a diff against the DB; add --write to commit
python etl/fee_scraper.py --year 2025/26 --db data/education.duckdb

# HEA enrolments — downloads dated CSV snapshots to data/raw/hea/, then load them
python etl/hea_enrolments.py
python etl/hea_csv_loader.py --inspect                              # safe, no writes
python etl/hea_csv_loader.py --load --db data/education.duckdb

# CSO graduate outcomes — downloads + loads national-level counts/outcomes
python etl/cso_hgo.py --tables HGO07 HGO09 HGO11 HGO15 --db data/education.duckdb
```

## Known issues

- **`fact_health_graduates` is national-level by design (Decision E004,
  2026-08-19).** CSO's HGO07 table (the source for health graduate counts)
  has no institution dimension at all — only Graduation Year, Nationality,
  PPSN Validity, Gender, and Field of Study — and no other HGO table adds
  one. `institution_id` is always `NULL` for CSO-sourced rows; this is
  intentional, not a bug. See the decision log at the top of
  `schema/create_education_schema.sql` before revisiting it. One consequence:
  the documented RCSI PPSN-validation exclusion for 2012-2016 graduates
  can't be applied at the row level either, since there's no institution
  column to match RCSI against — treat national Medicine totals for those
  years as carrying that caveat unflagged.
- **`hea_csv_loader.py` can only populate what the downloaded CSVs contain**
  — `programme_type`, `academic_year`, `headcount`, and a hardcoded
  `isced_label` of "Health and welfare". There is no Institution, Gender, or
  Domicile column in either downloaded file, so those columns stay `NULL`.
  Getting that finer breakdown would mean changing `hea_enrolments.py`'s
  Shiny filter/grouping settings before download, not just the loader.
- **The two HEA CSVs overlap, not add.** `hea_enrolments_health_welfare_*`
  is every Health & Welfare student; `hea_enrolments_medicine_institutions_*`
  is the subset of those already-counted students at the six medicine-
  granting institutions. Both get loaded (`source_file` distinguishes them),
  but summing `headcount` across both source files double-counts every
  medicine-institution student — always filter `WHERE source_file = ...`.
- **UCC's fee schedule URL only stays live for the current + next academic
  year.** `fee_scraper.py` falls back one year forward automatically when
  the requested year's page 404s, and flags the result as coming from a
  later year than requested.
