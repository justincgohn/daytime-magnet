#!/usr/bin/env python3
"""
Process Census LEHD LODES Origin-Destination data into county-level commuter JSON.

Downloads state-level OD files (main + aux), aggregates block-to-block flows
to county-to-county using DuckDB, computes commuter metrics per county,
and outputs JSON for the Daytime Magnet frontend.

Data source: Census LEHD LODES v8
https://lehd.ces.census.gov/data/
"""

import json
import os
import urllib.request
import duckdb
from pathlib import Path

# --- Configuration ---

BASE_URL = "https://lehd.ces.census.gov/data/lodes/LODES8"
XWALK_URL = "https://lehd.ces.census.gov/data/lodes/LODES8/{st}/{st}_xwalk.csv.gz"
JOB_TYPE = "JT01"  # Primary jobs

# State abbreviations (lowercase) for LODES
STATES = [
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "dc", "fl",
    "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me",
    "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh",
    "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri",
    "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy"
]

# Year overrides: most states use 2023, but some lag
# Check availability and fall back
YEAR_OVERRIDES = {
    "ak": 2021,  # Alaska lags significantly
    "mi": 2021,  # Michigan lags
}
DEFAULT_YEAR = 2023

# Classification thresholds
MAGNET_THRESHOLD = 5.0      # net_swing_pct > +5% = Job Magnet
BEDROOM_THRESHOLD = -5.0    # net_swing_pct < -5% = Bedroom Community
SMALL_COUNTY_THRESHOLD = 1000  # live_here < 1000 = small county flag


def get_year(st):
    return YEAR_OVERRIDES.get(st, DEFAULT_YEAR)


def od_url(st, part, year):
    return f"{BASE_URL}/{st}/od/{st}_od_{part}_{JOB_TYPE}_{year}.csv.gz"


def xwalk_url(st):
    return XWALK_URL.format(st=st)


def download_file(url, dest):
    """Download a file if it doesn't already exist. Returns True if file exists."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        print(f"  Downloading {url}")
        urllib.request.urlretrieve(url, str(dest))
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def download_all(raw_dir):
    """Download all LODES OD files (main + aux) for each state."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    year_map = {}

    for st in STATES:
        year = get_year(st)
        year_map[st] = year
        files_for_state = []

        for part in ["main", "aux"]:
            url = od_url(st, part, year)
            filename = f"{st}_od_{part}_{JOB_TYPE}_{year}.csv.gz"
            dest = raw_dir / filename

            if download_file(url, dest):
                files_for_state.append(dest)
            else:
                # Try previous years as fallback
                for fallback_year in [year - 1, year - 2, year - 3]:
                    url_fb = od_url(st, part, fallback_year)
                    filename_fb = f"{st}_od_{part}_{JOB_TYPE}_{fallback_year}.csv.gz"
                    dest_fb = raw_dir / filename_fb
                    print(f"  Trying fallback year {fallback_year}...")
                    if download_file(url_fb, dest_fb):
                        files_for_state.append(dest_fb)
                        year_map[st] = fallback_year
                        break

        if files_for_state:
            downloaded.append((st, files_for_state))
            print(f"  {st.upper()} ({year_map[st]}): {len(files_for_state)} files")
        else:
            print(f"  {st.upper()}: NO FILES AVAILABLE")

    return downloaded, year_map


def download_crosswalks(raw_dir):
    """Download crosswalk files for county name lookup."""
    xwalk_dir = raw_dir / "xwalk"
    xwalk_dir.mkdir(parents=True, exist_ok=True)
    xwalk_files = []

    for st in STATES:
        url = xwalk_url(st)
        dest = xwalk_dir / f"{st}_xwalk.csv.gz"
        if download_file(url, dest):
            xwalk_files.append(dest)

    return xwalk_files


def aggregate_with_duckdb(downloaded, raw_dir):
    """
    Aggregate block-level OD pairs to county-level using DuckDB.
    Returns a DuckDB connection with the aggregated table.
    """
    con = duckdb.connect()

    # Create the aggregation table
    con.execute("""
        CREATE TABLE county_od (
            home_county VARCHAR,
            work_county VARCHAR,
            workers INTEGER
        )
    """)

    total_files = sum(len(files) for _, files in downloaded)
    processed = 0

    for st, files in downloaded:
        for filepath in files:
            processed += 1
            print(f"  Processing [{processed}/{total_files}] {filepath.name}...")

            # Read gzipped CSV, extract county FIPS, aggregate
            con.execute(f"""
                INSERT INTO county_od
                SELECT
                    SUBSTR(CAST(h_geocode AS VARCHAR), 1, 5) AS home_county,
                    SUBSTR(CAST(w_geocode AS VARCHAR), 1, 5) AS work_county,
                    SUM(S000) AS workers
                FROM read_csv_auto('{filepath}', compression='gzip')
                GROUP BY
                    SUBSTR(CAST(h_geocode AS VARCHAR), 1, 5),
                    SUBSTR(CAST(w_geocode AS VARCHAR), 1, 5)
            """)

    # Final aggregation (merge main + aux for same state pairs)
    print("  Final aggregation across all states...")
    con.execute("""
        CREATE TABLE county_flows AS
        SELECT home_county, work_county, SUM(workers) AS workers
        FROM county_od
        GROUP BY home_county, work_county
    """)

    row_count = con.execute("SELECT COUNT(*) FROM county_flows").fetchone()[0]
    print(f"  Total county-to-county flow pairs: {row_count:,}")

    return con


