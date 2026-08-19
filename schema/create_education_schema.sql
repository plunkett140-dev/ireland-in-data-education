-- create_education_schema.sql
-- Ireland in Data — Education & Workforce Data Warehouse
-- Initialise DuckDB tables for the education pipeline.
-- Run once: python -c "import duckdb; duckdb.connect('data/ireland_in_data.duckdb').execute(open('etl/education/create_education_schema.sql').read())"
--
-- Decision log:
--   E001: HEA data may not distinguish UG from GEM within "Health and welfare".
--         Inspect Programme Type column after first download.
--   E002: CSO "Not Captured" ≠ emigration. Always label precisely.
--   E003: UCD GEM fee €18,800/year — student-verified ground truth (2025/26).
--         All other institutions marked unverified until confirmed from primary source.

-- ─────────────────────────────────────────────────────────────────────────────
-- Dimension: Institutions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_institution (
    institution_id        VARCHAR PRIMARY KEY,   -- e.g. 'UCD', 'UCC', 'TCD'
    hea_name              VARCHAR NOT NULL,       -- name as it appears in HEA downloads
    cso_name              VARCHAR,               -- name as it appears in CSO tables (NULL if not in CSO)
    city                  VARCHAR,
    type                  VARCHAR,               -- 'university', 'iot', 'other'
    offers_medicine_ug    BOOLEAN DEFAULT FALSE,
    offers_medicine_gem   BOOLEAN DEFAULT FALSE
);

INSERT OR IGNORE INTO dim_institution VALUES
    ('UCD',       'University College Dublin',               'UCD',                     'Dublin',  'university', TRUE,  TRUE),
    ('UCC',       'University College Cork',                 'UCC',                     'Cork',    'university', TRUE,  TRUE),
    ('TCD',       'Trinity College Dublin',                  'TCD',                     'Dublin',  'university', TRUE,  TRUE),
    ('NUIG',      'University of Galway',                    'University of Galway',    'Galway',  'university', TRUE,  FALSE),
    ('UL',        'University of Limerick',                  'UL',                      'Limerick','university', TRUE,  FALSE),
    ('RCSI',      'Royal College of Surgeons in Ireland',    'RCSI',                    'Dublin',  'university', TRUE,  FALSE);


-- ─────────────────────────────────────────────────────────────────────────────
-- Fact: Student Enrolments (from HEA Shiny dashboard)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_student_enrolments (
    institution_id      VARCHAR REFERENCES dim_institution(institution_id),
    academic_year       VARCHAR NOT NULL,    -- e.g. '2024/2025'
    gender              VARCHAR,             -- 'Female', 'Male', 'Other'
    eu_status           VARCHAR,             -- 'EU', 'Non-EU'  (HEA "Domicile Group")
    isced_code          VARCHAR,             -- e.g. '0912' for Medicine; NULL if broad field only
    isced_label         VARCHAR NOT NULL,    -- e.g. 'Health and welfare'
    programme_level     VARCHAR,             -- 'Undergraduate', 'Postgraduate'
    programme_type      VARCHAR,             -- e.g. 'Graduate Entry Medicine' if HEA separates it
    entry_type          VARCHAR,             -- 'New Entrant', 'Continuing'
    mode                VARCHAR,             -- 'Full Time', 'Part Time', 'Distance/Other'
    headcount           INTEGER,
    is_rounded          BOOLEAN DEFAULT TRUE, -- HEA rounds all figures to nearest 5
    source_file         VARCHAR NOT NULL,    -- filename of raw CSV
    load_date           DATE NOT NULL DEFAULT current_date
);

CREATE INDEX IF NOT EXISTS idx_enrol_year    ON fact_student_enrolments(academic_year);
CREATE INDEX IF NOT EXISTS idx_enrol_inst    ON fact_student_enrolments(institution_id);
CREATE INDEX IF NOT EXISTS idx_enrol_field   ON fact_student_enrolments(isced_label);


-- ─────────────────────────────────────────────────────────────────────────────
-- Fact: Health Graduates by Institution (CSO HGO08)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_health_graduates (
    institution_id      VARCHAR REFERENCES dim_institution(institution_id),
    graduation_year     INTEGER NOT NULL,   -- e.g. 2023
    field_of_study      VARCHAR NOT NULL,   -- CSO field label
    gender              VARCHAR,
    graduate_count      INTEGER,
    data_excluded       BOOLEAN DEFAULT FALSE,
    exclusion_reason    VARCHAR,            -- e.g. 'RCSI PPSN validation issues 2012-2016 (CSO background note)'
    source_table        VARCHAR NOT NULL,   -- e.g. 'HGO08'
    load_date           DATE NOT NULL DEFAULT current_date
);

