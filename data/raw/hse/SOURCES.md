# HSE Medical Workforce Report data sources

Six consecutive annual HSE National Doctors Training & Planning (NDTP)
"Medical Workforce Report" / "Medical Workforce Analysis Report" PDFs,
2019/20 through 2024/25 — the years where the report consistently covers
both NCHDs and Consultants (earlier reports, back to 2010, exist too but
are NCHD-only under the title "Annual Assessment of NCHD Posts" — see the
education pipeline README's Next steps for that longer, narrower series).

HSE's own site (hse.ie) was down site-wide when this was pulled
(2026-08-20) — every PDF here came via a Wayback Machine snapshot instead.
Original canonical URLs, for whenever hse.ie is back:

| File | Original URL |
|---|---|
| medical-workforce-report-2019-20.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/ed/rep/medical-workforce-report-2019-2020.pdf |
| medical-workforce-report-2020-21.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/ed/rep/medical-workforce-report-2020-21.pdf |
| medical-workforce-report-2021-22.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/ndtp-workforce-report-2021-2023.pdf (URL slug says "2021-2023" but the document itself is titled "Medical Workforce Report 2021-2022") |
| medical-workforce-report-2022-23.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/ndtp-medical-workforce-report-2023.pdf |
| medical-workforce-report-2023-24.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/medical-workforce-report-23-24-digital.pdf |
| medical-workforce-report-2024-25.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/medical-workforce-analysis-report-2024-2025.pdf |

A newer 2025/26 report has also been published (found via medicalcareers.ie
mirror) but wasn't pulled in for this round — see Next steps.

## Exact citations for every figure used in the dashboard

**Consultant Workforce, Training NCHDs (incl. interns), NTSDs — 2019-2024**
Each report carries its own 5-year retrospective "Overview" table (Table 1
in 2023-24/2024-25, Table 1.1 in 2021-22/2022-23), each internally
consistent within that report. To get the freshest-available restatement
of each year:
  - 2019 values: `medical-workforce-report-2023-24.pdf`, Table 1 ("Overview
    of Consultants and NCHDs..."), page ~7.
  - 2020-2024 values: `medical-workforce-report-2024-25.pdf`, Table 1
    ("Overview of NCHDs in Training and NTSDs and Consultants..."), page ~4.

  **Known data revision, not a transcription error:** 2022's Consultant
  Workforce is reported as 3,814 in the 2022-23 report's own Table 1.1, but
  restated as 3,782 in both the 2023-24 and 2024-25 reports' retrospective
  tables. The dashboard uses the later, twice-confirmed 3,782 figure.
  2022-23's own footnote also flags a measurement-date change ("Consultant
  and NTSD data as at December for each year, previous report reported
  October data") which likely explains some of the cross-vintage drift
  visible if you compare raw report tables directly.

**Total Vacant Consultant Posts — 2019-2024**
Stated in prose in each report's own "Vacant Posts" section (section
5.1.3 from 2021-22 onward; described differently in 2019-20/2020-21, which
predate a dedicated Vacant Posts section):
  - 2019: `medical-workforce-report-2019-20.pdf` — "179 were marked as
    vacant" as of the report's DIME snapshot date (~Sept 2019).
  - 2020: `medical-workforce-report-2020-21.pdf` — "221 were marked as
    vacant" (9th October 2020 DIME snapshot).
  - 2021: `medical-workforce-report-2021-22.pdf`, section 5.1.3 — "Three
    hundred and sixty posts were marked as vacant in October 2021".
  - 2022: `medical-workforce-report-2022-23.pdf`, section 5.1.3 — "Four
    hundred and forty four posts were marked as vacant in December 2022".
  - 2023: `medical-workforce-report-2023-24.pdf`, Table 14 ("Vacant Posts
    December 2023 by Duration Vacant") — Total row, 445.
  - 2024: `medical-workforce-report-2024-25.pdf`, Table 14 — Total row,
    309 ("a 31% decline on the number of vacant posts at the same time
    last year").

  **Caveat:** the measurement date moves around (Sept → Oct → Oct → Dec →
  Dec → Dec) across these six snapshots — not a clean same-day-of-year
  comparison, though close enough for a year-over-year trend to be
  meaningful.

**NTSD Country of Graduation — 2022-2024 only** (not published before 2022)
  - 2022: `medical-workforce-report-2022-23.pdf`, Figure 4.20 ("Country of
    Graduation of NTSDs") — Pakistan 26%, Ireland 23%, Others 20%, Sudan
    18%, Romania 6%, South Africa 5%, Egypt 3%.
  - 2023: `medical-workforce-report-2023-24.pdf`, Figure 23 ("Country of
    Graduation of Non-Training Scheme Doctors in 2023") — Pakistan 30%,
    Other 21%, Ireland 20%, Sudan 18%, Romania 5%, South Africa 5%, Egypt
    2%.
  - 2024: `medical-workforce-report-2024-25.pdf`, Figure 24 ("Country of
    Graduation of Non-Training Scheme Doctors in 2024") — Pakistan 33.1%,
    Ireland 20.9%, Sudan 16.8%, Europe (other) 8.5%, Asia (other) 7.2%,
    South Africa 5.5%, Romania 4.2%, Egypt 1.6%, Africa (other) 1.5%, North
    America / Australia / South America 0.2% each.

  Each year buckets minor countries differently (a flat "Others"/"Other"
  in 2022/2023, split into continent-level buckets in 2024). The dashboard
  consolidates all three years to the same four categories — Pakistan,
  Ireland, Sudan, Other (everything else summed) — for a clean trend;
  the exact minor-country breakdown for 2024 is preserved in this file
  since it's more granular than what the chart shows.

**Filled and Vacant Approved Posts by Specialty — 2024 only (single
snapshot, not a trend)**
  - `medical-workforce-report-2024-25.pdf`, Table 15 ("Filled and Vacant
    Approved Posts by Specialty as of December 2024"). Full ~40-specialty
    breakdown; the dashboard shows the top specialties by vacant count.
    Equivalent tables exist in 2022-23 (Table 4.9-ish) and 2023-24
    (Table 15) and could extend this to a multi-year specialty view — not
    done in this pass, see Next steps.

## Next steps not done in this pass

- Specialty-level vacancy trend (not just the 2024 snapshot) — would need
  each year's equivalent specialty table extracted and reconciled the same
  way the headline totals were.
- Pre-2019 NCHD-only data (2010-2018/19) — different report title/scope,
  see the main README.
- The 2025/26 report, published after this data pull.
- No automated re-scraper was built for this — HSE's PDF structure and
  section numbering shifts enough year to year (new sections added,
  tables renumbered) that hand-verifying each year's citation, as done
  here, was more reliable than a brittle parser. Re-running this next year
  means repeating this citation-finding process against the new PDF, not
  running a script.