def build_county_names(con, raw_dir):
    """Build county FIPS → name mapping from crosswalk files."""
    xwalk_dir = raw_dir / "xwalk"
    county_names = {}

    if not xwalk_dir.exists():
        return county_names

    for xwalk_file in sorted(xwalk_dir.glob("*_xwalk.csv.gz")):
        try:
            result = con.execute(f"""
                SELECT DISTINCT
                    SUBSTR(CAST(cty AS VARCHAR), 1, 5) AS fips,
                    ctyname
                FROM read_csv_auto('{xwalk_file}', compression='gzip',
                     ignore_errors=true)
                WHERE cty IS NOT NULL AND ctyname IS NOT NULL
            """).fetchall()

            for fips, name in result:
                if fips and name and len(fips) == 5:
                    county_names[fips] = name
        except Exception as e:
            print(f"  Warning: Could not read {xwalk_file.name}: {e}")

    print(f"  Loaded {len(county_names)} county names from crosswalks")
    return county_names


def compute_metrics(con, county_names, year_map):
    """Compute per-county commuter metrics."""
    print("Computing per-county metrics...")

    # Get all unique counties
    counties = set()
    for row in con.execute("SELECT DISTINCT home_county FROM county_flows").fetchall():
        counties.add(row[0])
    for row in con.execute("SELECT DISTINCT work_county FROM county_flows").fetchall():
        counties.add(row[0])

    print(f"  Total unique counties: {len(counties)}")

    # For each county, compute metrics
    results = {}

    for fips in sorted(counties):
        if not fips or len(fips) != 5:
            continue

        # Internal workers (live and work in same county)
        internal = con.execute(
            "SELECT COALESCE(SUM(workers), 0) FROM county_flows WHERE home_county = ? AND work_county = ?",
            [fips, fips]
        ).fetchone()[0]

        # Total employed here (all jobs located in this county)
        employed_here = con.execute(
            "SELECT COALESCE(SUM(workers), 0) FROM county_flows WHERE work_county = ?",
            [fips]
        ).fetchone()[0]

        # Total living here (all workers residing in this county)
        live_here = con.execute(
            "SELECT COALESCE(SUM(workers), 0) FROM county_flows WHERE home_county = ?",
            [fips]
        ).fetchone()[0]

        in_commuters = employed_here - internal
        out_commuters = live_here - internal

        # Sanity check
        assert employed_here == internal + in_commuters, \
            f"Sanity check failed for {fips}: {employed_here} != {internal} + {in_commuters}"

        # Net swing percentage
        if live_here > 0:
            net_swing_pct = round((in_commuters - out_commuters) / live_here * 100, 1)
        else:
            net_swing_pct = 0.0

        # Classification
        if net_swing_pct > MAGNET_THRESHOLD:
            classification = "Job Magnet"
        elif net_swing_pct < BEDROOM_THRESHOLD:
            classification = "Bedroom Community"
        else:
            classification = "Self-Contained"

        # Small county flag
        small_county = live_here < SMALL_COUNTY_THRESHOLD

        # Determine data year from state FIPS
        state_fips = fips[:2]
        state_abbr = fips_to_state(state_fips)
        data_year = year_map.get(state_abbr, DEFAULT_YEAR) if state_abbr else DEFAULT_YEAR

        # County name
        name = county_names.get(fips, f"County {fips}")

        # Top 5 origins (where workers come from)
        top_origins = con.execute("""
            SELECT home_county, workers
            FROM county_flows
            WHERE work_county = ? AND home_county != ?
            ORDER BY workers DESC
            LIMIT 5
        """, [fips, fips]).fetchall()

        # Top 5 destinations (where residents go to work)
        top_destinations = con.execute("""
            SELECT work_county, workers
            FROM county_flows
            WHERE home_county = ? AND work_county != ?
            ORDER BY workers DESC
            LIMIT 5
        """, [fips, fips]).fetchall()

        results[fips] = {
            "name": name,
            "employed_here": employed_here,
            "live_here": live_here,
            "internal": internal,
            "in_commuters": in_commuters,
            "out_commuters": out_commuters,
            "net_swing_pct": net_swing_pct,
            "classification": classification,
            "data_year": data_year,
            "small_county": small_county,
            "top_origins": [
                {"fips": r[0], "name": county_names.get(r[0], f"County {r[0]}"), "workers": r[1]}
                for r in top_origins
            ],
            "top_destinations": [
                {"fips": r[0], "name": county_names.get(r[0], f"County {r[0]}"), "workers": r[1]}
                for r in top_destinations
            ],
        }

    return results


