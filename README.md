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
- **CSO graduate outcomes** — health graduate counts and post-graduation
  outcomes from the CSO's Higher Education Outcomes (HGO) PxStat tables.

## Structure

```
etl/
  fee_scraper.py      GEM fee scraper (UCD, UCC, UL, RCSI) — dry-run by default
  hea_enrolments.py   HEA Shiny dashboard scraper (Playwright)
  cso_hgo.py          CSO PxStat HGO table downloader/loader — WIP, see below
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

# HEA enrolments — downloads dated CSV snapshots to data/raw/hea/
python etl/hea_enrolments.py
python etl/hea_enrolments.py --validate

# CSO graduate outcomes — see WIP note below before running a full load
python etl/cso_hgo.py --tables HGO09 HGO11 HGO15 --download-only
```

## Known issues

- **`cso_hgo.py` is WIP.** The CSO's HGO07 table (intended source for
  per-institution health graduate counts) has no institution dimension at
  all — its only fields are Graduation Year, Nationality, PPSN Validity,
  Gender, and Field of Study. Loading it as-is silently writes
  `institution_id = NULL` for every row in `fact_health_graduates`, which
  defeats the point of that table. Do not run the full `--tables` load
  against a real database until this is resolved — a different CSO table,
  or a different data source entirely, may be needed for institution-level
  breakdowns. `HGO08` (also referenced in earlier drafts) does not exist in
  CSO's PxStat catalog at all.
- **No loader yet for HEA enrolments.** `hea_enrolments.py` only downloads
  and validates raw CSV snapshots; nothing currently parses them into
  `fact_student_enrolments`. The Shiny dashboard's default download is also
  an aggregated pivot (Programme Type × academic year), not the granular
  per-institution/gender/domicile breakdown that table's schema expects —
  the download filters will need adjusting before a loader can be written.
- **UCC's fee schedule URL only stays live for the current + next academic
  year.** `fee_scraper.py` falls back one year forward automatically when
  the requested year's page 404s, and flags the result as coming from a
  later year than requested.
