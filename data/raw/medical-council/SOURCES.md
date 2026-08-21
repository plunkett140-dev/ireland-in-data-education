# Medical Council of Ireland — Medical Workforce Intelligence Report sources

Three consecutive annual reports, used for Section 04 of the HSE workforce
dashboard ("Irish-qualified — consultants and trainees too, not just
NTSDs") — a different organisation and register from the HSE's own
Medical Workforce Reports in `../hse/`, used specifically because HSE
doesn't publish country/qualification data for Consultants or
training-scheme NCHDs, only for NTSDs (see `../hse/SOURCES.md`).

| File | Year covered | Published | Original URL |
|---|---|---|---|
| `medical-workforce-intelligence-report-2022.pdf` | 2022 | titled "2022 Medical Workforce Intelligence Consolidated Report" | https://www.medicalcouncil.ie/news-and-publications/reports/2022-medical-workforce-intelligence-consolidated-report.pdf |
| `medical-workforce-intelligence-report-2023.pdf` | 2023 | Aug 2024 | https://www.medicalcouncil.ie/news-and-publications/reports/medical-workforce-intelligence-report-2023.pdf |
| `medical-workforce-intelligence-report-2024.pdf` | 2024 | Aug 2025 | https://www.medicalcouncil.ie/news-and-publications/reports/medical-workforce-intelligence-report-2024.pdf |

No 2025 edition exists yet as of 2026-08-21 (checked directly on
medicalcouncil.ie and via search) — 2024 is the most recent available.

## Division by Basic Medical Qualification (BMQ) — exact citations

Doctors register in one of six divisions of the Medical Council's
Register depending on training completed/underway. The three relevant
here: **Specialist** (closest proxy to HSE hospital Consultants, but also
includes GPs and non-hospital specialists), **Trainee Specialist**
(closest proxy to HSE's training-scheme NCHDs), **General** (closest
proxy to HSE's NTSDs, but not identical — a genuinely different
population defined by a different organisation).

- **2022** — `medical-workforce-intelligence-report-2022.pdf`, "Figure 11.
  Division By BMQ" (p.21). This year only splits Irish BMQ vs.
  International BMQ (no separate EU/UK category). Trainee Specialist:
  2,481 Irish (80.6%) / 596 International (19.4%), n=3,077. General:
  2,135 Irish (36.4%) / 3,735 International (63.6%), n=5,870. Specialist:
  7,246 Irish (74.4%) / 2,494 International (25.6%), n=9,740.
- **2023** — `medical-workforce-intelligence-report-2023.pdf`, "Figure 4.
  Division by Qualification Category" (p.15). Three-way split (Irish / EU
  or UK / Outside Ireland-EU-UK). Trainee Specialist: 2,428 Irish (78.2%)
  / 321 EU-UK / 356 International, n=3,105. General: 2,164 Irish (34.0%)
  / 828 EU-UK / 3,377 International, n=6,369. Specialist: 7,116 Irish
  (73.4%) / 1,512 EU-UK / 1,072 International, n=9,700.
- **2024** — `medical-workforce-intelligence-report-2024.pdf`, "Figure 5.
  Division by Qualification Category" (p.16). Trainee Specialist: 2,729
  Irish (71.3%) / 386 EU-UK (10.1%) / 710 International (18.6%), n=3,825.
  General: 1,841 Irish (28.5%) / 823 EU-UK (12.8%) / 3,789 International
  (58.7%), n=6,453. Specialist: 7,660 Irish (72.7%) / 1,692 EU-UK (16.1%)
  / 1,187 International (11.3%), n=10,539.

Each report also gives a national "Top countries of international
graduates" breakdown (e.g. 2024: Pakistan 39.7%, Sudan 21.3%, South
Africa 10.4%, India 5.3%, Egypt 4.2% of international BMQ holders) — but
**not split by division**, so a named-country breakdown specifically for
Consultants or Trainee Specialists (the way Section 03 has one for NTSDs
from HSE's data) isn't obtainable from this source. Only the coarser
Irish / EU-or-UK / International split is available per division.

## Extraction method

Read via `pdftotext -layout` (each report's relevant figures render as
plain text/numbers alongside the chart, not embedded-image-only) — no
scraper script, one-off manual extraction like the HSE PDFs. Cross-check:
each year's three per-division totals sum to that division's published
headcount (e.g. 2024 Specialist: 7,660+1,692+1,187=10,539, matching the
report's own Division-of-Register total for Specialist).