# State FIPS → abbreviation mapping
STATE_FIPS_MAP = {
    "01": "al", "02": "ak", "04": "az", "05": "ar", "06": "ca",
    "08": "co", "09": "ct", "10": "de", "11": "dc", "12": "fl",
    "13": "ga", "15": "hi", "16": "id", "17": "il", "18": "in",
    "19": "ia", "20": "ks", "21": "ky", "22": "la", "23": "me",
    "24": "md", "25": "ma", "26": "mi", "27": "mn", "28": "ms",
    "29": "mo", "30": "mt", "31": "ne", "32": "nv", "33": "nh",
    "34": "nj", "35": "nm", "36": "ny", "37": "nc", "38": "nd",
    "39": "oh", "40": "ok", "41": "or", "42": "pa", "44": "ri",
    "45": "sc", "46": "sd", "47": "tn", "48": "tx", "49": "ut",
    "50": "vt", "51": "va", "53": "wa", "54": "wv", "55": "wi",
    "56": "wy"
}


def fips_to_state(state_fips):
    return STATE_FIPS_MAP.get(state_fips)


def compute_percentiles(results):
    """Compute percentile for net_swing_pct across all counties."""
    # Get all swing values (exclude tiny counties for meaningful percentiles)
    swings = sorted([
        r["net_swing_pct"] for r in results.values()
        if not r["small_county"]
    ])
    n = len(swings)

    for fips, data in results.items():
        swing = data["net_swing_pct"]
        count_below = sum(1 for s in swings if s < swing)
        data["percentile"] = round((count_below / n) * 100) if n > 0 else 50


def build_county_list(results):
    """Build the autocomplete county list."""
    county_list = []
    for fips, data in sorted(results.items()):
        name = data["name"]
        # Extract state from county name (e.g., "Philadelphia County, PA" → "PA")
        parts = name.rsplit(", ", 1)
        state = parts[1] if len(parts) > 1 else ""
        county_list.append({
            "fips": fips,
            "name": name,
            "state": state
        })
    return county_list


def save_json(data, path):
    """Save data as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"  Saved {path} ({size_mb:.1f} MB)")


def main():
    script_dir = Path(__file__).parent
    raw_dir = script_dir.parent / "raw"
    processed_dir = script_dir.parent / "processed"
    docs_data_dir = script_dir.parent.parent / "docs" / "data"

    print("=" * 60)
    print("Daytime Magnet — LODES Data Pipeline")
    print("=" * 60)

    # Step 1: Download OD files
    print("\n[1/6] Downloading LODES OD files...")
    downloaded, year_map = download_all(raw_dir)
    print(f"  Downloaded files for {len(downloaded)} states")

    # Step 2: Download crosswalks (for county names)
    print("\n[2/6] Downloading crosswalk files...")
    download_crosswalks(raw_dir)

    # Step 3: Aggregate with DuckDB
    print("\n[3/6] Aggregating to county level with DuckDB...")
    con = aggregate_with_duckdb(downloaded, raw_dir)

    # Step 4: Build county names
    print("\n[4/6] Building county name lookup...")
    county_names = build_county_names(con, raw_dir)

    # Step 5: Compute metrics
    print("\n[5/6] Computing commuter metrics...")
    results = compute_metrics(con, county_names, year_map)
    print(f"  Computed metrics for {len(results)} counties")

    # Compute percentiles
    compute_percentiles(results)

    # Step 6: Save output
    print("\n[6/6] Saving JSON output...")
    save_json(results, processed_dir / "commuter_data.json")
    save_json(results, docs_data_dir / "commuter_data.json")

    county_list = build_county_list(results)
    save_json(county_list, processed_dir / "county_list.json")
    save_json(county_list, docs_data_dir / "county_list.json")

    # Spot checks
    print("\n" + "=" * 60)
    print("SPOT CHECKS")
    print("=" * 60)
    spot_checks = ["36061", "06075", "51013", "36059", "37183"]  # Manhattan, SF, Arlington VA, Nassau NY, Wake NC
    for fips in spot_checks:
        if fips in results:
            d = results[fips]
            print(f"\n  {d['name']} ({fips}):")
            print(f"    Employed here: {d['employed_here']:,}")
            print(f"    Live here: {d['live_here']:,}")
            print(f"    Internal: {d['internal']:,}")
            print(f"    In-commuters: {d['in_commuters']:,}")
            print(f"    Out-commuters: {d['out_commuters']:,}")
            print(f"    Net swing: {d['net_swing_pct']:+.1f}%")
            print(f"    Classification: {d['classification']}")
            print(f"    Percentile: {d['percentile']}")
        else:
            print(f"\n  {fips}: NOT FOUND")

    print(f"\nTotal counties: {len(results)}")
    print("Done!")

    con.close()


if __name__ == "__main__":
    main()
