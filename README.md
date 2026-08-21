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
  graduate counts by gender and nationality, post-graduation outcome mix by
  years-since-graduation, and (from CSO's Census 2022-matched release,
  published 2025-11-14) public/private sector employment and occupation —
  from the CSO's Higher Education Outcomes (HGO) PxStat tables. Unlike HEA,
  CSO data *can* isolate Medicine specifically — but only at national level
  (Decision E004) and never combined with institution.
- **2022 is the current ceiling, not staleness in this pipeline.** CSO's
  most recent graduate-counts table (HGO07) was itself last updated
  2025-11-14 and still only covers graduation years 2010–2022 — that's the
  frontier of what CSO has published, confirmed against their own release
  notes, not a scrape running behind.

## Dashboards

`dashboard/education-dashboard.html` — a static, self-contained page with
8 charts across 5 sections (fees, who becomes a doctor, enrolments in
broader context, post-graduation outcomes, public sector & occupation).
Open it directly in a browser, or publish it wherever you publish Ireland
in Data artifacts. Chart data is inlined from the queries in this README's
history — re-run the queries below against a fresh `education.duckdb` and
update the inline arrays at the bottom of the file to refresh it.

`dashboard/hse-workforce-dashboard.html` — a second, separate static
dashboard covering seven years (2019/20–2025/26) of HSE's own annual
Medical Workforce Reports, plus a second source for one section. Sections
01-03 and 05 pair a current-year detail snapshot with a multi-year trend
chart, from HSE's own reports: consultant/NCHD/NTSD headcount growth;
the vacant consultant posts spike-then-fall-then-rise (179 → 445 → 309 →
324) alongside 2025's breakdown by how long each post's been vacant; NTSD
country of graduation since 2022 (Pakistan overtaking Ireland as the
largest single source, 34.2% vs 21.8% in 2025) alongside 2025's full,
unconsolidated country/region breakdown; and specialty-level vacancies
(top 12 for 2025, plus a 4-year trend for 3 specialties with notably
different trajectories). Section 04 switches source to the Medical
Council of Ireland's Medical Workforce Intelligence Reports, the only
place a country/qualification breakdown exists for Consultants and
training-scheme NCHDs, not just NTSDs — Irish-qualified share fell
2022-2024 in all three divisions, fastest among trainees (80.6% → 71.3%).
Section 06 covers official 1 Aug 2025 NCHD and Consultant pay scales, a
different HSE document again (none of the seven Medical Workforce Reports
carry pay figures). Not built from the DuckDB pipeline — none of these
are API/clean-CSV sources, so all of it was pulled by hand from PDFs (see
`data/raw/hse/SOURCES.md` and `data/raw/medical-council/SOURCES.md` for
the exact table/figure citation behind every number, including a real
cross-report Consultant Workforce revision pattern worth knowing about)
rather than scraped. Chart data is inlined the same way as the education
dashboard — update the arrays in the file directly to refresh.

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
  hse/                Seven years of HSE Medical Workforce Report PDFs + SOURCES.md citations
  medical-council/    Three years of Medical Council Workforce Intelligence Report PDFs + SOURCES.md citations
dashboard/
  education-dashboard.html      Static chart dashboard, see above
  hse-workforce-dashboard.html  HSE workforce dashboard, see above
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

# CSO graduate data — downloads + loads national-level counts/outcomes/sector/occupation
python etl/cso_hgo.py --tables HGO07 HGO09 HGO11 HGO14 HGO15 HGO16 --db data/education.duckdb
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

-- Public vs private sector employment, one cohort (closest available HSE proxy)
SELECT years_since_graduation, sector, graduate_count FROM fact_graduate_sector
WHERE field_of_study='Medicine' AND graduation_year=2018 AND sector != 'All sectors';

-- Share still working as Medical practitioners, Census 2022 snapshot, by cohort
SELECT graduation_year,
  SUM(CASE WHEN occupational_group='All occupational groups' THEN graduate_count END) AS total,
  SUM(CASE WHEN occupational_group='Medical practitioners' THEN graduate_count END) AS doctors
FROM fact_graduate_occupation WHERE field_of_study='Medicine'
GROUP BY graduation_year ORDER BY graduation_year;
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
- **HSE-specific employment still isn't in this data — "public sector" is
  the closest proxy, not a stand-in.** Neither CSO nor HEA publish
  employer-level data, so `fact_graduate_sector` (HGO14, added 2026-08-19)
  can only say "public sector," which for a Medicine graduate in Ireland
  overwhelmingly means the HSE system, but isn't verified as such. CSO's
  "Not Captured" outcome category (Decision E002) still means *not found
  in Irish employment or social insurance records* — explicitly not
  confirmed emigration. See Next steps below for the HSE annual reports
  lead, which might get genuinely employer-specific.
- **`fact_graduate_occupation` (HGO16) is a single Census 2022 snapshot,
  not a trajectory.** Each graduation-year cohort is observed at a
  different number of years post-graduation (whatever elapsed by Census
  night, 2022), and it only covers graduates who responded to Census 2022
  and were matched — a much smaller population than the full graduating
  cohort in `fact_health_graduates` (hundreds vs. the full 500-700+ per
  cohort). It answers "of those we can see, what do they do?", not "of
  everyone who graduated, what fraction still practise?" Don't join it to
  the other fact tables expecting matching denominators.
- **The HEA CSVs overlap, not add.** All four downloaded files cover the
  same national Health & Welfare population sliced by a different
  dimension (`medicine_institutions` also narrows institutions). Never
  `SUM(headcount)` across `source_file` values — always filter to one.
- **UCC's fee schedule URL only stays live for the current + next academic
  year.** `fee_scraper.py` falls back one year forward automatically when
  the requested year's page 404s, and flags the result as coming from a
  later year than requested.

## Next steps

- **HSE Medical Workforce Reports — done for 2019/20–2025/26, more
  possible.** See `dashboard/hse-workforce-dashboard.html`. Not yet done:
  the pre-2019 "Annual Assessment of NCHD Posts" years (2010–2018/19,
  NCHD-only, different report structure — would extend the NCHD-side
  trends further back but has no consultant/vacancy data to add); a
  *full* specialty-level vacancy trend (currently a 2025 snapshot for all
  ~40 specialties, plus a hand-picked 4-year trend for just 3 of them —
  every year has an equivalent full table, not yet reconciled across
  years for the other ~37). This still doesn't answer "how many doctors
  work for the HSE specifically by nationality" — NTSD country-of-
  graduation is the closest HSE gets, and it's a subset of NCHDs, not the
  full workforce.
- **HGO17 (Graduate Regions of Employment)** — same Census 2022-matched
  release as HGO14/16, dimension is literally "HSE Health Regions" (which
  of 6 regions graduates work in). Checked its structure but not
  downloaded, loaded, or charted — lower priority than sector/occupation,
  would need its own fact table following the HGO16 pattern.
- **HGO13 (Graduate NACE Sector of Employment)** — industry classification,
  same release, not investigated in detail.
- **HEA institution/gender/domicile combined cuts** — the current HEA
  downloads only ever break down by one dimension at a time (Row Variable
  is single-select in their dashboard). A combined view (e.g. domicile x
  institution) would need a different Shiny interaction, not just a new
  download.
