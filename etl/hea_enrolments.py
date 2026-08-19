"""
hea_enrolments.py
=================
Ireland in Data — HEA Enrolments ETL
Scrapes the HEA Shiny dashboard (https://highereducationauthority.shinyapps.io/Enrolments25/)
and saves a dated CSV snapshot to data/raw/hea/.

Shiny input IDs confirmed via live DOM inspection 2026-08-18:
  Academic & Programme Filters (accordion section "Academic & Programme Filters"):
    Course_Level_filter_p1      – ["Undergraduate", "Postgraduate"]
    Field_of_Study_filter_p1    – 11 ISCED broad fields; "Health and welfare" is what we want
    Institute_filter_p1         – 26 institutions
    Mode_of_Study_filter_p1     – ["Full Time", "Part Time", "Distance/Other"]
    New_Entrant_status_filter_p1– ["New Entrant", "Continuing"]
    Programme_Type_filter_p1    – 14 programme types (includes GEM if separated)

  Student Demographic Filters (accordion section):
    Age_Group_filter_p1         – age bands
    Domicile_Group_filter_p1    – EU / Non-EU domicile (key for our analysis)
    Gender_filter_p1            – ["Female", "Male", "Other"]

  Display controls:
    Single_row_select           – row grouping for single-row table view
    filter_accordion            – which accordion panels are open
    tabsetPanel                 – active tab
    reset_btn                   – action button (resets all filters)
    toggle_expand_single        – action button
    toggle_expand_multi         – action button

  Download button:  #Download  (confirmed from .clientdata_output_Download_hidden key)

Run:
  pip install playwright
  playwright install chromium
  python hea_enrolments.py

Output:
  data/raw/hea/hea_enrolments_health_welfare_YYYY-MM-DD.csv        Programme Type x academic year
  data/raw/hea/hea_enrolments_domicile_YYYY-MM-DD.csv              Domicile Group x academic year
  data/raw/hea/hea_enrolments_gender_YYYY-MM-DD.csv                Gender x academic year
  data/raw/hea/hea_enrolments_medicine_institutions_YYYY-MM-DD.csv Programme Type x academic year, medicine institutions only
All four are Health and welfare field only, each a different Row Variable
breakdown of the SAME underlying population (except the last, which also
narrows institutions) — see hea_csv_loader.py's module docstring before
combining them.

Decision E001: it is unknown whether HEA data distinguishes UG from GEM medicine within
"Health and welfare". After the first download, inspect the Programme Type column.
If GEM is a separate programme type, we can filter to it directly.
"""

import asyncio
import os
from datetime import date
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HEA_URL = "https://highereducationauthority.shinyapps.io/Enrolments25/"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "hea"
TODAY = date.today().isoformat()

# The field-of-study value we want for medicine (confirmed visible in DOM)
TARGET_FIELD = "Health and welfare"

