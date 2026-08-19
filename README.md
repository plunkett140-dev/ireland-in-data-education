# Ireland in Data — Education

The Ireland in Data education pipeline: who trains to be a doctor in
Ireland, what it costs, and where they go afterwards. Tracks Graduate
Entry Medicine (GEM) fees, HEA student enrolments, and CSO graduate
outcomes for Irish medical education.

## What this tracks

- **GEM fees** — annual programme fees for Graduate Entry Medicine at UCD,
  UCC, UL, and RCSI, scraped from each institution's official fee schedule.
- **HEA enrolments** — Health & Welfare field enrolment snapshots from the
  Higher Education Authority's public Shiny dashboard, broken down by
  Programme Type, Domicile Group (Ireland / EU / Non-EU / GB / NI /
  Unknown), and Gender. HEA can't isolate Medicine specifically — its
  narrowest field-of-study filter is "Health and welfare" (nursing,
  pharmacy, dentistry etc. included).
- **CSO graduate data** — national-level Medicine (and other health field)
  graduate counts by gender and nationality, plus post-graduation outcome
  mix by years-since-graduation, from the CSO's Higher Education Outcomes
  (HGO) PxStat tables. Unlike HEA, CSO data *can* isolate Medicine
  specifically — but only at national level (Decision E004) and only with
  gender/nationality, never combined institution-level.

## Dashboard

`dashboard/education-dashboard.html` — a static, self-contained page with
6 charts across 4 sections (fees, who becomes a doctor, enrolments in
broader context, post-graduation outcomes). Open it directly in a browser,
or publish it wherever you publish Ireland in Data artifacts. Chart data is
inlined from the queries in this README's history — re-run the queries
below against a fresh `education.duckdb` and update the inline arrays at
the bottom of the file to refresh it.

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
  hea/                Raw HEA enrolment CSV snapshots (programme type, domicile, gender)
  cso/                Raw CSO HGO CSV snapshots
dashboard/
  education-dashboard.html   Static chart dashboard, see above
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

# HEA enrolments — downloads 4 dated CSV snapshots to data/raw/hea/, then load them
python etl/hea_enrolments.py
python etl/hea_csv_loader.py --inspect                              # safe, no writes
python etl/hea_csv_loader.py --load --db data/education.duckdb

# CSO graduate data — downloads + loads national-level counts/outcomes
python etl/cso_hgo.py --tables HGO07 HGO09 HGO11 HGO15 --db data/education.duckdb
```

Useful queries once loaded (see `dashboard/education-dashboard.html` for
the full set that feeds every chart):

```sql
-- Medicine graduates by gender, national
SELECT graduation_year, gender, graduate_count FROM fact_health_graduates
WHERE field_of_study='Medicine' AND gender IN ('Male','Female')
  AND nationality='All nationalities';

-- Medicine graduates by nationality (Irish vs Non-Irish only — no EU/Non-EU split)
SELECT graduation_year, nationality, graduate_count FROM fact_health_graduates
WHERE field_of_study='Medicine' AND nationality IN ('All Irish','Non-Irish')
  AND gender='All genders';

-- Post-graduation outcome mix by years since graduation, one cohort
SELECT years_since_graduation, outcome_category, graduate_count
FROM fact_graduate_outcomes
WHERE field_of_study='Medicine' AND graduation_year=2018 AND gender='All genders'
  AND outcome_category != 'All Graduate Outcomes';
```

## Known issues

- **`fact_health_graduates` and `fact_graduate_outcomes` are national-level
  by design (Decision E004, 2026-08-19).** No CSO HGO table has an
  institution dimension. `institution_id` is always `NULL` for CSO-sourced
  rows; this is intentional. See the decision log at the top of
  `schema/create_education_schema.sql`. One consequence: the documented
  RCSI PPSN-validation exclusion for 2012-2016 graduates can't be applied
  at the row level either — treat national Medicine totals for those years
  as carrying that caveat unflagged.
- **Nationality/domicile granularity differs by source and doesn't match.**
  CSO's HGO07 only splits Irish vs Non-Irish (graduates). HEA's Domicile
  Group gives a real Ireland/EU/Non-EU/GB/NI/Unknown split (enrolments,
  Health & Welfare broadly — not Medicine). Neither can be combined with
  the other, and `fact_graduate_outcomes` (HGO09) has no nationality
  dimension at all — outcome-by-nationality isn't obtainable from CSO.
- **HSE-specific employment isn't in this data at all.** CSO's "Not
  Captured" outcome category (Decision E002) means *not found in Irish
  employment or social insurance records* — it is explicitly not confirmed
  emigration, and neither CSO nor HEA publish employer-level data. Nothing
  in this pipeline can currently say how many graduates work for the HSE
  specifically. See Next steps below.
- **The HEA CSVs overlap, not add.** All four downloaded files cover the
  same national Health & Welfare population sliced by a different
  dimension (`medicine_institutions` also narrows institutions). Never
  `SUM(headcount)` across `source_file` values — always filter to one.
- **UCC's fee schedule URL only stays live for the current + next academic
  year.** `fee_scraper.py` falls back one year forward automatically when
  the requested year's page 404s, and flags the result as coming from a
  later year than requested.

## Next steps

- **HSE annual reports** may publish employment figures for doctors and
  nurses by specialty and level of training, plus open-post data — and
  possibly nationality of hires. Worth checking whether that can fill the
  "HSE-specific employment" gap above; not yet investigated or scraped.
- **HEA institution/gender/domicile combined cuts** — the current HEA
  downloads only ever break down by one dimension at a time (Row Variable
  is single-select in their dashboard). A combined view (e.g. domicile x
  institution) would need a different Shiny interaction, not just a new
  download.
