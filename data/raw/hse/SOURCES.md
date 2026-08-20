# HSE Medical Workforce Report data sources

Seven consecutive annual HSE National Doctors Training & Planning (NDTP)
"Medical Workforce Report" / "Medical Workforce Analysis Report" PDFs,
2019/20 through 2025/26 — the years where the report consistently covers
both NCHDs and Consultants (earlier reports, back to 2010, exist too but
are NCHD-only under the title "Annual Assessment of NCHD Posts" — see the
education pipeline README's Next steps for that longer, narrower series).

HSE's own site (hse.ie) was down site-wide when the first six of these
were pulled (2026-08-20); those six came via Wayback Machine snapshots.
The 2025-26 report was added the same day via its medicalcareers.ie
mirror (hse.ie was still down). Original canonical URLs, for whenever
hse.ie is back:

| File | Original URL |
|---|---|
| medical-workforce-report-2019-20.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/ed/rep/medical-workforce-report-2019-2020.pdf |
| medical-workforce-report-2020-21.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/ed/rep/medical-workforce-report-2020-21.pdf |
| medical-workforce-report-2021-22.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/ndtp-workforce-report-2021-2023.pdf (URL slug says "2021-2023" but the document itself is titled "Medical Workforce Report 2021-2022") |
| medical-workforce-report-2022-23.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/ndtp-medical-workforce-report-2023.pdf |
| medical-workforce-report-2023-24.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/medical-workforce-report-23-24-digital.pdf |
| medical-workforce-report-2024-25.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/medical-workforce-analysis-report-2024-2025.pdf |
| medical-workforce-report-2025-26.pdf | https://www.hse.ie/eng/staff/leadership-education-development/met/plan/ (exact 2025-26 slug not yet confirmed on hse.ie directly — pulled via https://www.medicalcareers.ie/wp-content/uploads/2026/04/Medical-Workforce-Report-2025-2026-FINAL-DIGITAL.pdf) |

## Important: Consultant Workforce figures get revised between report vintages

Each report carries its own multi-year retrospective "Overview" table
(Table 1 in most years). Comparing the SAME calendar year's Consultant
Workforce figure across different report vintages shows real,
unexplained-in-the-text revisions:

| Year | As reported in... | ...in the 2022-23 report | ...in 2023-24 | ...in 2024-25 | ...in 2025-26 |
|---|---|---|---|---|---|
| 2022 | | 3,814 | 3,782 | 3,782 | **3,814** |
| 2023 | | — | 4,255 | 4,255 | **4,289** |
| 2024 | | — | — | 4,620 | **4,698** |

This is not monotonic correction (2022 went 3,814 → 3,782 → back to
3,814) — it isn't simply "later is always more accurate." **This
dashboard uses each year's value from the most recent report available**
(i.e. the freshest restatement), on the reasoning that NDTP's own
retrospective tables are presumably their best current view of history,
even though the 2022 example shows that isn't a fully safe assumption
either. Treat the Consultant Workforce trend as directionally right and
approximately correct, not as precise to the individual digit.

**By contrast, Total Training NCHDs (incl. interns) and NTSD figures are
stable across every report vintage checked** — the 2021-2025 values in
the 2025-26 report's Table 1 match the 2024-25 report's Table 1 exactly
for every overlapping year. The revision issue is specific to the
Consultant Workforce count, not NCHD-side figures generally.

## Exact citations for every figure used in the dashboard

**Consultant Workforce, Training NCHDs (incl. interns), NTSDs — 2019-2025**
  - 2019: `medical-workforce-report-2023-24.pdf`, Table 1, page ~7 (earliest
    year available in any retrospective table; not covered by 2025-26's).
  - 2020: `medical-workforce-report-2024-25.pdf`, Table 1, page ~4 (not
    covered by 2025-26's table either).
  - 2021-2025: `medical-workforce-report-2025-26.pdf`, Table 1 ("Overview
    of NCHDs in Training and NTSDs and Consultants..."), page ~4 — the
    freshest available restatement for these years. See the revision note
    above for why 2022-2024 differ from what the dashboard showed before
    this report was added.

**Total Vacant Consultant Posts — 2019-2025**
Stated in prose/tables in each report's own "Vacant Posts" section:
  - 2019: `medical-workforce-report-2019-20.pdf` — "179 were marked as
    vacant" (~Sept 2019 DIME snapshot).
  - 2020: `medical-workforce-report-2020-21.pdf` — "221 were marked as
    vacant" (9th October 2020).
  - 2021: `medical-workforce-report-2021-22.pdf`, section 5.1.3 — "Three
    hundred and sixty posts were marked as vacant in October 2021".
  - 2022: `medical-workforce-report-2022-23.pdf`, section 5.1.3 — "Four
    hundred and forty four posts were marked as vacant in December 2022".
  - 2023: `medical-workforce-report-2023-24.pdf`, Table 14, Total row, 445.
  - 2024: `medical-workforce-report-2024-25.pdf`, Table 14, Total row, 309.
  - 2025: `medical-workforce-report-2025-26.pdf`, section 5.1.3 / Table 13
    — "There were 324 posts marked as vacant in December 2025, which
    equates to a 5% increase on the number of vacant posts at the same
    time last year" (309 → 324 checks out: 309 × 1.05 ≈ 324).

  **Caveat:** measurement date moves around (Sept → Oct → Oct → Dec → Dec
  → Dec → Dec) across these seven snapshots.

  **Vacant Posts by Duration, December 2025 snapshot** (dashboard's
  Section 2 "detail" chart): `medical-workforce-report-2025-26.pdf`, Table
  13 — Less than 6 Months: 182 (56%), 6-12 Months: 37 (11%), 12-18 Months:
  28 (9%), 18+ Months: 77 (24%), Total: 324.

**NTSD Country of Graduation — 2022-2025 only** (not published before 2022)
  - 2022: `medical-workforce-report-2022-23.pdf`, Figure 4.20 — Pakistan
    26%, Ireland 23%, Others 20%, Sudan 18%, Romania 6%, South Africa 5%,
    Egypt 3%.
  - 2023: `medical-workforce-report-2023-24.pdf`, Figure 23 — Pakistan
    30%, Other 21%, Ireland 20%, Sudan 18%, Romania 5%, South Africa 5%,
    Egypt 2%.
  - 2024: `medical-workforce-report-2024-25.pdf`, Figure 24 — Pakistan
    33.1%, Ireland 20.9%, Sudan 16.8%, Europe (other) 8.5%, Asia (other)
    7.2%, South Africa 5.5%, Romania 4.2%, Egypt 1.6%, Africa (other)
    1.5%, North America / Australia / South America 0.2% each.
  - 2025: `medical-workforce-report-2025-26.pdf`, section 4.9.3, Figure 30
    ("Country of Graduation of Non-Training Scheme Doctors in 2025") —
    Pakistan 34.2%, Ireland 21.8%, Sudan 16.0%, Europe (Excl. Ireland)
    12.2%, Africa 7.9%, Asia 7.5%, North America 0.2%, South America 0.1%,
    Australasia 0.1%. This year's report also states outright: "NTSDs who
    graduated in Ireland comprise almost 22% of these NCHDs. Therefore,
    78% of NTSDs graduated outside of Ireland which compares to 48% of
    NCHDs graduating outside of Ireland" — i.e. HSE's own report frames
    this exact comparison directly.

  Each year buckets minor countries differently (a flat "Others"/"Other"
  in 2022/2023, split into continent-level buckets from 2024 onward). The
  dashboard's trend chart consolidates all four years to four consistent
  categories — Pakistan, Ireland, Sudan, Other (everything else summed);
  the dashboard's "detail" chart shows 2025's full, unconsolidated
  country/continent breakdown exactly as published.

**Filled and Vacant Approved Posts by Specialty — snapshot (Dec 2025) plus
a 4-year trend (2022-2025) for the specialties with the largest current
vacancies or most notable trend**
  - 2022: `medical-workforce-report-2022-23.pdf`, Table 5.5.
  - 2023: `medical-workforce-report-2023-24.pdf`, Table 15.
  - 2024: `medical-workforce-report-2024-25.pdf`, Table 15.
  - 2025: `medical-workforce-report-2025-26.pdf`, Table 14 (full ~40
    specialty table; the dashboard's "detail" chart shows the top 12 by
    vacant count).

  Trend series pulled from all four years above for: Radiology (41, 43,
  36, 30), Psychiatry (40, 31, 25, 34 — "Psychiatry" 2022/2024/2025 vs.
  "General Adult Psychiatry" 2023, same underlying specialty, HSE renamed
  the row), Emergency Medicine (50, 36, 16, 15). Not extracted for every
  specialty in every year — a full multi-year specialty grid across all
  ~40 specialties would need all four tables fully reconciled, not just
  these three rows; see Next steps.

## Next steps not done in this pass

- Full multi-year specialty-level vacancy grid (all ~40 specialties, not
  just the 3 charted) — would need each year's full table reconciled the
  same way the 3 charted specialties were.
- Pre-2019 NCHD-only data (2010-2018/19) — different report title/scope,
  see the main README.
- No automated re-scraper was built for this — HSE's PDF structure and
  section/table numbering shifts enough year to year (new sections added,
  tables renumbered, even column labels changing e.g. "Psychiatry" vs.
  "General Adult Psychiatry") that hand-verifying each year's citation, as
  done here, was more reliable than a brittle parser. Re-running this next
  year means repeating this citation-finding process against the new PDF
  (there should be a 2026-27 report in ~12 months), not running a script.