# Institutions offering medicine (used for a focused subset download)
MEDICINE_INSTITUTIONS = [
    "University College Dublin",
    "University College Cork",
    "Trinity College Dublin",
    "University of Galway",
    "University of Limerick",
    "Royal College of Surgeons in Ireland",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def wait_for_shiny(page, timeout=60_000):
    """Wait for Shiny to finish processing (spinner disappears)."""
    try:
        await page.wait_for_selector(".shiny-busy", state="visible", timeout=5_000)
    except PlaywrightTimeout:
        pass  # may already be done
    await page.wait_for_selector(".shiny-busy", state="hidden", timeout=timeout)


async def set_shiny_input(page, input_id: str, value):
    """
    Set a Shiny input value programmatically.
    Works for selectize multi-selects (lists) and single selects (strings).
    Passes {priority: 'event'} so Shiny treats it as a real user change.
    """
    escaped = repr(value)  # safe for list or string
    js = f"""
    (function() {{
        if (!window.Shiny) return 'Shiny not found';
        Shiny.setInputValue('{input_id}', {escaped}, {{priority: 'event'}});
        return 'ok';
    }})()
    """
    result = await page.evaluate(js)
    return result


async def open_accordion(page, panel_name: str):
    """
    Ensure an accordion panel is open by setting filter_accordion via Shiny.
    panel_name: one of "Academic & Programme Filters", "Student Demographic Filters"
    """
    # Check current state
    current = await page.evaluate(
        "window.Shiny?.shinyapp?.$inputValues?.filter_accordion || []"
    )
    if panel_name not in (current or []):
        new_val = list(current or []) + [panel_name]
        await set_shiny_input(page, "filter_accordion", new_val)
        await wait_for_shiny(page)


async def download_current_view(page, filename: str) -> Path:
    """
    Click the Download button and save the CSV.
    Returns the path where the file was saved.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / filename

    async with page.expect_download(timeout=60_000) as download_info:
        # Download button is a Shiny downloadButton — renders as <a> with id="Download"
        await page.click("#Download")

    dl = await download_info.value
    await dl.save_as(dest)
    print(f"  Saved → {dest}")
    return dest


# ---------------------------------------------------------------------------
# Main scrape
# ---------------------------------------------------------------------------

async def scrape_hea():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        print(f"Loading {HEA_URL} ...")
        # NOTE: wait_until="networkidle" is unreliable against this app —
        # its websocket keeps the connection looking "busy" indefinitely, so
        # networkidle sometimes never fires and goto() times out at 120s
        # (observed repeatedly 2026-08-19). domcontentloaded + waiting for
        # window.Shiny to exist is the reliable signal instead.
        await page.goto(HEA_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_function("window.Shiny !== undefined", timeout=60_000)
        await page.wait_for_timeout(5000)  # let Shiny finish its initial render
        print("  Shiny app ready.")

        # ── Open both accordion panels ──────────────────────────────────────
        await open_accordion(page, "Academic & Programme Filters")
        await open_accordion(page, "Student Demographic Filters")

        # ── Download 1: All data for Health and Welfare field ───────────────
        print("Setting Field of Study → Health and welfare ...")
        await set_shiny_input(page, "Field_of_Study_filter_p1", [TARGET_FIELD])
        await wait_for_shiny(page)

        # Both course levels
        await set_shiny_input(page, "Course_Level_filter_p1", ["Undergraduate", "Postgraduate"])
        await wait_for_shiny(page)

        # All institutions (default — don't filter by institution for broad download)
        # Domicile: all (EU + Non-EU) — we want both for our EU/non-EU breakdown
        # Gender: all

        print("Downloading Health & Welfare snapshot ...")
        await download_current_view(
            page,
            f"hea_enrolments_health_welfare_{TODAY}.csv"
        )

        # ── Download 2: same scope, Row Variable → Domicile Group ───────────
        # Ireland / (Other) EU / Non-EU / Great Britain / Northern Ireland /
        # Unknown — still all institutions, still Health and welfare.
        print("Setting Row Variable → Domicile Group ...")
        await set_shiny_input(page, "Single_row_select", "Domicile Group")
        await wait_for_shiny(page)

        print("Downloading domicile-group snapshot ...")
        await download_current_view(
            page,
            f"hea_enrolments_domicile_{TODAY}.csv"
        )

        # ── Download 3: same scope, Row Variable → Gender ────────────────────
        print("Setting Row Variable → Gender ...")
        await set_shiny_input(page, "Single_row_select", "Gender")
        await wait_for_shiny(page)

        print("Downloading gender snapshot ...")
        await download_current_view(
            page,
            f"hea_enrolments_gender_{TODAY}.csv"
        )

        # ── Download 4: Medicine institutions only (belt-and-braces) ────────
        # Back to Row Variable → Programme Type for this one, matching the
        # first download's shape.
        print("Setting Row Variable → Programme Type, filtering to medicine institutions ...")
        await set_shiny_input(page, "Single_row_select", "Programme Type")
        await wait_for_shiny(page)
        await set_shiny_input(page, "Institute_filter_p1", MEDICINE_INSTITUTIONS)
        await wait_for_shiny(page)

        print("Downloading medicine-institutions snapshot ...")
        await download_current_view(
            page,
            f"hea_enrolments_medicine_institutions_{TODAY}.csv"
        )

        # ── Download 3 (optional): Full dataset — all fields, all institutions ─
        # Uncomment to get the complete HEA file for archiving:
        #
        # print("Resetting all filters for full dataset ...")
        # await page.click("#reset_btn")
        # await wait_for_shiny(page)
        # await download_current_view(page, f"hea_enrolments_all_fields_{TODAY}.csv")

        await browser.close()

    print("\nDone.")
    print(f"Files in {RAW_DIR}:")
    for f in sorted(RAW_DIR.glob("*.csv")):
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")


# ---------------------------------------------------------------------------
# Post-download validation printout
# ---------------------------------------------------------------------------

def validate_downloads():
    """
    After running the scraper, print a quick summary of what was downloaded.
    Run separately or append to scrape pipeline:
      python hea_enrolments.py --validate
    """
    import csv

    files = sorted(RAW_DIR.glob(f"*{TODAY}*.csv"))
    if not files:
        print("No files found for today.")
        return

    for fpath in files:
        print(f"\n{'='*60}")
        print(f"File: {fpath.name}")
        with open(fpath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"  Rows: {len(rows)}")
        if rows:
            print(f"  Columns: {list(rows[0].keys())}")
            # Print unique values for key columns
            for col in ["Field of Study", "Programme Type", "Domicile", "EU Status",
                        "Course Level", "Gender", "Mode of Study"]:
                vals = sorted(set(r.get(col, "") for r in rows if r.get(col)))
                if vals:
                    print(f"  {col}: {vals}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if "--validate" in sys.argv:
        validate_downloads()
    else:
        asyncio.run(scrape_hea())
