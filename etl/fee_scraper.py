"""
fee_scraper.py
==============
Ireland in Data — GEM Fee Scraper
Fetches the current-year fee from each institution's official fee page,
compares against the stored value in DuckDB, and prints a human-reviewable
diff. Optionally writes confirmed figures back to the database.

GEM providers in Ireland (as of 2025/26):
  UCD   University College Dublin          €18,800  (student-verified)
  UCC   University College Cork            €15,707  (€15,500 + €207 capitation)
  UL    University of Limerick             €15,924  (€15,820 + €104 levy)
  RCSI  Royal College of Surgeons in Ireland €17,070

Not GEM providers: TCD (UG only), University of Galway (UG only).

URL strategies:
  UCC:   URL includes the academic year (e.g. euundergraduatefees202526) — construct dynamically.
  RCSI:  Stable dedicated GEM fees page — parse itemised table.
  UL:    Stable programme fees page — parse fee figure.
  UCD:   Programme page lists fee — parse from known CSS selector.

Run:
  pip install requests beautifulsoup4 duckdb
  python fee_scraper.py                        # dry-run: print diff only
  python fee_scraper.py --write                # write confirmed changes to DB
  python fee_scraper.py --year 2026/27         # override target academic year
  python fee_scraper.py --db path/to/db.duckdb

Schedule: run once in September each year when institutions publish new fees.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeeResult:
    institution_id: str
    institution_name: str
    academic_year: str
    total_fee: Optional[float]
    breakdown: dict = field(default_factory=dict)
    source_url: str = ""
    notes: str = ""
    parse_ok: bool = True
    error: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; IrelandInData-FeeBot/1.0; "
        "+https://irelandindata.ie/about)"
    )
}


def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def parse_euro(text: str) -> Optional[float]:
    """Extract first euro amount from a string, e.g. '€15,707' → 15707.0"""
    m = re.search(r"€\s*([\d,]+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1).replace(",", ""))
    # Also handle plain numbers like '15707'
    m = re.search(r"\b(\d{4,6}(?:\.\d+)?)\b", text)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def academic_year_slug(year_str: str) -> str:
    """'2025/26' → '202526'"""
    return year_str.replace("/", "").replace("-", "")


# ─────────────────────────────────────────────────────────────────────────────
# Per-institution scrapers
# ─────────────────────────────────────────────────────────────────────────────

def next_academic_year(academic_year: str) -> str:
    """'2025/26' -> '2026/27'"""
    start = int(academic_year.split("/")[0])
    return f"{start + 1}/{str(start + 2)[-2:]}"


def scrape_ucc(academic_year: str) -> FeeResult:
    """
    UCC publishes a fee schedule per academic year at a predictable URL.
    Pattern: /en/financeoffice/fees/schedules/euundergraduatefees{SLUG}/
    GEM is listed as CK791 (Graduate Entry to Medicine).

    UCC only keeps the current + next academic year's schedule live; once a
    year rolls over, the prior year's page 404s. If the requested year is
    gone, fall back to the next academic year's page and flag the result
    as coming from a later year than requested.
    """
    requested_year = academic_year
    slug = academic_year_slug(academic_year)
    url = f"https://www.ucc.ie/en/financeoffice/fees/schedules/euundergraduatefees{slug}/"

    result = FeeResult(
        institution_id="UCC",
        institution_name="University College Cork",
        academic_year=academic_year,
        total_fee=None,
        source_url=url,
    )

    try:
        try:
            soup = fetch(url)
        except requests.HTTPError as e:
            if e.response.status_code != 404:
                raise
            # Requested year's page has likely aged off the site — try next year.
            fallback_year = next_academic_year(academic_year)
            fallback_slug = academic_year_slug(fallback_year)
            fallback_url = (
                f"https://www.ucc.ie/en/financeoffice/fees/schedules/"
                f"euundergraduatefees{fallback_slug}/"
            )
            soup = fetch(fallback_url)
            result.academic_year = fallback_year
            result.source_url = fallback_url
            result.notes = (
                f"Requested year {requested_year} page no longer live on ucc.ie "
                f"(404) — showing {fallback_year} figures instead. "
            )
        text = soup.get_text(" ", strip=True)

        # Look for CK791 row (the GEM course code). UCC's table lists columns
        # as Total, Capitation, Student Contribution, Tuition (total-first) —
        # e.g. "CK791 €16,010 €210 N/A €15,800". Take only the euro amounts
        # in a tight window right after "CK791" (before the next course row
        # starts) so we don't bleed into the following course's figures.
        ck791_match = re.search(
            r"CK791.{0,300}?(€[\d,]+)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if ck791_match:
            window_start = text.find("CK791")
            # Stop at the next course code (4 letters + 3 digits) if one
            # appears before 400 chars, so we don't pull in the next row.
            window = text[window_start: window_start + 400]
            next_course = re.search(r"\b[A-Z]{2}\d{3}\b", window[5:])
            if next_course:
                window = window[: 5 + next_course.start()]
            amounts = [parse_euro(m) for m in re.findall(r"€[\d,]+", window) if parse_euro(m)]
            if amounts:
                total = amounts[0]  # first figure after CK791 is UCC's published total
                capitation = amounts[1] if len(amounts) > 1 else None
                tuition = amounts[3] if len(amounts) > 3 else None
                result.total_fee = total
                result.breakdown = {"total": total, "capitation": capitation, "tuition": tuition}
                result.notes += (
                    "Clinical placement contribution €750/yr applies in years 2–4 "
                    "(not included in total_fee — add to notes in DB)"
                )
        else:
            # Fallback: search for "Graduate Entry" near a euro figure
            gem_match = re.search(
                r"[Gg]raduate [Ee]ntry.{0,200}?(€[\d,]+(?:\.\d+)?)",
                text,
                re.DOTALL,
            )
            if gem_match:
                result.total_fee = parse_euro(gem_match.group(1))
            else:
                result.parse_ok = False
                result.error = "Could not locate CK791 or 'Graduate Entry' fee in page"

    except requests.HTTPError as e:
        result.parse_ok = False
        result.error = f"HTTP {e.response.status_code} — URL may need updating for this year"
    except Exception as e:
        result.parse_ok = False
        result.error = str(e)

    return result


def scrape_rcsi(academic_year: str) -> FeeResult:
    """
    RCSI has a stable dedicated GEM fees page with an itemised table.
    Looks for EU fee total; also captures the per-item breakdown.
    """
    url = "https://www.rcsi.com/dublin/undergraduate/gem/fees-and-funding"
    result = FeeResult(
        institution_id="RCSI",
        institution_name="Royal College of Surgeons in Ireland",
        academic_year=academic_year,
        total_fee=None,
        source_url=url,
    )

    try:
        soup = fetch(url)
        text = soup.get_text(" ", strip=True)

        # Find the section relevant to the target academic year
        # RCSI lists "2025/26" style labels; find the closest match
        year_short = academic_year  # e.g. "2025/26"
        year_idx = text.find(year_short)

        if year_idx == -1:
            # Try just the start year
            year_short_alt = academic_year.split("/")[0]
            year_idx = text.find(year_short_alt)

        if year_idx >= 0:
            window = text[year_idx: year_idx + 600]
            # Look for "Total" fee
            total_match = re.search(
                r"[Tt]otal.{0,50}?(€[\d,]+)",
                window,
            )
            if total_match:
                result.total_fee = parse_euro(total_match.group(1))
            else:
                # Sum all euro amounts in window
                amounts = [parse_euro(m) for m in re.findall(r"€[\d,]+", window) if parse_euro(m)]
                if amounts:
                    result.total_fee = max(amounts)

            # Capture breakdown items
            breakdown_matches = re.findall(
                r"([A-Za-z /\-]+)\s+(€[\d,]+)",
                window,
            )
            result.breakdown = {k.strip(): parse_euro(v) for k, v in breakdown_matches}
            result.notes = (
                "Health screening (€380) and NUI fee (€135) are one-time Year 1 costs; "
                "total_fee includes them — ongoing annual cost is lower."
            )
        else:
            result.parse_ok = False
            result.error = f"Could not find year '{year_short}' on page — may be published later"

    except Exception as e:
        result.parse_ok = False
        result.error = str(e)

    return result


def scrape_ul(academic_year: str) -> FeeResult:
    """
    UL has a stable GEM fees-and-funding programme page.
    Fee structure: tuition + student levy = total.
    """
    url = "https://www.ul.ie/study/undergraduate/medicine-graduate-entry/fees-and-funding"
    result = FeeResult(
        institution_id="UL",
        institution_name="University of Limerick",
        academic_year=academic_year,
        total_fee=None,
        source_url=url,
    )

    try:
        soup = fetch(url)
        text = soup.get_text(" ", strip=True)

        # Look for "EU fees per year €X" or similar
        eu_match = re.search(
            r"EU fees? per year\s*(€[\d,]+)",
            text,
            re.IGNORECASE,
        )
        if eu_match:
            result.total_fee = parse_euro(eu_match.group(1))
        else:
            # Fallback: find tuition + levy pattern
            tuition_match = re.search(r"[Tt]uition\s*:?\s*(€[\d,]+)", text)
            levy_match = re.search(r"[Ll]evy\s*:?\s*(€[\d,]+)", text)
            if tuition_match:
                tuition = parse_euro(tuition_match.group(1))
                levy = parse_euro(levy_match.group(1)) if levy_match else 0
                result.total_fee = (tuition or 0) + (levy or 0)
                result.breakdown = {"tuition": tuition, "levy": levy}
            else:
                result.parse_ok = False
                result.error = "Could not locate EU fee figure"

        result.notes = "Healthcare screening €350 and iPad ~€600 are additional Year 1 costs (not in total_fee)"

    except Exception as e:
        result.parse_ok = False
        result.error = str(e)

    return result


def scrape_ucd(academic_year: str) -> FeeResult:
    """
    UCD's marketing course page (ucd.ie/courses/medicine-graduate-entry) is a
    dead client-side meta-refresh — not actually JS-rendered content, just a
    stale redirect. The real fee table lives in a legacy SISWeb system that
    UCD's own official fees page (ucd.ie/students/fees/eucoursefees/...)
    embeds via <iframe>. That endpoint returns plain server-rendered HTML —
    no browser/JS execution needed — and is keyed by ACYR=<start year>.

    UCD GEM is course code DN401, "Medicine (Graduate Entry)", fee category
    MDS9, under RESD=EU&DGLEV=UG (GEM is fee-classified as undergraduate).
    """
    start_year = academic_year.split("/")[0]
    url = (
        f"https://sisweb.ucd.ie/usis/!W_HU_MENU.P_PUBLISH"
        f"?p_tag=FEESLEVEL&RESD=EU&DGLEV=UG&ACYR={start_year}"
    )
    result = FeeResult(
        institution_id="UCD",
        institution_name="University College Dublin",
        academic_year=academic_year,
        total_fee=None,
        source_url=url,
    )

    try:
        soup = fetch(url)
        text = soup.get_text(" ", strip=True)

        # DN401 = Medicine (Graduate Entry). Anchor on the course code so we
        # don't match "Vet Medicine (Graduate Entry)" (DN301) instead.
        dn401_match = re.search(
            r"Medicine \(Graduate Entry\) DN401\s+School of Medicine\s+"
            r"Full Time\s+Per Year\s+(?:\w{3}\s+)?([\d,]+\.\d{2})",
            text,
        )
        if dn401_match:
            # Captured group is a plain "18,880.00" figure (no € prefix, and
            # only 2 digits after the comma) — parse_euro's regexes don't
            # match that shape, so convert directly instead.
            result.total_fee = float(dn401_match.group(1).replace(",", ""))
        else:
            result.parse_ok = False
            result.error = "Could not locate DN401 (Medicine Graduate Entry) row in SISWeb fee table"

    except requests.HTTPError as e:
        result.parse_ok = False
        result.error = f"HTTP {e.response.status_code} — SISWeb ACYR param may need updating for this year"
    except Exception as e:
        result.parse_ok = False
        result.error = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Diff against database
# ─────────────────────────────────────────────────────────────────────────────

def load_stored_fees(db_path: str, academic_year: str) -> dict:
    """Return {institution_id: annual_fee_eur} for the given year from DuckDB."""
    try:
        import duckdb
        conn = duckdb.connect(db_path, read_only=True)
        rows = conn.execute("""
            SELECT institution_id, annual_fee_eur
            FROM fact_programme_fees
            WHERE academic_year = ?
              AND programme_type = 'GEM'
              AND fee_status = 'EU GEM'
        """, [academic_year]).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        print(f"  [DB] Could not load stored fees: {e}")
        return {}


def write_fee_to_db(result: FeeResult, db_path: str):
    import duckdb
    conn = duckdb.connect(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO fact_programme_fees
            (institution_id, academic_year, programme_type, fee_status,
             annual_fee_eur, source_url, verified_by, verified_date, notes)
        VALUES (?, ?, 'GEM', 'EU GEM', ?, ?, 'scraper', ?, ?)
    """, [
        result.institution_id,
        result.academic_year,
        result.total_fee,
        result.source_url,
        date.today().isoformat(),
        result.notes,
    ])
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