CREATE INDEX IF NOT EXISTS idx_hgrad_year  ON fact_health_graduates(graduation_year);
CREATE INDEX IF NOT EXISTS idx_hgrad_inst  ON fact_health_graduates(institution_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- Fact: Graduate Outcomes — "Not Captured" proxy for emigration (CSO HGO09)
-- NOTE (Decision E002): "Not Captured" = graduates not found in Irish employment
-- or social insurance records at N years post-graduation. This is NOT confirmed
-- emigration — some may be unemployed, on career breaks, or missed by the
-- matching algorithm. Always label as "not captured in Irish employment records".
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_graduate_outcomes (
    field_of_study          VARCHAR NOT NULL,
    graduation_year         INTEGER NOT NULL,
    years_since_graduation  INTEGER NOT NULL,  -- 1, 2, 3, 4, 5
    outcome_category        VARCHAR NOT NULL,  -- 'Employment', 'Further Study', 'Not Captured', etc.
    graduate_count          INTEGER,
    pct_of_cohort           NUMERIC(5,2),
    source_table            VARCHAR NOT NULL,  -- 'HGO09'
    load_date               DATE NOT NULL DEFAULT current_date
);

CREATE INDEX IF NOT EXISTS idx_outcome_field  ON fact_graduate_outcomes(field_of_study);
CREATE INDEX IF NOT EXISTS idx_outcome_year   ON fact_graduate_outcomes(graduation_year);


-- ─────────────────────────────────────────────────────────────────────────────
-- Fact: Graduate Returns to Ireland (CSO HGO11)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_graduate_returns (
    field_of_study      VARCHAR NOT NULL,
    graduation_year     INTEGER NOT NULL,
    years_since_return  INTEGER NOT NULL,
    returner_count      INTEGER,
    source_table        VARCHAR NOT NULL,  -- 'HGO11'
    load_date           DATE NOT NULL DEFAULT current_date
);


-- ─────────────────────────────────────────────────────────────────────────────
-- Fact: Programme Fees (manual register — Source C)
-- Decision E003: UCD GEM €18,800/year is student-verified ground truth (2025/26).
-- All other rows have verified_by NULL until confirmed from primary source.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_programme_fees (
    institution_id      VARCHAR REFERENCES dim_institution(institution_id),
    academic_year       VARCHAR NOT NULL,   -- e.g. '2025/26'
    programme_type      VARCHAR NOT NULL,   -- e.g. 'GEM', 'UG', 'International UG'
    fee_status          VARCHAR,            -- 'EU GEM', 'Non-EU', 'Free Fees'
    annual_fee_eur      NUMERIC(10,2),
    student_contrib     NUMERIC(10,2),      -- student contribution charge (if separate)
    other_mandatory     NUMERIC(10,2),      -- other mandatory charges
    -- VIRTUAL: total_annual_fee = annual_fee_eur + COALESCE(student_contrib,0) + COALESCE(other_mandatory,0)
    places_available    INTEGER,
    source_url          VARCHAR,
    verified_by         VARCHAR,            -- 'student', 'official-page', NULL=unverified
    verified_date       DATE,
    notes               VARCHAR
);

-- Seed with known data
INSERT OR IGNORE INTO fact_programme_fees VALUES
    ('UCD', '2025/26', 'GEM', 'EU GEM', 18800.00, NULL, NULL, NULL,
     'https://www.ucd.ie/medicine/', 'student', '2026-08-18',
     'Decision E003: confirmed by current UCD GEM student. Exact figure €18,800/year.');

-- Note: TCD and University of Galway do NOT offer GEM (undergraduate medicine only).
-- GEM providers: UCD, UCC, UL, RCSI only.

-- UCC 2025/26 — confirmed from official fee schedule euundergraduatefees202526
-- CK791 row: €15,500 tuition + €207 capitation = €15,707
-- Clinical placement contribution €750/yr applies additionally in years 2–4
INSERT OR IGNORE INTO fact_programme_fees VALUES
    ('UCC', '2025/26', 'GEM', 'EU GEM', 15707.00, NULL, 207.00, NULL,
     'https://www.ucc.ie/en/financeoffice/fees/schedules/euundergraduatefees202526/',
     'scraper', '2026-08-19',
     '€15,500 tuition + €207 capitation. Clinical placement fee €750/yr additional in years 2–4 (not in annual_fee_eur).');

-- UL 2025/26 — confirmed from official programme fees page (year label not shown; assumed current)
-- €15,820 tuition + €104 levy = €15,924
INSERT OR IGNORE INTO fact_programme_fees VALUES
    ('UL', '2025/26', 'GEM', 'EU GEM', 15924.00, 104.00, NULL, NULL,
     'https://www.ul.ie/study/undergraduate/medicine-graduate-entry/fees-and-funding',
     'scraper', '2026-08-19',
     '€15,820 tuition + €104 student levy. Healthcare screening €350 and iPad ~€600 additional Year 1 costs.');

-- RCSI 2025/26 — confirmed from official GEM fees page
-- Tuition €15,080 + student contribution €1,000 + IT fee €475 + health screening €380 (yr1) + NUI fee €135 (yr1) = €17,070
INSERT OR IGNORE INTO fact_programme_fees VALUES
    ('RCSI', '2025/26', 'GEM', 'EU GEM', 17070.00, 1000.00, 990.00, NULL,
     'https://www.rcsi.com/dublin/undergraduate/gem/fees-and-funding',
     'scraper', '2026-08-19',
     '€15,080 tuition + €1,000 student contribution + €475 IT fee + €380 health screening (yr1 only) + €135 NUI fee (yr1 only). other_mandatory = €475 ongoing annual; yr1 total higher.');

-- University of Galway: UG medicine only (not GEM), €7,408 p.a. 2026/27
INSERT OR IGNORE INTO fact_programme_fees VALUES
    ('NUIG', '2026/27', 'UG', 'EU', 7408.00, NULL, NULL, NULL,
     'https://www.universityofgalway.ie/courses/fees-and-funding/fees.html',
     'scraper', '2026-08-19',
     'Undergraduate medicine (MB BCh BAO). Not GEM. Includes levy.');