SCRAPERS = {
    "UCD":  scrape_ucd,
    "UCC":  scrape_ucc,
    "UL":   scrape_ul,
    "RCSI": scrape_rcsi,
}


def current_academic_year() -> str:
    """Best guess at current academic year: after July, flip to next."""
    today = date.today()
    if today.month >= 7:
        return f"{today.year}/{str(today.year + 1)[-2:]}"
    return f"{today.year - 1}/{str(today.year)[-2:]}"


def main():
    parser = argparse.ArgumentParser(description="Ireland in Data — GEM Fee Scraper")
    parser.add_argument(
        "--year", default=None,
        help="Academic year to target, e.g. '2025/26' (default: auto-detect)"
    )
    parser.add_argument(
        "--db", default="data/ireland_in_data.duckdb",
        help="Path to DuckDB file (for diff and optional write)"
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write scraped fees to the database (after human review of diff)"
    )
    parser.add_argument(
        "--institutions", nargs="+", default=list(SCRAPERS.keys()),
        help="Which institutions to scrape (default: all)"
    )
    args = parser.parse_args()

    academic_year = args.year or current_academic_year()
    print(f"\nIreland in Data — GEM Fee Scraper")
    print(f"Target year: {academic_year}")
    print(f"Institutions: {', '.join(args.institutions)}")
    print(f"{'─' * 60}\n")

    stored = load_stored_fees(args.db, academic_year)
    results = []
    changes = []

    for inst_id in args.institutions:
        if inst_id not in SCRAPERS:
            print(f"⚠  Unknown institution: {inst_id}")
            continue

        print(f"Scraping {inst_id}...")
        result = SCRAPERS[inst_id](academic_year)
        results.append(result)

        status = "✅" if result.parse_ok and result.total_fee else "❌"
        fee_str = f"€{result.total_fee:,.0f}" if result.total_fee else "N/A"
        print(f"  {status} {result.institution_name}: {fee_str}")
        if not result.parse_ok:
            print(f"     ERROR: {result.error}")
        if result.notes:
            print(f"     NOTE: {result.notes}")

        stored_fee = stored.get(inst_id)
        if stored_fee is not None:
            stored_fee = float(stored_fee)
        if stored_fee is not None and result.total_fee is not None:
            if abs(stored_fee - result.total_fee) > 1:
                delta = result.total_fee - stored_fee
                print(f"     ⚡ CHANGE: was €{stored_fee:,.0f} → now €{result.total_fee:,.0f} "
                      f"({'+' if delta > 0 else ''}{delta:,.0f})")
                changes.append(result)
            else:
                print(f"     → No change from stored €{stored_fee:,.0f}")
        elif result.total_fee is not None and inst_id not in stored:
            print(f"     → New entry (not in DB for {academic_year})")
            changes.append(result)

        print()

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"{'─' * 60}")
    print(f"Summary: {len([r for r in results if r.parse_ok and r.total_fee])} scraped OK, "
          f"{len([r for r in results if not r.parse_ok])} failed, "
          f"{len(changes)} changes detected\n")

    if changes:
        print("CHANGES TO REVIEW:")
        for r in changes:
            print(f"  {r.institution_id:6s}  {r.academic_year}  €{r.total_fee:>8,.0f}  {r.source_url}")
        print()

    if args.write:
        if not changes:
            print("No changes to write.")
        else:
            print(f"Writing {len(changes)} changes to {args.db}...")
            for r in changes:
                if r.parse_ok and r.total_fee:
                    write_fee_to_db(r, args.db)
                    print(f"  Wrote {r.institution_id} {r.academic_year} €{r.total_fee:,.0f}")
            print("Done. Run with --validate to double-check.")
    else:
        if changes:
            print("Dry-run: no changes written. Re-run with --write to commit.")

    # Return exit code 1 if any parse failed (useful for CI alerting)
    if any(not r.parse_ok for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
